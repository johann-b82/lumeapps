"""Integration tests for /api/signage/pair/* — SGN-BE-03.

Covers the 14 test cases enumerated in Plan 42-02:
  POST /request  -> 201, rate limit, DB side-effect
  GET  /status   -> pending / expired / claimed-once / expired-after-drain
  POST /claim    -> admin gate, atomic claim, dash-tolerance, race-free

Uses the project's `client` fixture (httpx.AsyncClient + ASGITransport +
LifespanManager) so startup/shutdown events fire and we exercise the
real app routing graph. Seeds/cleans `signage_*` rows via asyncpg so we
avoid state leakage across tests. Skips cleanly when POSTGRES_* env is
not set so `pytest --collect-only` on a partial tree stays green.
"""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import jwt
import pytest
import pytest_asyncio

from app.config import settings
from app.security.rate_limit import _reset_for_tests as _reset_rate_limit
from tests.test_directus_auth import _mint, ADMIN_UUID, VIEWER_UUID


CODE_RE = re.compile(r"^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{3}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{3}$")
UNDASHED_RE = re.compile(r"^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{6}$")


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
        pytest.skip("POSTGRES_* not set — pair router tests need a live DB")
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
    """Purge all signage-pair state between tests."""
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute("DELETE FROM signage_pairing_sessions")
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_devices")
    finally:
        await conn.close()


async def _count_sessions(dsn: str) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchval("SELECT COUNT(*) FROM signage_pairing_sessions")
    finally:
        await conn.close()


async def _fetch_session_by_id(dsn: str, session_id: uuid.UUID):
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchrow(
            "SELECT id, code, claimed_at, expires_at, device_id FROM signage_pairing_sessions WHERE id = $1",
            session_id,
        )
    finally:
        await conn.close()


async def _insert_pending_session(dsn: str, *, code: str, ttl_s: int = 600) -> uuid.UUID:
    session_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_pairing_sessions (id, code, expires_at) VALUES ($1, $2, $3)",
            session_id,
            code,
            datetime.now(timezone.utc) + timedelta(seconds=ttl_s),
        )
    finally:
        await conn.close()
    return session_id


async def _insert_device(dsn: str) -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status) VALUES ($1, $2, 'pending')",
            device_id,
            f"test-device-{device_id.hex[:6]}",
        )
    finally:
        await conn.close()
    return device_id


@pytest_asyncio.fixture(autouse=True)
async def _reset_state():
    _reset_rate_limit()
    yield
    _reset_rate_limit()


# ---------- POST /api/signage/pair/request ----------


async def test_request_returns_201_with_pairing_code(client):
    dsn = await _require_db()
    try:
        r = await client.post("/api/signage/pair/request")
        assert r.status_code == 201, r.text
        body = r.json()
        assert CODE_RE.match(body["pairing_code"]), body["pairing_code"]
        assert body["expires_in"] == 600
        session_id = uuid.UUID(body["pairing_session_id"])

        # DB-side: row exists, pending, expires ~now+600
        row = await _fetch_session_by_id(dsn, session_id)
        assert row is not None
        assert row["claimed_at"] is None
        assert UNDASHED_RE.match(row["code"])
        delta = (row["expires_at"] - datetime.now(timezone.utc)).total_seconds()
        assert 595 <= delta <= 600
    finally:
        await _cleanup(dsn)


async def test_request_rate_limit_429_on_sixth(client):
    dsn = await _require_db()
    try:
        for i in range(5):
            r = await client.post("/api/signage/pair/request")
            assert r.status_code == 201, f"call {i}: {r.text}"
        r = await client.post("/api/signage/pair/request")
        assert r.status_code == 429, r.text
        assert r.headers.get("retry-after") == "60"
    finally:
        await _cleanup(dsn)


# ---------- GET /api/signage/pair/status ----------


async def test_status_pending_returns_pending(client):
    dsn = await _require_db()
    try:
        session_id = await _insert_pending_session(dsn, code="ABCDEF")
        r = await client.get(
            "/api/signage/pair/status",
            params={"pairing_session_id": str(session_id)},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["device_token"] is None
    finally:
        await _cleanup(dsn)


async def test_status_unknown_id_returns_expired(client):
    await _require_db()
    unknown = uuid.uuid4()
    r = await client.get(
        "/api/signage/pair/status",
        params={"pairing_session_id": str(unknown)},
    )
    # Per RESEARCH §"Open Questions" Q1 — unknown id is 200 expired, not 404.
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "expired"
    assert body["device_token"] is None


async def test_status_expired_ttl_returns_expired(client):
    dsn = await _require_db()
    try:
        session_id = await _insert_pending_session(dsn, code="AAAAAA", ttl_s=-10)
        r = await client.get(
            "/api/signage/pair/status",
            params={"pairing_session_id": str(session_id)},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "expired"
    finally:
        await _cleanup(dsn)


async def test_status_after_claim_delivers_jwt_once(client):
    dsn = await _require_db()
    try:
        # Insert a pending session, then simulate claim by UPDATE'ing claimed_at +
        # device_id directly (we exercise POST /claim separately).
        session_id = await _insert_pending_session(dsn, code="BBBBBB")
        device_id = await _insert_device(dsn)
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await conn.execute(
                "UPDATE signage_pairing_sessions SET claimed_at = now(), device_id = $1 WHERE id = $2",
                device_id,
                session_id,
            )
        finally:
            await conn.close()

        # First poll — delivers JWT, then deletes row.
        r1 = await client.get(
            "/api/signage/pair/status",
            params={"pairing_session_id": str(session_id)},
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["status"] == "claimed"
        assert isinstance(body1["device_token"], str) and body1["device_token"]

        # Decode JWT; scope=device and sub=device_id.
        payload = jwt.decode(
            body1["device_token"],
            settings.SIGNAGE_DEVICE_JWT_SECRET,
            algorithms=["HS256"],
        )
        assert payload["scope"] == "device"
        assert payload["sub"] == str(device_id)

        # Row is gone (delete-on-deliver).
        assert await _fetch_session_by_id(dsn, session_id) is None

        # Second poll — expired (nothing left).
        r2 = await client.get(
            "/api/signage/pair/status",
            params={"pairing_session_id": str(session_id)},
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["status"] == "expired"
        assert body2["device_token"] is None
    finally:
        await _cleanup(dsn)


# ---------- POST /api/signage/pair/claim ----------


async def test_claim_no_auth_returns_401(client):
    await _require_db()
    r = await client.post(
        "/api/signage/pair/claim",
        json={"code": "ABCDEF", "device_name": "lobby-1"},
    )
    assert r.status_code == 401, r.text


async def test_claim_viewer_returns_403(client):
    await _require_db()
    token = _mint(VIEWER_UUID)
    r = await client.post(
        "/api/signage/pair/claim",
        json={"code": "ABCDEF", "device_name": "lobby-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text


async def test_claim_admin_valid_pending_returns_204(client):
    dsn = await _require_db()
    try:
        session_id = await _insert_pending_session(dsn, code="CCCCCC")
        token = _mint(ADMIN_UUID)
        r = await client.post(
            "/api/signage/pair/claim",
            json={"code": "CCCCCC", "device_name": "lobby-1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204, r.text

        # Device row with status="pending" and our name
        conn = await asyncpg.connect(dsn=dsn)
        try:
            devices = await conn.fetch(
                "SELECT id, name, status FROM signage_devices WHERE name = 'lobby-1'"
            )
            assert len(devices) == 1
            device_id = devices[0]["id"]
            assert devices[0]["status"] == "pending"
        finally:
            await conn.close()

        # Session is now claimed and bound.
        row = await _fetch_session_by_id(dsn, session_id)
        assert row is not None
        assert row["claimed_at"] is not None
        assert row["device_id"] == device_id
    finally:
        await _cleanup(dsn)


async def test_claim_already_claimed_returns_404(client):
    dsn = await _require_db()
    try:
        session_id = await _insert_pending_session(dsn, code="DDDDDD")
        token = _mint(ADMIN_UUID)
        r1 = await client.post(
            "/api/signage/pair/claim",
            json={"code": "DDDDDD", "device_name": "dev-a"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 204, r1.text

        r2 = await client.post(
            "/api/signage/pair/claim",
            json={"code": "DDDDDD", "device_name": "dev-b"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 404, r2.text
        detail = r2.json().get("detail", "").lower()
        assert (
            "invalid" in detail or "expired" in detail or "claimed" in detail
        ), detail
    finally:
        await _cleanup(dsn)


async def test_claim_expired_returns_404(client):
    dsn = await _require_db()
    try:
        await _insert_pending_session(dsn, code="EEEEEE", ttl_s=-10)
        token = _mint(ADMIN_UUID)
        r = await client.post(
            "/api/signage/pair/claim",
            json={"code": "EEEEEE", "device_name": "dev-exp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404, r.text

        # No device row should have been left behind.
        conn = await asyncpg.connect(dsn=dsn)
        try:
            n_devices = await conn.fetchval(
                "SELECT COUNT(*) FROM signage_devices WHERE name = 'dev-exp'"
            )
        finally:
            await conn.close()
        assert n_devices == 0
    finally:
        await _cleanup(dsn)


async def test_claim_accepts_dashed_and_undashed(client):
    dsn = await _require_db()
    try:
        # Dashed submission
        await _insert_pending_session(dsn, code="FFFFFF")
        token = _mint(ADMIN_UUID)
        r1 = await client.post(
            "/api/signage/pair/claim",
            json={"code": "FFF-FFF", "device_name": "dashed-ok"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 204, r1.text

        # Undashed submission
        await _insert_pending_session(dsn, code="GGGGGG")
        r2 = await client.post(
            "/api/signage/pair/claim",
            json={"code": "GGGGGG", "device_name": "undashed-ok"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 204, r2.text
    finally:
        await _cleanup(dsn)


async def test_claim_concurrent_exactly_one_wins(client):
    dsn = await _require_db()
    try:
        await _insert_pending_session(dsn, code="HHHHHH")
        token = _mint(ADMIN_UUID)

        # Two in-process admin claims for the same code. Exactly one must win.
        async def _attempt(name: str):
            return await client.post(
                "/api/signage/pair/claim",
                json={"code": "HHHHHH", "device_name": name},
                headers={"Authorization": f"Bearer {token}"},
            )

        results = await asyncio.gather(
            _attempt("racer-a"), _attempt("racer-b"), return_exceptions=False
        )
        statuses = sorted(r.status_code for r in results)
        assert statuses == [204, 404], statuses

        # Only one device row should be present.
        conn = await asyncpg.connect(dsn=dsn)
        try:
            n = await conn.fetchval(
                "SELECT COUNT(*) FROM signage_devices WHERE name IN ('racer-a','racer-b')"
            )
        finally:
            await conn.close()
        assert n == 1
    finally:
        await _cleanup(dsn)
