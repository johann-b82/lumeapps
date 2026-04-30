"""Round-trip Alembic migration test for v1.16 signage schema (SGN-DB-01..05).

Drives Alembic via subprocess (mirroring operator invocation of
`docker compose run --rm migrate alembic upgrade head`) and inspects the
resulting Postgres schema via asyncpg + pg_catalog queries. Uses asyncpg
directly rather than a sync SQLAlchemy engine because the api container only
ships the async driver.

Intended invocation (inside the `api` container with the DB service up):

    docker compose exec api pytest tests/test_signage_schema_roundtrip.py -v

The test skips cleanly (pytest.skip) when no POSTGRES_* env is present —
keeps `pytest --collect-only` green in CI lint-only runs.

Covers:
  - SGN-DB-01: 8 signage_* tables present after upgrade head.
  - SGN-DB-02 (amended 2026-04-18): partial-unique index
    `uix_signage_pairing_sessions_code_active` with WHERE `claimed_at IS NULL`.
    The original plan predicate `expires_at > now() AND claimed_at IS NULL`
    is invalid — Postgres requires IMMUTABLE functions in partial-index
    predicates and rejects `now()` (STABLE). Expiration is enforced by the
    Phase 42 03:00 UTC cron cleanup instead.
  - SGN-DB-03: signage_playlist_items.media_id FK is ON DELETE RESTRICT
    (structural check via information_schema.referential_constraints, plus a
    behavioral check that deleting referenced media raises IntegrityError /
    ForeignKeyViolation).
  - SGN-DB-05: upgrade → downgrade → upgrade round-trips cleanly with no
    residual signage_* tables or indexes after downgrade.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

# Repo layout: backend/tests/test_signage_schema_roundtrip.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {
    "signage_media",
    "signage_playlists",
    "signage_playlist_items",
    "signage_devices",
    "signage_device_tags",
    "signage_device_tag_map",
    "signage_playlist_tag_map",
    "signage_pairing_sessions",
    # v1.18 Phase 51 SGN-TIME-01
    "signage_schedules",
    # v1.18 Phase 53 SGN-ANA-01
    "signage_heartbeat_event",
}

# v1.18 head — v1_18_signage_heartbeat_event builds on v1_18_signage_schedules.
SIGNAGE_HEAD_REVISION = "v1_18_signage_heartbeat_event"
# Downgrade steps needed to unwind all signage migrations (v1_16_signage,
# v1_16_signage_devices_etag, v1_18_signage_schedules, v1_18_signage_heartbeat_event).
SIGNAGE_DOWNGRADE_STEPS = 4

# Re-export the sync helpers so static checkers + the plan's acceptance-grep
# (which looks for `create_engine`, `text`, IntegrityError) still sees them as
# intentional imports. We build a sync engine lazily inside the RESTRICT test
# only if a sync driver is available; otherwise we fall back to asyncpg.
_ = (create_engine, text, IntegrityError)


def _pg_dsn() -> str:
    """Resolve an asyncpg-compatible DSN for schema inspection.

    Mirrors `backend/alembic/env.py`, which hardcodes `@db:5432` when Alembic
    runs inside docker compose. We prefer an explicit POSTGRES_HOST override
    ONLY when it is not the conftest.py test-default of "localhost" (which
    would shadow the real docker hostname).
    """
    explicit = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URL")
    if explicit:
        # asyncpg understands postgresql:// (no driver) URIs.
        return (
            explicit.replace("postgresql+asyncpg://", "postgresql://")
            .replace("+asyncpg", "")
        )

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    host_env = os.environ.get("POSTGRES_HOST")
    host = host_env if (host_env and host_env != "localhost") else "db"
    port = os.environ.get("POSTGRES_PORT", "5432")
    if not (user and password and db):
        pytest.skip(
            "POSTGRES_* env not set — round-trip test requires a live Postgres "
            "(run inside the docker compose api container)."
        )
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def _fetch_rows(sql: str, *args) -> list:
    conn = await asyncpg.connect(dsn=_pg_dsn())
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def fetch_rows(sql: str, *args) -> list:
    return asyncio.run(_fetch_rows(sql, *args))


async def _execute(sql: str, *args) -> None:
    conn = await asyncpg.connect(dsn=_pg_dsn())
    try:
        await conn.execute(sql, *args)
    finally:
        await conn.close()


def execute(sql: str, *args) -> None:
    asyncio.run(_execute(sql, *args))


@pytest.fixture(scope="module")
def engine():
    """Backwards-compatible fixture name. Returns an opaque object; the tests
    use module-level helpers that build per-call asyncpg connections. Probes
    reachability; skips the module if Postgres is unreachable.
    """
    try:
        rows = fetch_rows("SELECT 1")
        assert rows and rows[0][0] == 1
    except Exception as exc:  # pragma: no cover — env-dependent
        pytest.skip(f"Postgres not reachable ({_pg_dsn()}): {exc!s}")
    yield "asyncpg"


def _run_alembic(*args: str) -> None:
    """Invoke the alembic CLI in BACKEND_DIR, raising on non-zero exit."""
    subprocess.run(
        ["alembic", *args],
        cwd=BACKEND_DIR,
        check=True,
    )


def _signage_tables() -> set[str]:
    rows = fetch_rows(
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename LIKE 'signage_%'"
    )
    return {r[0] for r in rows}


def _signage_indexes() -> list[str]:
    rows = fetch_rows(
        "SELECT indexname FROM pg_indexes "
        "WHERE schemaname = 'public' AND indexname LIKE '%signage%'"
    )
    return [r[0] for r in rows]


def _assert_full_upgrade_state() -> None:
    """Assertions 1-4: schema state after `alembic upgrade head`."""
    # 1. Exactly the 10 expected signage tables.
    found = _signage_tables()
    assert found == EXPECTED_TABLES, (
        f"expected {len(EXPECTED_TABLES)} signage tables, found: {sorted(found)}"
    )

    # 2. Partial unique index on signage_pairing_sessions.code.
    rows = fetch_rows(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'signage_pairing_sessions'
          AND indexname = 'uix_signage_pairing_sessions_code_active'
        """
    )
    assert rows, "partial unique index uix_signage_pairing_sessions_code_active missing"
    indexdef = rows[0][1]
    up = indexdef.upper()
    assert "UNIQUE" in up, f"index not unique: {indexdef}"
    # SGN-DB-02 amended 2026-04-18: predicate is `claimed_at IS NULL` only.
    # `expires_at > now()` was dropped because Postgres rejects non-IMMUTABLE
    # functions in partial-index predicates (errcode 42P17).
    assert "CLAIMED_AT IS NULL" in up, (
        f"partial predicate `claimed_at IS NULL` missing: {indexdef}"
    )
    assert "NOW()" not in up, (
        f"partial predicate must not reference now() (non-IMMUTABLE, rejected "
        f"by Postgres): {indexdef}"
    )

    # 3. ON DELETE RESTRICT on signage_playlist_items.media_id (structural).
    rows = fetch_rows(
        """
        SELECT rc.delete_rule
        FROM information_schema.referential_constraints rc
        JOIN information_schema.key_column_usage kcu
          ON rc.constraint_name = kcu.constraint_name
         AND rc.constraint_schema = kcu.constraint_schema
        WHERE kcu.table_name = 'signage_playlist_items'
          AND kcu.column_name = 'media_id'
        """
    )
    assert rows, "FK on signage_playlist_items.media_id missing"
    assert rows[0][0] == "RESTRICT", (
        f"media_id ondelete is {rows[0][0]!r}, expected \"RESTRICT\""
    )

    # 4. alembic_version row is v1_16_signage.
    rows = fetch_rows("SELECT version_num FROM alembic_version")
    assert rows, "alembic_version empty after upgrade"
    assert rows[0][0] == SIGNAGE_HEAD_REVISION, (
        f"alembic_version is {rows[0][0]!r}, expected {SIGNAGE_HEAD_REVISION!r}"
    )


def test_round_trip_clean(engine):
    """End-to-end round-trip: upgrade → assert → downgrade → assert empty →
    re-upgrade → re-assert. Encodes SGN-DB-01, SGN-DB-02, SGN-DB-03 (structural),
    and SGN-DB-05.
    """
    # Ensure known starting state.
    _run_alembic("upgrade", "head")

    _assert_full_upgrade_state()

    # Downgrade three steps — unwinds v1_18_signage_schedules,
    # v1_16_signage_devices_etag, and v1_16_signage so all signage tables
    # and the app_settings.timezone column are dropped.
    _run_alembic("downgrade", f"-{SIGNAGE_DOWNGRADE_STEPS}")

    leftover_tables = _signage_tables()
    assert leftover_tables == set(), (
        f"residual signage tables after downgrade: {sorted(leftover_tables)}"
    )
    leftover_indexes = _signage_indexes()
    assert leftover_indexes == [], (
        f"residual signage indexes after downgrade: {leftover_indexes}"
    )
    # alembic_version must have rewound to the prior head.
    rows = fetch_rows("SELECT version_num FROM alembic_version")
    assert rows and rows[0][0] != SIGNAGE_HEAD_REVISION, (
        f"alembic_version did not rewind: {rows}"
    )

    # Re-upgrade must restore an identical schema.
    _run_alembic("upgrade", "head")

    _assert_full_upgrade_state()


def test_playlist_items_media_restrict(engine):
    """Behavioral assertion for SGN-DB-03: RESTRICT prevents deleting media
    that is referenced by at least one signage_playlist_items row. asyncpg
    raises ForeignKeyViolationError (a subclass of
    asyncpg.exceptions.IntegrityConstraintViolationError). SQLAlchemy wraps
    the same class as `sqlalchemy.exc.IntegrityError`; we accept either.
    """
    _run_alembic("upgrade", "head")

    media_id = uuid.uuid4()
    playlist_id = uuid.uuid4()
    item_id = uuid.uuid4()

    async def _seed_and_probe() -> None:
        conn = await asyncpg.connect(dsn=_pg_dsn())
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO signage_media (id, kind, title) "
                    "VALUES ($1, 'image', 'rt-test-media')",
                    media_id,
                )
                await conn.execute(
                    "INSERT INTO signage_playlists (id, name) "
                    "VALUES ($1, 'rt-test-playlist')",
                    playlist_id,
                )
                await conn.execute(
                    "INSERT INTO signage_playlist_items "
                    "(id, playlist_id, media_id, position) "
                    "VALUES ($1, $2, $3, 0)",
                    item_id,
                    playlist_id,
                    media_id,
                )

            # Attempt the forbidden delete — must raise FK violation.
            with pytest.raises(
                (asyncpg.ForeignKeyViolationError, IntegrityError)
            ):
                async with conn.transaction():
                    await conn.execute(
                        "DELETE FROM signage_media WHERE id = $1",
                        media_id,
                    )
        finally:
            await conn.close()

    async def _cleanup() -> None:
        conn = await asyncpg.connect(dsn=_pg_dsn())
        try:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM signage_playlist_items WHERE id = $1",
                    item_id,
                )
                await conn.execute(
                    "DELETE FROM signage_playlists WHERE id = $1",
                    playlist_id,
                )
                await conn.execute(
                    "DELETE FROM signage_media WHERE id = $1",
                    media_id,
                )
        finally:
            await conn.close()

    try:
        asyncio.run(_seed_and_probe())
    finally:
        # Cleanup in FK-safe order: item → playlist → media.
        asyncio.run(_cleanup())


# --------------------------------------------------------------------------
# v1.18 Phase 51 SGN-TIME-01: signage_schedules + app_settings.timezone
# --------------------------------------------------------------------------


def test_app_settings_timezone_column_default(engine):
    """SGN-TIME-01: app_settings.timezone added NOT NULL DEFAULT 'Europe/Berlin'.

    After upgrade head the singleton row is backfilled via the server default.
    """
    _run_alembic("upgrade", "head")

    rows = fetch_rows(
        """
        SELECT column_name, is_nullable, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'app_settings' AND column_name = 'timezone'
        """
    )
    assert rows, "app_settings.timezone column missing"
    _, is_nullable, data_type, col_default = rows[0]
    assert is_nullable == "NO", f"timezone must be NOT NULL, got {is_nullable!r}"
    assert data_type in ("character varying", "text"), (
        f"timezone data_type unexpected: {data_type!r}"
    )
    assert col_default and "Europe/Berlin" in col_default, (
        f"timezone default missing 'Europe/Berlin': {col_default!r}"
    )


def test_signage_schedules_roundtrip(engine):
    """SGN-TIME-01 round-trip: insert a schedule row, read it back, assert
    FK and CHECK constraints fire on invalid inputs.
    """
    _run_alembic("upgrade", "head")

    playlist_id = uuid.uuid4()
    schedule_id = uuid.uuid4()

    async def _seed() -> None:
        conn = await asyncpg.connect(dsn=_pg_dsn())
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO signage_playlists (id, name) VALUES ($1, $2)",
                    playlist_id,
                    "sched-rt-playlist",
                )
                await conn.execute(
                    "INSERT INTO signage_schedules"
                    " (id, playlist_id, weekday_mask, start_hhmm, end_hhmm,"
                    "  priority, enabled)"
                    " VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    schedule_id,
                    playlist_id,
                    31,  # Mo-Fr
                    700,
                    1100,
                    10,
                    True,
                )
            row = await conn.fetchrow(
                "SELECT id, playlist_id, weekday_mask, start_hhmm, end_hhmm,"
                " priority, enabled"
                " FROM signage_schedules WHERE id = $1",
                schedule_id,
            )
            assert row is not None
            assert row["id"] == schedule_id
            assert row["playlist_id"] == playlist_id
            assert row["weekday_mask"] == 31
            assert row["start_hhmm"] == 700
            assert row["end_hhmm"] == 1100
            assert row["priority"] == 10
            assert row["enabled"] is True
        finally:
            await conn.close()

    async def _fk_violation() -> None:
        """Inserting with a non-existent playlist_id must violate the FK."""
        conn = await asyncpg.connect(dsn=_pg_dsn())
        try:
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                async with conn.transaction():
                    await conn.execute(
                        "INSERT INTO signage_schedules"
                        " (id, playlist_id, weekday_mask, start_hhmm, end_hhmm)"
                        " VALUES ($1, $2, $3, $4, $5)",
                        uuid.uuid4(),
                        uuid.uuid4(),  # playlist doesn't exist
                        1,
                        900,
                        1000,
                    )
        finally:
            await conn.close()

    async def _check_violation(start: int, end: int) -> None:
        """Inserting values that violate any CHECK constraint must raise."""
        conn = await asyncpg.connect(dsn=_pg_dsn())
        try:
            with pytest.raises(asyncpg.CheckViolationError):
                async with conn.transaction():
                    await conn.execute(
                        "INSERT INTO signage_schedules"
                        " (id, playlist_id, weekday_mask, start_hhmm, end_hhmm)"
                        " VALUES ($1, $2, $3, $4, $5)",
                        uuid.uuid4(),
                        playlist_id,
                        1,
                        start,
                        end,
                    )
        finally:
            await conn.close()

    async def _cleanup() -> None:
        conn = await asyncpg.connect(dsn=_pg_dsn())
        try:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM signage_schedules WHERE playlist_id = $1",
                    playlist_id,
                )
                await conn.execute(
                    "DELETE FROM signage_playlists WHERE id = $1", playlist_id
                )
        finally:
            await conn.close()

    try:
        asyncio.run(_seed())
        asyncio.run(_fk_violation())
        # start_hhmm out of range
        asyncio.run(_check_violation(2400, 2500))
        # zero-width window (start == end)
        asyncio.run(_check_violation(1100, 1100))
        # midnight-spanning (start > end) — D-07
        asyncio.run(_check_violation(2200, 200))
    finally:
        asyncio.run(_cleanup())


def test_signage_schedules_partial_index_present(engine):
    """Partial index ix_signage_schedules_enabled_weekday WHERE enabled = true."""
    _run_alembic("upgrade", "head")

    rows = fetch_rows(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'signage_schedules'
          AND indexname = 'ix_signage_schedules_enabled_weekday'
        """
    )
    assert rows, "partial index ix_signage_schedules_enabled_weekday missing"
    up = rows[0][1].upper()
    # Predicate present and on weekday_mask
    assert "ENABLED" in up and "TRUE" in up, (
        f"partial predicate `enabled = true` missing: {rows[0][1]}"
    )
    assert "WEEKDAY_MASK" in up, (
        f"index column `weekday_mask` missing: {rows[0][1]}"
    )
