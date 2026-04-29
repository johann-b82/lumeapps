"""Integration tests for POST /api/signage/pair/devices/{id}/revoke — D-14, ROADMAP SC #5.

Proves end-to-end that after an admin revokes a device, the same JWT that was
minted for it stops working on any protected endpoint guarded by
`get_current_device`.

Cases:
  1. No auth          → 401
  2. Viewer JWT       → 403
  3. Admin + valid id → 204 + DB.revoked_at IS NOT NULL
  4. Admin + unknown  → 404
  5. Admin + already-revoked → 204 + revoked_at preserved (idempotent)
  6. E2E (SC #5):  device JWT → 200 before revoke; revoke; same JWT → 401
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest
import pytest_asyncio
from fastapi import Depends

from app.main import app
from app.security.device_auth import get_current_device
from app.services.signage_pairing import mint_device_jwt
from tests.test_directus_auth import _mint, ADMIN_UUID, VIEWER_UUID


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
        pytest.skip("POSTGRES_* not set — device-revoke tests need a live DB")
    try:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Postgres not reachable ({dsn}): {exc!s}")
    return dsn


async def _cleanup(dsn: str) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute("DELETE FROM signage_pairing_sessions")
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_devices")
    finally:
        await conn.close()


async def _insert_device(dsn: str, *, name: str = "testpi") -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status) VALUES ($1, $2, 'pending')",
            device_id,
            name,
        )
    finally:
        await conn.close()
    return device_id


async def _get_revoked_at(dsn: str, device_id: uuid.UUID) -> datetime | None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchval(
            "SELECT revoked_at FROM signage_devices WHERE id = $1", device_id
        )
    finally:
        await conn.close()


async def _set_revoked_at(dsn: str, device_id: uuid.UUID, when: datetime) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "UPDATE signage_devices SET revoked_at = $1 WHERE id = $2", when, device_id
        )
    finally:
        await conn.close()


# Register a test-only protected route that depends on get_current_device.
# Added once at import time — safe because the ASGI app is module-scoped.
_TEST_ROUTE_PATH = "/_test/me-device"


async def _test_me_device(device=Depends(get_current_device)):
    return {"id": str(device.id), "name": device.name}


def _ensure_test_route_registered() -> None:
    for route in app.routes:
        if getattr(route, "path", None) == _TEST_ROUTE_PATH:
            return
    app.add_api_route(_TEST_ROUTE_PATH, _test_me_device, methods=["GET"])


_ensure_test_route_registered()


@pytest_asyncio.fixture(autouse=True)
async def _purge():
    dsn = _pg_dsn()
    if dsn is not None:
        try:
            await _cleanup(dsn)
        except Exception:
            pass
    yield
    if dsn is not None:
        try:
            await _cleanup(dsn)
        except Exception:
            pass


# ---------- Auth / authz ----------


async def test_revoke_no_auth_returns_401(client):
    await _require_db()
    r = await client.post(f"/api/signage/pair/devices/{uuid.uuid4()}/revoke")
    assert r.status_code == 401, r.text


async def test_revoke_viewer_returns_403(client):
    await _require_db()
    token = _mint(VIEWER_UUID)
    r = await client.post(
        f"/api/signage/pair/devices/{uuid.uuid4()}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text


async def test_revoke_unknown_device_returns_404(client):
    await _require_db()
    token = _mint(ADMIN_UUID)
    r = await client.post(
        f"/api/signage/pair/devices/{uuid.uuid4()}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404, r.text


async def test_revoke_admin_valid_returns_204(client):
    dsn = await _require_db()
    device_id = await _insert_device(dsn)
    assert await _get_revoked_at(dsn, device_id) is None

    token = _mint(ADMIN_UUID)
    r = await client.post(
        f"/api/signage/pair/devices/{device_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204, r.text
    assert await _get_revoked_at(dsn, device_id) is not None


async def test_revoke_already_revoked_is_idempotent(client):
    dsn = await _require_db()
    device_id = await _insert_device(dsn)
    original = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    await _set_revoked_at(dsn, device_id, original)

    token = _mint(ADMIN_UUID)
    r = await client.post(
        f"/api/signage/pair/devices/{device_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204, r.text
    # Timestamp preserved (idempotent no-op).
    assert await _get_revoked_at(dsn, device_id) == original


# ---------- SC #5: end-to-end revoke → get_current_device 401 ----------


async def test_device_jwt_rejected_after_revoke(client):
    """ROADMAP SC #5: a revoked device's JWT is rejected by get_current_device."""
    dsn = await _require_db()
    device_id = await _insert_device(dsn, name="sc5-pi")
    device_jwt = mint_device_jwt(device_id)

    # (a) Pre-revoke — device JWT opens the protected endpoint.
    r_before = await client.get(
        _TEST_ROUTE_PATH, headers={"Authorization": f"Bearer {device_jwt}"}
    )
    assert r_before.status_code == 200, r_before.text
    body = r_before.json()
    assert body["id"] == str(device_id)

    # (b) Admin revokes the device.
    admin_token = _mint(ADMIN_UUID)
    r_revoke = await client.post(
        f"/api/signage/pair/devices/{device_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_revoke.status_code == 204, r_revoke.text
    assert await _get_revoked_at(dsn, device_id) is not None

    # (c) Post-revoke — same JWT is rejected 401, with WWW-Authenticate.
    r_after = await client.get(
        _TEST_ROUTE_PATH, headers={"Authorization": f"Bearer {device_jwt}"}
    )
    assert r_after.status_code == 401, r_after.text
    assert r_after.headers.get("www-authenticate") == "Bearer"
