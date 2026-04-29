"""Tests for app.security.device_auth.get_current_device — SGN-BE-04.

Mounts the dep on a minimal FastAPI app; seeds and cleans up
`signage_devices` rows via asyncpg so we avoid dragging in the full
test-client fixture (which resets app_settings and needs the main app).

Skips cleanly when POSTGRES_* env is not set (matches the convention in
test_signage_schema_roundtrip.py) so `pytest --collect-only` stays green.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import jwt
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.models import SignageDevice
from app.security.device_auth import get_current_device
from app.services.signage_pairing import mint_device_jwt


def _pg_dsn() -> str | None:
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    host_env = os.environ.get("POSTGRES_HOST")
    host = host_env if (host_env and host_env != "localhost") else "db"
    port = os.environ.get("POSTGRES_PORT", "5432")
    if not (user and password and db):
        return None
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def _require_db() -> str:
    dsn = _pg_dsn()
    if dsn is None:
        pytest.skip("POSTGRES_* not set — device_auth tests need a live DB")
    try:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Postgres not reachable ({dsn}): {exc!s}")
    return dsn


@pytest.fixture
def app():
    a = FastAPI()

    @a.get("/device-protected")
    async def device_protected(device: SignageDevice = Depends(get_current_device)):
        return {"id": str(device.id), "revoked": device.revoked_at is not None}

    return a


@pytest_asyncio.fixture
async def client(app):
    # Dispose the shared async engine pool so this event loop gets fresh conns.
    from app.database import engine

    await engine.dispose()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        await engine.dispose()


async def _insert_device(
    dsn: str, *, revoked: bool = False
) -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status, revoked_at) "
            "VALUES ($1, $2, 'pending', $3)",
            device_id,
            f"test-device-{device_id.hex[:6]}",
            datetime.now(timezone.utc) if revoked else None,
        )
    finally:
        await conn.close()
    return device_id


async def _delete_device(dsn: str, device_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute("DELETE FROM signage_devices WHERE id = $1", device_id)
    finally:
        await conn.close()


# ---------- tests ----------


async def test_missing_authorization_returns_401(client):
    r = await client.get("/device-protected")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"
    assert r.json()["detail"] == "invalid or missing device token"


async def test_malformed_token_returns_401(client):
    r = await client.get(
        "/device-protected", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert r.status_code == 401


async def test_wrong_scope_returns_401(client):
    # signed correctly but scope != "device"
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "scope": "admin",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(
        payload, settings.SIGNAGE_DEVICE_JWT_SECRET, algorithm="HS256"
    )
    r = await client.get(
        "/device-protected", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_sub_not_uuid_returns_401(client):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "not-a-uuid",
        "scope": "device",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(
        payload, settings.SIGNAGE_DEVICE_JWT_SECRET, algorithm="HS256"
    )
    r = await client.get(
        "/device-protected", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_expired_token_returns_401(client):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "scope": "device",
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(
        payload, settings.SIGNAGE_DEVICE_JWT_SECRET, algorithm="HS256"
    )
    r = await client.get(
        "/device-protected", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_unknown_device_returns_401(client):
    await _require_db()
    token = mint_device_jwt(uuid.uuid4())  # device_id never inserted
    r = await client.get(
        "/device-protected", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401


async def test_valid_device_returns_row(client):
    dsn = await _require_db()
    device_id = await _insert_device(dsn, revoked=False)
    try:
        token = mint_device_jwt(device_id)
        r = await client.get(
            "/device-protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == str(device_id)
        assert body["revoked"] is False
    finally:
        await _delete_device(dsn, device_id)


async def test_valid_device_via_query_token_returns_row(client):
    """Phase 47 OQ4: EventSource-compatible ?token= fallback works when no
    ``Authorization`` header is present."""
    dsn = await _require_db()
    device_id = await _insert_device(dsn, revoked=False)
    try:
        token = mint_device_jwt(device_id)
        r = await client.get(f"/device-protected?token={token}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == str(device_id)
        assert body["revoked"] is False
    finally:
        await _delete_device(dsn, device_id)


async def test_revoked_device_returns_401_not_403(client):
    dsn = await _require_db()
    device_id = await _insert_device(dsn, revoked=True)
    try:
        token = mint_device_jwt(device_id)
        r = await client.get(
            "/device-protected", headers={"Authorization": f"Bearer {token}"}
        )
        # D-14: revoked MUST be 401, never 403.
        assert r.status_code == 401, r.text
    finally:
        await _delete_device(dsn, device_id)
