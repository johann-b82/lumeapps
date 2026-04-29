"""Integration tests for POST /api/signage/player/heartbeat event-log insert.

Phase 53 SGN-ANA-01 — proves the heartbeat POST inserts one row into
``signage_heartbeat_event`` per call and is idempotent on
``(device_id, ts)`` collision via ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest
import pytest_asyncio

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
        pytest.skip("POSTGRES_* not set — heartbeat-event tests need a live DB")
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
        await conn.execute("DELETE FROM signage_heartbeat_event")
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_devices")
    finally:
        await conn.close()


async def _insert_device(dsn: str, *, status: str = "online") -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status) VALUES ($1, $2, $3)",
            device_id,
            f"pi-{device_id.hex[:6]}",
            status,
        )
    finally:
        await conn.close()
    return device_id


async def _insert_heartbeat(dsn: str, device_id: uuid.UUID, ts: datetime) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_heartbeat_event (device_id, ts) VALUES ($1, $2) "
            "ON CONFLICT DO NOTHING",
            device_id,
            ts,
        )
    finally:
        await conn.close()


async def _count_events(dsn: str, device_id: uuid.UUID) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM signage_heartbeat_event WHERE device_id = $1",
            device_id,
        )
    finally:
        await conn.close()


async def _last_seen_at(dsn: str, device_id: uuid.UUID):
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchval(
            "SELECT last_seen_at FROM signage_devices WHERE id = $1", device_id
        )
    finally:
        await conn.close()


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


async def test_heartbeat_post_inserts_event_row(client):
    dsn = await _require_db()
    device_id = await _insert_device(dsn)
    token = mint_device_jwt(device_id)

    before = await _count_events(dsn, device_id)
    resp = await client.post(
        "/api/signage/player/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 204, resp.text

    after = await _count_events(dsn, device_id)
    assert after == before + 1
    # Existing behaviour preserved: last_seen_at updated.
    assert await _last_seen_at(dsn, device_id) is not None


async def test_heartbeat_post_is_idempotent_on_same_microsecond(
    client, monkeypatch
):
    """Two writes to (device_id, ts) — the handler's INSERT must not 5xx.

    Strategy: pre-seed a row at a fixed timestamp, then monkeypatch
    ``datetime.now`` inside the router module so the handler's INSERT
    collides on the composite PK. ON CONFLICT DO NOTHING swallows it.
    """
    dsn = await _require_db()
    device_id = await _insert_device(dsn)
    token = mint_device_jwt(device_id)

    fixed = datetime(2026, 4, 21, 12, 0, 0, 0, tzinfo=timezone.utc)
    await _insert_heartbeat(dsn, device_id, fixed)

    import app.routers.signage_player as player_module

    class _FakeDT:
        @staticmethod
        def now(tz=None):  # noqa: D401 — shim
            return fixed

    monkeypatch.setattr(player_module, "datetime", _FakeDT)

    resp = await client.post(
        "/api/signage/player/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 204, resp.text

    # Exactly one row at that ts — ON CONFLICT DO NOTHING did its job.
    conn = await asyncpg.connect(dsn=dsn)
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM signage_heartbeat_event "
            "WHERE device_id = $1 AND ts = $2",
            device_id,
            fixed,
        )
    finally:
        await conn.close()
    assert count == 1
