"""Integration tests for the signage_heartbeat_sweeper 1-min job — SGN-SCH-01.

Covers:
  1. Stale online device (last_seen_at = now - 10m) -> flipped to offline
  2. Fresh device (last_seen_at = now - 1m)          -> untouched
  3. Revoked device, stale                           -> untouched (excluded)
  4. Already-offline device, stale                   -> untouched (idempotent)
  5. HEARTBEAT_SWEEPER_JOB_ID constant exported
  6. Smoke: after lifespan(app) startup, scheduler has interval job at
     1-minute cadence with id "signage_heartbeat_sweeper"

D-10 note: the sweeper observes ``last_seen_at``, which heartbeat writes and
GET /playlist never touches. This is the cross-cutting invariant that keeps
polling kiosks from faking presence.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio


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
        pytest.skip("POSTGRES_* not set — heartbeat sweeper tests need a live DB")
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


async def _insert_heartbeat_event(
    dsn: str, device_id: uuid.UUID, ts: datetime
) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_heartbeat_event (device_id, ts) "
            "VALUES ($1, $2) ON CONFLICT DO NOTHING",
            device_id,
            ts,
        )
    finally:
        await conn.close()


async def _list_event_ts(dsn: str, device_id: uuid.UUID) -> list[datetime]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(
            "SELECT ts FROM signage_heartbeat_event WHERE device_id = $1 "
            "ORDER BY ts",
            device_id,
        )
    finally:
        await conn.close()
    return [r["ts"] for r in rows]


async def _insert_device(
    dsn: str,
    *,
    status: str,
    last_seen_at: datetime | None,
    revoked_at: datetime | None = None,
) -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status, last_seen_at, revoked_at)"
            " VALUES ($1, $2, $3, $4, $5)",
            device_id,
            f"pi-{device_id.hex[:6]}",
            status,
            last_seen_at,
            revoked_at,
        )
    finally:
        await conn.close()
    return device_id


async def _fetch_status(dsn: str, device_id: uuid.UUID) -> str:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        return await conn.fetchval(
            "SELECT status FROM signage_devices WHERE id = $1", device_id
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


# ---------- Constant export ----------


async def test_heartbeat_sweeper_job_id_constant():
    from app.scheduler import HEARTBEAT_SWEEPER_JOB_ID

    assert HEARTBEAT_SWEEPER_JOB_ID == "signage_heartbeat_sweeper"


# ---------- Sweeper coroutine behavior ----------


async def test_sweeper_flips_stale_device_to_offline():
    dsn = await _require_db()
    from app.scheduler import _run_signage_heartbeat_sweeper

    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    device_id = await _insert_device(
        dsn, status="online", last_seen_at=stale, revoked_at=None
    )

    await _run_signage_heartbeat_sweeper()

    assert await _fetch_status(dsn, device_id) == "offline"


async def test_sweeper_ignores_fresh_device():
    dsn = await _require_db()
    from app.scheduler import _run_signage_heartbeat_sweeper

    fresh = datetime.now(timezone.utc) - timedelta(minutes=1)
    device_id = await _insert_device(
        dsn, status="online", last_seen_at=fresh, revoked_at=None
    )

    await _run_signage_heartbeat_sweeper()

    assert await _fetch_status(dsn, device_id) == "online"


async def test_sweeper_ignores_revoked_device():
    dsn = await _require_db()
    from app.scheduler import _run_signage_heartbeat_sweeper

    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    revoked = datetime.now(timezone.utc)
    device_id = await _insert_device(
        dsn, status="online", last_seen_at=stale, revoked_at=revoked
    )

    await _run_signage_heartbeat_sweeper()

    # revoked_at IS NOT NULL -> excluded from the sweep
    assert await _fetch_status(dsn, device_id) == "online"


async def test_sweeper_idempotent_on_already_offline():
    dsn = await _require_db()
    from app.scheduler import _run_signage_heartbeat_sweeper

    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    device_id = await _insert_device(
        dsn, status="offline", last_seen_at=stale, revoked_at=None
    )

    # Should not error and status stays "offline".
    await _run_signage_heartbeat_sweeper()

    assert await _fetch_status(dsn, device_id) == "offline"


# ---------- Lifespan smoke test ----------


async def test_lifespan_registers_sweeper_at_one_minute_interval(client):
    from app.scheduler import HEARTBEAT_SWEEPER_JOB_ID, scheduler

    job = scheduler.get_job(HEARTBEAT_SWEEPER_JOB_ID)
    assert job is not None, "signage_heartbeat_sweeper job not registered"
    # Interval triggers expose the period via trigger.interval (a timedelta).
    interval = job.trigger.interval
    assert interval == timedelta(minutes=1), interval


# ---------- Phase 53 SGN-ANA-01: 25 h event-log prune ----------


async def test_sweeper_prunes_old_heartbeat_events():
    """D-03: rows with ts < now - 25h are removed on every tick."""
    dsn = await _require_db()
    from app.scheduler import _run_signage_heartbeat_sweeper

    device_id = await _insert_device(
        dsn, status="online", last_seen_at=datetime.now(timezone.utc)
    )
    now = datetime.now(timezone.utc)
    await _insert_heartbeat_event(dsn, device_id, now - timedelta(minutes=10))
    await _insert_heartbeat_event(
        dsn, device_id, now - timedelta(hours=24, minutes=30)
    )
    await _insert_heartbeat_event(dsn, device_id, now - timedelta(hours=26))

    await _run_signage_heartbeat_sweeper()

    remaining = await _list_event_ts(dsn, device_id)
    assert len(remaining) == 2
    # Oldest remaining must be within the 25 h window (tolerate a few seconds
    # of jitter between python-side `now` and Postgres-side now()).
    assert min(remaining) >= now - timedelta(hours=25, minutes=1)
