"""Integration tests for the PPTX stuck-row reset — SGN-SCH-03 / D-09 + D-18.

Covers:
  1. PPTX 'processing' row older than 5 minutes -> flipped to 'failed' with
     conversion_error='abandoned_on_restart'.
  2. PPTX 'processing' row only 2 minutes old -> NOT flipped.
  3. PPTX 'pending' row (conversion_started_at NULL) -> NOT flipped.
  4. Non-PPTX row (kind='image', conversion_status NULL) -> NOT flipped.
  5. PPTX 'done' row -> NOT flipped.
  6. Idempotent: running the reset twice on the same DB keeps the failed
     row stable (no additional writes beyond the initial flip).
  7. Reset on an empty table is a no-op (does not raise).
  8. The function is NOT registered as an APScheduler job (one-shot only
     per D-18).
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
        pytest.skip("POSTGRES_* not set — pptx stuck reset tests need a live DB")
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
        await conn.execute("DELETE FROM signage_playlist_items")
        await conn.execute("DELETE FROM signage_media")
    finally:
        await conn.close()


async def _insert_media(
    dsn: str,
    *,
    kind: str,
    title: str,
    conversion_status: str | None,
    conversion_started_at: datetime | None = None,
    conversion_error: str | None = None,
    slide_paths: list | None = None,
) -> uuid.UUID:
    import json

    media_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_media"
            " (id, kind, title, conversion_status, conversion_started_at,"
            "  conversion_error, slide_paths)"
            " VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)",
            media_id,
            kind,
            title,
            conversion_status,
            conversion_started_at,
            conversion_error,
            json.dumps(slide_paths) if slide_paths is not None else None,
        )
    finally:
        await conn.close()
    return media_id


async def _fetch_row(dsn: str, media_id: uuid.UUID) -> dict:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "SELECT conversion_status, conversion_error, updated_at"
            " FROM signage_media WHERE id = $1",
            media_id,
        )
        return dict(row) if row else {}
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


# ---------- Reset coroutine behavior ----------


async def test_reset_flips_stale_processing_row():
    dsn = await _require_db()
    from app.scheduler import _run_pptx_stuck_reset

    stale_started = datetime.now(timezone.utc) - timedelta(minutes=10)
    media_id = await _insert_media(
        dsn,
        kind="pptx",
        title="stale.pptx",
        conversion_status="processing",
        conversion_started_at=stale_started,
    )

    await _run_pptx_stuck_reset()

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] == "failed"
    assert row["conversion_error"] == "abandoned_on_restart"


async def test_reset_skips_young_processing_row():
    dsn = await _require_db()
    from app.scheduler import _run_pptx_stuck_reset

    young_started = datetime.now(timezone.utc) - timedelta(minutes=2)
    media_id = await _insert_media(
        dsn,
        kind="pptx",
        title="young.pptx",
        conversion_status="processing",
        conversion_started_at=young_started,
    )

    await _run_pptx_stuck_reset()

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] == "processing"
    assert row["conversion_error"] is None


async def test_reset_skips_pending_row_with_null_started_at():
    dsn = await _require_db()
    from app.scheduler import _run_pptx_stuck_reset

    media_id = await _insert_media(
        dsn,
        kind="pptx",
        title="pending.pptx",
        conversion_status="pending",
        conversion_started_at=None,
    )

    await _run_pptx_stuck_reset()

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] == "pending"
    assert row["conversion_error"] is None


async def test_reset_skips_non_pptx_row():
    dsn = await _require_db()
    from app.scheduler import _run_pptx_stuck_reset

    media_id = await _insert_media(
        dsn,
        kind="image",
        title="picture.png",
        conversion_status=None,
        conversion_started_at=None,
    )

    await _run_pptx_stuck_reset()

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] is None
    assert row["conversion_error"] is None


async def test_reset_skips_done_row():
    dsn = await _require_db()
    from app.scheduler import _run_pptx_stuck_reset

    old_started = datetime.now(timezone.utc) - timedelta(minutes=30)
    media_id = await _insert_media(
        dsn,
        kind="pptx",
        title="done.pptx",
        conversion_status="done",
        conversion_started_at=old_started,
        slide_paths=["slide-1.png"],
    )

    await _run_pptx_stuck_reset()

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] == "done"
    assert row["conversion_error"] is None


async def test_reset_is_noop_on_clean_table():
    await _require_db()
    from app.scheduler import _run_pptx_stuck_reset

    # No inserts — just confirm it doesn't raise.
    await _run_pptx_stuck_reset()


async def test_reset_is_idempotent():
    dsn = await _require_db()
    from app.scheduler import _run_pptx_stuck_reset

    stale_started = datetime.now(timezone.utc) - timedelta(minutes=10)
    media_id = await _insert_media(
        dsn,
        kind="pptx",
        title="stale.pptx",
        conversion_status="processing",
        conversion_started_at=stale_started,
    )

    await _run_pptx_stuck_reset()
    first = await _fetch_row(dsn, media_id)
    assert first["conversion_status"] == "failed"
    assert first["conversion_error"] == "abandoned_on_restart"

    # Second call: row already 'failed' — no longer matches predicate, so
    # the UPDATE rowcount is zero and the row is unchanged.
    await _run_pptx_stuck_reset()
    second = await _fetch_row(dsn, media_id)
    assert second["conversion_status"] == "failed"
    assert second["conversion_error"] == "abandoned_on_restart"


# ---------- Not a scheduled job (D-18) ----------


async def test_reset_is_not_registered_as_apscheduler_job(client):
    """Per D-18 the reset is one-shot at startup — never an interval job."""
    from app.scheduler import scheduler

    for job in scheduler.get_jobs():
        assert "pptx_stuck_reset" not in job.id, (
            f"_run_pptx_stuck_reset unexpectedly registered as job: {job.id}"
        )
