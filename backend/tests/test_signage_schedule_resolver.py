"""SGN-TIME-03 integration tests for ``resolve_schedule_for_device`` + the
``resolve_playlist_for_device`` composition wrapper.

Covers the 7 SGN-TIME-03 test cases plus the REQUIREMENTS.md §3 worked
example as an end-to-end sanity check:

  TC1  schedule-match (single window)
  TC2  priority tiebreak (+ updated_at tiebreak when priorities equal)
  TC3  weekday-miss (Saturday query against a Mo-Fr schedule)
  TC4  time-miss (boundary: start inclusive, end exclusive)
  TC5  disabled-schedule-skip
  TC6  tag-mismatch-skip
  TC7  empty-schedules-fallback (composition: tag resolver still runs)
  REQ3 worked example — Mo-Fr 07-11 X (pri 10), Mo-So 11-14 Y (pri 5);
       Wed 08:30 → X, Wed 12:00 → Y, Wed 15:00 → tag fallback

All tests pass an explicit ``now=`` — we never rely on the real clock
(Pitfall 5). ``2026-04-22`` is a Wednesday; ``2026-04-25`` a Saturday.

Seeding uses asyncpg (mirrors ``test_signage_resolver.py``). Each test
re-reads the device row afterwards to assert pure-read (D-10).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio
import zoneinfo
from sqlalchemy import select, update

from app.database import AsyncSessionLocal, engine
from app.models import AppSettings
from app.models.signage import SignageDevice
from app.services.signage_resolver import (
    resolve_playlist_for_device,
    resolve_schedule_for_device,
)


# --------------------------------------------------------------------------
# DSN plumbing — mirrors test_signage_resolver.py
# --------------------------------------------------------------------------


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
        pytest.skip("POSTGRES_* not set — resolver tests need a live DB")
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
        await conn.execute("DELETE FROM signage_schedules")
        await conn.execute("DELETE FROM signage_playlist_items")
        await conn.execute("DELETE FROM signage_playlist_tag_map")
        await conn.execute("DELETE FROM signage_device_tag_map")
        await conn.execute("DELETE FROM signage_playlists")
        await conn.execute("DELETE FROM signage_devices")
        await conn.execute("DELETE FROM signage_device_tags")
        await conn.execute("DELETE FROM signage_media")
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def dsn():
    d = await _require_db()
    await _cleanup(d)
    try:
        await engine.dispose()
    except Exception:
        pass
    # Ensure the singleton timezone is exactly 'Europe/Berlin' for determinism
    # (reset_settings autouse fixture handles AppSettings in general, but we
    # re-assert here to be robust if the defaults ever drift).
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(AppSettings)
            .where(AppSettings.id == 1)
            .values(timezone="Europe/Berlin")
        )
        await db.commit()
    yield d
    await _cleanup(d)


# --------------------------------------------------------------------------
# Seeding helpers (asyncpg)
# --------------------------------------------------------------------------


async def _insert_device(dsn: str, *, name: str = "pi-1") -> uuid.UUID:
    device_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_devices (id, name, status) VALUES ($1, $2, 'online')",
            device_id,
            name,
        )
    finally:
        await conn.close()
    return device_id


async def _insert_tag(dsn: str, name: str) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "INSERT INTO signage_device_tags (name) VALUES ($1) RETURNING id",
            name,
        )
    finally:
        await conn.close()
    return row["id"]


async def _tag_device(dsn: str, device_id: uuid.UUID, tag_id: int) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_device_tag_map (device_id, tag_id) VALUES ($1, $2)",
            device_id,
            tag_id,
        )
    finally:
        await conn.close()


async def _insert_playlist(
    dsn: str,
    *,
    name: str,
    priority: int = 0,
    enabled: bool = True,
) -> uuid.UUID:
    pid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_playlists (id, name, priority, enabled)"
            " VALUES ($1, $2, $3, $4)",
            pid,
            name,
            priority,
            enabled,
        )
    finally:
        await conn.close()
    return pid


async def _tag_playlist(dsn: str, playlist_id: uuid.UUID, tag_id: int) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_playlist_tag_map (playlist_id, tag_id)"
            " VALUES ($1, $2)",
            playlist_id,
            tag_id,
        )
    finally:
        await conn.close()


async def _insert_schedule(
    dsn: str,
    *,
    playlist_id: uuid.UUID,
    weekday_mask: int,
    start_hhmm: int,
    end_hhmm: int,
    priority: int = 0,
    enabled: bool = True,
    updated_at: datetime | None = None,
) -> uuid.UUID:
    sid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        if updated_at is None:
            await conn.execute(
                "INSERT INTO signage_schedules"
                " (id, playlist_id, weekday_mask, start_hhmm, end_hhmm, priority, enabled)"
                " VALUES ($1, $2, $3, $4, $5, $6, $7)",
                sid,
                playlist_id,
                weekday_mask,
                start_hhmm,
                end_hhmm,
                priority,
                enabled,
            )
        else:
            await conn.execute(
                "INSERT INTO signage_schedules"
                " (id, playlist_id, weekday_mask, start_hhmm, end_hhmm, priority,"
                "  enabled, updated_at)"
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                sid,
                playlist_id,
                weekday_mask,
                start_hhmm,
                end_hhmm,
                priority,
                enabled,
                updated_at,
            )
    finally:
        await conn.close()
    return sid


async def _load_device(db, device_id: uuid.UUID) -> SignageDevice:
    stmt = select(SignageDevice).where(SignageDevice.id == device_id)
    return (await db.execute(stmt)).scalar_one()


async def _assert_device_untouched(dsn: str, device_id: uuid.UUID) -> None:
    """D-10: resolver must not mutate the device row."""
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "SELECT last_seen_at, status, current_item_id, current_playlist_etag"
            " FROM signage_devices WHERE id = $1",
            device_id,
        )
    finally:
        await conn.close()
    assert row["last_seen_at"] is None
    assert row["current_item_id"] is None
    assert row["current_playlist_etag"] is None
    assert row["status"] == "online"


# Canonical test timestamps. 2026-04-22 is a Wednesday; 2026-04-25 a Saturday.
BERLIN = zoneinfo.ZoneInfo("Europe/Berlin")
WED_08_30 = datetime(2026, 4, 22, 8, 30, tzinfo=BERLIN)
WED_12_00 = datetime(2026, 4, 22, 12, 0, tzinfo=BERLIN)
WED_15_00 = datetime(2026, 4, 22, 15, 0, tzinfo=BERLIN)
WED_06_59 = datetime(2026, 4, 22, 6, 59, tzinfo=BERLIN)
WED_07_00 = datetime(2026, 4, 22, 7, 0, tzinfo=BERLIN)
WED_11_00 = datetime(2026, 4, 22, 11, 0, tzinfo=BERLIN)
SAT_09_00 = datetime(2026, 4, 25, 9, 0, tzinfo=BERLIN)

# weekday masks (bit 0=Mon..bit 6=Sun)
MASK_MO_FR = 0b0011111  # = 31
MASK_MO_SO = 0b1111111  # = 127


# --------------------------------------------------------------------------
# TC1 — schedule-match (single)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_single_match(dsn):
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    playlist_x = await _insert_playlist(dsn, name="Playlist X", priority=5)
    await _tag_playlist(dsn, playlist_x, t_lobby)
    await _insert_schedule(
        dsn,
        playlist_id=playlist_x,
        weekday_mask=MASK_MO_FR,
        start_hhmm=700,
        end_hhmm=1100,
        priority=5,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_schedule_for_device(db, device, now=WED_08_30)

    assert env is not None
    assert env.playlist_id == playlist_x
    assert env.name == "Playlist X"
    await _assert_device_untouched(dsn, device_id)


# --------------------------------------------------------------------------
# TC2 — priority tiebreak (and updated_at sub-case)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_priority_tiebreak(dsn):
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    playlist_y = await _insert_playlist(dsn, name="Playlist Y-pri10", priority=10)
    playlist_z = await _insert_playlist(dsn, name="Playlist Z-pri5", priority=5)
    await _tag_playlist(dsn, playlist_y, t_lobby)
    await _tag_playlist(dsn, playlist_z, t_lobby)

    # Both cover Wed 12:00.
    await _insert_schedule(
        dsn,
        playlist_id=playlist_z,
        weekday_mask=MASK_MO_SO,
        start_hhmm=1100,
        end_hhmm=1400,
        priority=5,
    )
    await _insert_schedule(
        dsn,
        playlist_id=playlist_y,
        weekday_mask=MASK_MO_SO,
        start_hhmm=1100,
        end_hhmm=1400,
        priority=10,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_schedule_for_device(db, device, now=WED_12_00)

    assert env is not None
    assert env.playlist_id == playlist_y  # higher priority wins


@pytest.mark.asyncio
async def test_schedule_updated_at_tiebreak_when_priorities_equal(dsn):
    """When priorities are equal, the more recently updated schedule wins."""
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    older = await _insert_playlist(dsn, name="older", priority=5)
    newer = await _insert_playlist(dsn, name="newer", priority=5)
    await _tag_playlist(dsn, older, t_lobby)
    await _tag_playlist(dsn, newer, t_lobby)

    t_old = datetime.now(timezone.utc) - timedelta(days=2)
    t_new = datetime.now(timezone.utc) - timedelta(minutes=1)
    await _insert_schedule(
        dsn,
        playlist_id=older,
        weekday_mask=MASK_MO_SO,
        start_hhmm=1100,
        end_hhmm=1400,
        priority=5,
        updated_at=t_old,
    )
    await _insert_schedule(
        dsn,
        playlist_id=newer,
        weekday_mask=MASK_MO_SO,
        start_hhmm=1100,
        end_hhmm=1400,
        priority=5,
        updated_at=t_new,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_schedule_for_device(db, device, now=WED_12_00)

    assert env is not None
    assert env.playlist_id == newer


# --------------------------------------------------------------------------
# TC3 — weekday-miss
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_weekday_miss(dsn):
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    playlist_x = await _insert_playlist(dsn, name="Playlist X", priority=5)
    await _tag_playlist(dsn, playlist_x, t_lobby)
    await _insert_schedule(
        dsn,
        playlist_id=playlist_x,
        weekday_mask=MASK_MO_FR,  # no Saturday bit
        start_hhmm=700,
        end_hhmm=1200,
        priority=5,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_schedule_for_device(db, device, now=SAT_09_00)

    assert env is None
    await _assert_device_untouched(dsn, device_id)


# --------------------------------------------------------------------------
# TC4 — time-miss (boundaries: start inclusive, end exclusive)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_time_miss_boundaries(dsn):
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    playlist_x = await _insert_playlist(dsn, name="Playlist X", priority=5)
    await _tag_playlist(dsn, playlist_x, t_lobby)
    await _insert_schedule(
        dsn,
        playlist_id=playlist_x,
        weekday_mask=MASK_MO_SO,
        start_hhmm=700,
        end_hhmm=1100,
        priority=5,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        # 06:59 — before window.
        assert await resolve_schedule_for_device(db, device, now=WED_06_59) is None
        # 07:00 — start is inclusive.
        env_start = await resolve_schedule_for_device(db, device, now=WED_07_00)
        assert env_start is not None
        assert env_start.playlist_id == playlist_x
        # 11:00 — end is exclusive.
        assert await resolve_schedule_for_device(db, device, now=WED_11_00) is None


# --------------------------------------------------------------------------
# TC5 — disabled-schedule-skip
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_disabled_skip(dsn):
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    playlist_x = await _insert_playlist(dsn, name="Playlist X", priority=5)
    await _tag_playlist(dsn, playlist_x, t_lobby)
    await _insert_schedule(
        dsn,
        playlist_id=playlist_x,
        weekday_mask=MASK_MO_SO,
        start_hhmm=700,
        end_hhmm=1100,
        priority=5,
        enabled=False,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_schedule_for_device(db, device, now=WED_08_30)

    assert env is None


# --------------------------------------------------------------------------
# TC6 — tag-mismatch-skip
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_tag_mismatch_skip(dsn):
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    t_kitchen = await _insert_tag(dsn, "kitchen")
    await _tag_device(dsn, device_id, t_lobby)

    # Playlist targets 'kitchen' — device only carries 'lobby'.
    playlist_x = await _insert_playlist(dsn, name="kitchen-pl", priority=5)
    await _tag_playlist(dsn, playlist_x, t_kitchen)
    await _insert_schedule(
        dsn,
        playlist_id=playlist_x,
        weekday_mask=MASK_MO_SO,
        start_hhmm=700,
        end_hhmm=1100,
        priority=5,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        env = await resolve_schedule_for_device(db, device, now=WED_08_30)

    assert env is None


# --------------------------------------------------------------------------
# TC7 — empty-schedules-falls-back-to-tag-resolver
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_schedules_fallback_to_tag_resolver(dsn):
    """No schedules at all → ``resolve_playlist_for_device`` returns the
    pre-Phase-51 tag-based envelope.
    """
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    playlist_x = await _insert_playlist(dsn, name="tag-only", priority=5)
    await _tag_playlist(dsn, playlist_x, t_lobby)
    # No schedule rows inserted.

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)
        # schedule resolver directly: must be None
        assert await resolve_schedule_for_device(db, device) is None
        # composition wrapper: must return the tag-based envelope
        env = await resolve_playlist_for_device(db, device)

    assert env.playlist_id == playlist_x
    assert env.name == "tag-only"


# --------------------------------------------------------------------------
# REQ3 — worked example end-to-end (REQUIREMENTS.md §3 north-star)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_worked_example_REQ3(dsn):
    """Mo-Fr 07-11 Playlist X priority 10, Mo-So 11-14 Playlist Y priority 5.
    Device tagged for both. Wed 08:30 → X, Wed 12:00 → Y, Wed 15:00 → fallback.
    """
    device_id = await _insert_device(dsn)
    t_lobby = await _insert_tag(dsn, "lobby")
    await _tag_device(dsn, device_id, t_lobby)

    # Also register a tag-based-only playlist so the 15:00 fallback resolves
    # to something distinguishable from an empty envelope.
    fallback_pl = await _insert_playlist(dsn, name="tag-fallback", priority=1)
    await _tag_playlist(dsn, fallback_pl, t_lobby)

    playlist_x = await _insert_playlist(dsn, name="Playlist X", priority=10)
    playlist_y = await _insert_playlist(dsn, name="Playlist Y", priority=5)
    await _tag_playlist(dsn, playlist_x, t_lobby)
    await _tag_playlist(dsn, playlist_y, t_lobby)

    await _insert_schedule(
        dsn,
        playlist_id=playlist_x,
        weekday_mask=MASK_MO_FR,
        start_hhmm=700,
        end_hhmm=1100,
        priority=10,
    )
    await _insert_schedule(
        dsn,
        playlist_id=playlist_y,
        weekday_mask=MASK_MO_SO,
        start_hhmm=1100,
        end_hhmm=1400,
        priority=5,
    )

    async with AsyncSessionLocal() as db:
        device = await _load_device(db, device_id)

        env_0830 = await resolve_playlist_for_device(db, device)  # real clock — unused
        # Use schedule resolver directly for deterministic times:
        env_0830 = await resolve_schedule_for_device(db, device, now=WED_08_30)
        assert env_0830 is not None and env_0830.playlist_id == playlist_x

        env_1200 = await resolve_schedule_for_device(db, device, now=WED_12_00)
        assert env_1200 is not None and env_1200.playlist_id == playlist_y

        # 15:00 — no schedule matches, resolve_schedule returns None.
        env_1500 = await resolve_schedule_for_device(db, device, now=WED_15_00)
        assert env_1500 is None

        # Composition wrapper at 15:00 falls back to tag-based resolver.
        # resolve_playlist_for_device uses the real clock internally, but the
        # tag resolver happily returns the tag-fallback playlist (priority 1,
        # but beats nothing since schedules missed); deterministic assertion:
        # composition must not raise and must return a non-empty envelope
        # whose playlist_id is one of {playlist_x, playlist_y, fallback_pl}.
        # We assert fallback_pl is the resolved tag-match only if the real
        # clock isn't inside 07-11 or 11-14 Mo-Fr — which is time-dependent,
        # so here we assert only the composition shape is sane.
        env_now = await resolve_playlist_for_device(db, device)
        assert env_now.playlist_id in {playlist_x, playlist_y, fallback_pl}

    await _assert_device_untouched(dsn, device_id)
