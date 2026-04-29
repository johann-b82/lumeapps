"""Phase 68 MIG-SIGN-02 — DB-level CHECK enforcement on signage_schedules.

Validates that the CHECK constraint ``ck_signage_schedules_start_before_end``
(plan 68-02 Task 1) rejects any row where ``start_hhmm >= end_hhmm`` with
Postgres sqlstate 23514, and that downgrading drops it cleanly.

Skips when no live Postgres is reachable (mirrors the Phase 51
``test_signage_schema_roundtrip.py`` pattern). Run inside the dev/api
container or with POSTGRES_* / DATABASE_URL env pointing at a test DB.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CONSTRAINT_NAME = "ck_signage_schedules_start_before_end"
PHASE_REVISION = "v1_23_signage_schedule_check"


def _pg_dsn() -> str:
    explicit = os.environ.get("DATABASE_URL") or os.environ.get(
        "SQLALCHEMY_DATABASE_URL"
    )
    if explicit:
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
            "POSTGRES_* env not set — schedule-CHECK test requires live Postgres."
        )
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(dsn=_pg_dsn())


def _run(coro):
    return asyncio.run(coro)


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", *args], cwd=BACKEND_DIR, check=True)


@pytest.fixture(scope="module", autouse=True)
def _ensure_head():
    """Probe DB and ensure migration head is applied for the test module."""
    try:
        _run(_connect()).close  # type: ignore[func-returns-value]
    except Exception as exc:  # pragma: no cover — env-dependent
        pytest.skip(f"Postgres not reachable: {exc!s}")
    _alembic("upgrade", "head")
    yield


async def _make_playlist() -> uuid.UUID:
    """Create a throwaway playlist row so we have a valid FK target."""
    conn = await _connect()
    try:
        pid = uuid.uuid4()
        await conn.execute(
            "INSERT INTO signage_playlists (id, name, created_at, updated_at) "
            "VALUES ($1, $2, now(), now())",
            pid,
            f"check-test-{pid}",
        )
        return pid
    finally:
        await conn.close()


async def _delete_playlist(pid: uuid.UUID) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            "DELETE FROM signage_schedules WHERE playlist_id = $1", pid
        )
        await conn.execute("DELETE FROM signage_playlists WHERE id = $1", pid)
    finally:
        await conn.close()


async def _insert_schedule(
    pid: uuid.UUID, start: int, end: int
) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            "INSERT INTO signage_schedules "
            "(id, playlist_id, weekday_mask, start_hhmm, end_hhmm, "
            " priority, enabled, created_at, updated_at) "
            "VALUES ($1, $2, 1, $3, $4, 0, true, now(), now())",
            uuid.uuid4(),
            pid,
            start,
            end,
        )
    finally:
        await conn.close()


def test_check_constraint_exists_with_canonical_name():
    async def _go():
        conn = await _connect()
        try:
            row = await conn.fetchrow(
                "SELECT conname FROM pg_constraint WHERE conname = $1",
                CONSTRAINT_NAME,
            )
            assert row is not None, (
                f"expected CHECK constraint {CONSTRAINT_NAME!r} on "
                "signage_schedules after `alembic upgrade head`"
            )
        finally:
            await conn.close()

    _run(_go())


def test_positive_insert_succeeds():
    async def _go():
        pid = await _make_playlist()
        try:
            await _insert_schedule(pid, 600, 900)
        finally:
            await _delete_playlist(pid)

    _run(_go())


def test_negative_insert_inverted_range_rejected():
    async def _go():
        pid = await _make_playlist()
        try:
            with pytest.raises(asyncpg.exceptions.CheckViolationError) as exc:
                await _insert_schedule(pid, 900, 600)
            assert exc.value.sqlstate == "23514"
            assert CONSTRAINT_NAME in str(exc.value), (
                f"expected constraint name in error: {exc.value!s}"
            )
        finally:
            await _delete_playlist(pid)

    _run(_go())


def test_boundary_equal_start_end_rejected():
    """CHECK uses strict <, so equal start/end must fail."""
    async def _go():
        pid = await _make_playlist()
        try:
            with pytest.raises(asyncpg.exceptions.CheckViolationError) as exc:
                await _insert_schedule(pid, 600, 600)
            assert exc.value.sqlstate == "23514"
            assert CONSTRAINT_NAME in str(exc.value)
        finally:
            await _delete_playlist(pid)

    _run(_go())


def test_downgrade_then_upgrade_round_trip():
    """After downgrade -1, the canonical constraint name is gone; after
    upgrade head, it is back. Negative insert behaves accordingly.
    """
    async def _is_present() -> bool:
        conn = await _connect()
        try:
            row = await conn.fetchrow(
                "SELECT 1 FROM pg_constraint WHERE conname = $1",
                CONSTRAINT_NAME,
            )
            return row is not None
        finally:
            await conn.close()

    assert _run(_is_present()), "preflight: canonical constraint should exist"
    _alembic("downgrade", "-1")
    assert not _run(_is_present()), (
        "downgrade should rename constraint away from canonical name"
    )
    _alembic("upgrade", "head")
    assert _run(_is_present()), "upgrade should restore canonical name"
