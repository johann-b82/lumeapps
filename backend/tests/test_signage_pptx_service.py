"""Unit tests for app.services.signage_pptx — SGN-BE-08 / Phase 44.

Covers:
  - Module-level constants (CONVERSION_TIMEOUT_S, SLIDES_ROOT, semaphore).
  - Row-missing and non-pptx short-circuit (no raise, no state write).
  - Timeout path: asyncio.wait_for(pipeline, timeout=...) raises and row
    lands in failed/'timeout'.
  - soffice non-zero rc path: row lands in failed/'soffice_failed'.
  - delete_slides_dir is best-effort (never raises even on missing dir).

Uses the same live-Postgres skip pattern as test_signage_resolver.py — we
need a real signage_media row for the state-machine writes, but
subprocesses are monkeypatched so the test never touches libreoffice or
poppler.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from app.database import AsyncSessionLocal, engine


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
        pytest.skip("POSTGRES_* not set — signage_pptx tests need a live DB")
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


@pytest_asyncio.fixture
async def dsn():
    d = await _require_db()
    await _cleanup(d)
    try:
        await engine.dispose()
    except Exception:
        pass
    yield d
    await _cleanup(d)


async def _insert_media(
    dsn: str,
    *,
    kind: str = "pptx",
    title: str = "deck",
    uri: str | None = "fake-directus-uuid",
    conversion_status: str | None = "pending",
) -> uuid.UUID:
    mid = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_media (id, kind, title, uri, conversion_status)"
            " VALUES ($1, $2, $3, $4, $5)",
            mid,
            kind,
            title,
            uri,
            conversion_status,
        )
    finally:
        await conn.close()
    return mid


async def _fetch_media(dsn: str, mid: uuid.UUID) -> dict[str, Any]:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "SELECT conversion_status, conversion_error, slide_paths"
            " FROM signage_media WHERE id = $1",
            mid,
        )
    finally:
        await conn.close()
    return dict(row) if row else {}


# ----------------------------------------------------------------------------
# Module-level constants
# ----------------------------------------------------------------------------


def test_module_constants():
    from app.services import signage_pptx

    assert signage_pptx.CONVERSION_TIMEOUT_S == 60
    assert signage_pptx.SLIDES_ROOT == "/app/media/slides"
    assert isinstance(signage_pptx._CONVERSION_SEMAPHORE, asyncio.Semaphore)
    # Semaphore(1) exposes its internal counter via `_value` in CPython.
    assert signage_pptx._CONVERSION_SEMAPHORE._value == 1


# ----------------------------------------------------------------------------
# delete_slides_dir — best-effort, never raises
# ----------------------------------------------------------------------------


def test_delete_slides_dir_missing_is_noop(tmp_path, monkeypatch):
    from app.services import signage_pptx

    # Point SLIDES_ROOT at a nonexistent subdir of tmp_path — call must not raise.
    monkeypatch.setattr(signage_pptx, "SLIDES_ROOT", str(tmp_path / "nope"))
    signage_pptx.delete_slides_dir(uuid.uuid4())  # should not raise


def test_delete_slides_dir_existing_removes_tree(tmp_path, monkeypatch):
    from app.services import signage_pptx

    monkeypatch.setattr(signage_pptx, "SLIDES_ROOT", str(tmp_path))
    mid = uuid.uuid4()
    d = tmp_path / str(mid)
    d.mkdir()
    (d / "slide-001.png").write_bytes(b"x")

    signage_pptx.delete_slides_dir(mid)

    assert not d.exists()


# ----------------------------------------------------------------------------
# convert_pptx short-circuits on missing / non-pptx rows
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_convert_pptx_row_missing_does_not_raise(dsn):
    from app.services import signage_pptx

    # Row never existed — convert must short-circuit cleanly.
    await signage_pptx.convert_pptx(uuid.uuid4())


@pytest.mark.asyncio
async def test_convert_pptx_non_pptx_kind_does_not_raise(dsn):
    from app.services import signage_pptx

    mid = await _insert_media(dsn, kind="image", conversion_status=None)
    await signage_pptx.convert_pptx(mid)

    row = await _fetch_media(dsn, mid)
    # Non-pptx row must not be touched.
    assert row["conversion_status"] is None


# ----------------------------------------------------------------------------
# Timeout path
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_convert_pptx_timeout_sets_failed_timeout(dsn, monkeypatch):
    from app.services import signage_pptx

    mid = await _insert_media(dsn)

    # Force the outer wait_for to trip almost immediately while the inner
    # pipeline sleeps forever. This is the exact shape of a real timeout
    # except we don't need soffice/pdftoppm on the test image.
    async def _slow_pipeline(*args, **kwargs):
        await asyncio.sleep(999)

    monkeypatch.setattr(signage_pptx, "_run_pipeline", _slow_pipeline)
    monkeypatch.setattr(signage_pptx, "CONVERSION_TIMEOUT_S", 0.05)
    # Skip the Directus fetch — it would try to go over the network.
    monkeypatch.setattr(
        signage_pptx, "_download_pptx_from_directus", _no_directus
    )

    await signage_pptx.convert_pptx(mid)

    row = await _fetch_media(dsn, mid)
    assert row["conversion_status"] == "failed"
    assert row["conversion_error"] == "timeout"


async def _no_directus(*args, **kwargs):
    # Signature mirrors the private helper: (tempdir, directus_uuid) -> None.
    # Tests don't need an actual PPTX on disk because _run_pipeline is mocked.
    return None


# ----------------------------------------------------------------------------
# Subprocess-failure path
# ----------------------------------------------------------------------------


class _FakeProc:
    """Minimal stand-in for asyncio subprocess handles."""

    def __init__(self, returncode: int = 1, stderr: bytes = b"boom"):
        self.returncode = returncode
        self._stderr = stderr

    async def communicate(self):
        return b"", self._stderr

    def kill(self):
        pass


@pytest.mark.asyncio
async def test_convert_pptx_soffice_failure_sets_soffice_failed(dsn, monkeypatch):
    from app.services import signage_pptx

    mid = await _insert_media(dsn)

    async def _fake_exec(*args, **kwargs):
        return _FakeProc(returncode=1, stderr=b"soffice exploded")

    monkeypatch.setattr(
        signage_pptx.asyncio, "create_subprocess_exec", _fake_exec
    )
    monkeypatch.setattr(
        signage_pptx, "_download_pptx_from_directus", _no_directus
    )

    await signage_pptx.convert_pptx(mid)

    row = await _fetch_media(dsn, mid)
    assert row["conversion_status"] == "failed"
    assert row["conversion_error"] == "soffice_failed"
