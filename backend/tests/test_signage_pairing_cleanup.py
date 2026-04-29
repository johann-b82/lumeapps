"""Integration tests for the signage_pairing_cleanup 03:00 UTC cron — SGN-SCH-02.

Covers:
  1. Stale unclaimed row (expires_at = now - 25h)     → deleted
  2. Fresh unclaimed row (expires_at = now - 23h)     → survives (inside 24h grace)
  3. Active unclaimed row (expires_at = now + 10min)  → survives
  4. Stale claimed row (expires_at = now - 25h)       → deleted (predicate is
     expires_at only; claim-state is irrelevant to cleanup)
  5. PAIRING_CLEANUP_JOB_ID constant is exported with the correct value
  6. (smoke) After lifespan(app) startup, scheduler has a cron job registered
     at hour=3 minute=0 UTC under id "signage_pairing_cleanup"

D-13 note: this cron is the carrier for SGN-DB-02's expiration invariant.
Phase 41 dropped `expires_at > now()` from the partial-unique index predicate
(Postgres rejects now() in IMMUTABLE partial predicates, errcode 42P17), so
without this cron expired-but-unclaimed codes would pile up in the unique
index indefinitely.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio

from apscheduler.triggers.cron import CronTrigger


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
        pytest.skip("POSTGRES_* not set — pairing cleanup tests need a live DB")
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


async def _insert_session(
    dsn: str,
    *,
    code: str,
    expires_at: datetime,
    claimed: bool = False,
) -> uuid.UUID:
    session_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        if claimed:
            # Claimed rows: partial-unique index only indexes claimed_at IS NULL,
            # so we can reuse codes freely here.
            await conn.execute(
                "INSERT INTO signage_pairing_sessions (id, code, expires_at, claimed_at) "
                "VALUES ($1, $2, $3, now())",
                session_id,
                code,
                expires_at,
            )
        else:
            await conn.execute(
                "INSERT INTO signage_pairing_sessions (id, code, expires_at) VALUES ($1, $2, $3)",
                session_id,
                code,
                expires_at,
            )
    finally:
        await conn.close()
    return session_id


async def _session_exists(dsn: str, session_id: uuid.UUID) -> bool:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "SELECT 1 FROM signage_pairing_sessions WHERE id = $1", session_id
        )
    finally:
        await conn.close()
    return row is not None


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


async def test_pairing_cleanup_job_id_constant():
    from app.scheduler import PAIRING_CLEANUP_JOB_ID

    assert PAIRING_CLEANUP_JOB_ID == "signage_pairing_cleanup"


# ---------- Cleanup coroutine behavior ----------


async def test_stale_unclaimed_row_is_deleted():
    dsn = await _require_db()
    from app.scheduler import _run_signage_pairing_cleanup

    stale = datetime.now(timezone.utc) - timedelta(hours=25)
    session_id = await _insert_session(dsn, code="STALE1", expires_at=stale)
    assert await _session_exists(dsn, session_id)

    await _run_signage_pairing_cleanup()

    assert not await _session_exists(dsn, session_id)


async def test_fresh_unclaimed_row_within_grace_survives():
    dsn = await _require_db()
    from app.scheduler import _run_signage_pairing_cleanup

    fresh = datetime.now(timezone.utc) - timedelta(hours=23)
    session_id = await _insert_session(dsn, code="GRACE1", expires_at=fresh)

    await _run_signage_pairing_cleanup()

    assert await _session_exists(dsn, session_id)


async def test_active_unclaimed_row_survives():
    dsn = await _require_db()
    from app.scheduler import _run_signage_pairing_cleanup

    active = datetime.now(timezone.utc) + timedelta(minutes=10)
    session_id = await _insert_session(dsn, code="ACTIVE", expires_at=active)

    await _run_signage_pairing_cleanup()

    assert await _session_exists(dsn, session_id)


async def test_stale_claimed_row_is_also_deleted():
    dsn = await _require_db()
    from app.scheduler import _run_signage_pairing_cleanup

    stale = datetime.now(timezone.utc) - timedelta(hours=25)
    session_id = await _insert_session(
        dsn, code="CLAIM1", expires_at=stale, claimed=True
    )
    assert await _session_exists(dsn, session_id)

    await _run_signage_pairing_cleanup()

    # Predicate is expires_at only — claim-state irrelevant.
    assert not await _session_exists(dsn, session_id)


# ---------- Lifespan smoke test ----------


async def test_lifespan_registers_cron_at_0300_utc(client):
    """After lifespan startup, scheduler has our cron pinned to 03:00 UTC."""
    from app.scheduler import PAIRING_CLEANUP_JOB_ID, scheduler

    job = scheduler.get_job(PAIRING_CLEANUP_JOB_ID)
    assert job is not None, "signage_pairing_cleanup job not registered"
    trigger = job.trigger
    assert isinstance(trigger, CronTrigger)
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields.get("hour") == "3", fields
    assert fields.get("minute") == "0", fields
