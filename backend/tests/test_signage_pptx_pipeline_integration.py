"""Phase 44 end-to-end integration tests (Plan 44-05).

These exercise the real soffice + pdftoppm binaries against a tiny valid
PPTX fixture and the full state machine in
``app.services.signage_pptx.convert_pptx``. They are skipped automatically
on hosts without LibreOffice/poppler on PATH (developer laptops), and run
in Docker CI where Plan 44-01's apt layer supplies them.

Coverage:
  - happy path:           pending -> processing -> done + slide_paths populated
  - corrupt PPTX:         pending -> processing -> failed with
                          conversion_error in {soffice_failed, invalid_pptx}
  - skip-without-binaries: tests skip cleanly when soffice/pdftoppm absent
  - stuck-row reset:      seeds a 10-min-old processing row and verifies the
                          startup hook flips it to failed/abandoned_on_restart

The stuck-row test has NO binary requirement — it must still run on a
developer laptop.
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from app.services import signage_pptx
from app.services.signage_pptx import convert_pptx, SLIDES_ROOT
from app.scheduler import _run_pptx_stuck_reset

pytestmark = pytest.mark.asyncio

_HAS_BINS = (
    shutil.which("soffice") is not None and shutil.which("pdftoppm") is not None
)
_SKIP_BINS = pytest.mark.skipif(
    not _HAS_BINS,
    reason="soffice/pdftoppm not installed on PATH — Docker CI only",
)

FIXTURES = Path(__file__).parent / "fixtures" / "signage"
TINY_VALID = FIXTURES / "tiny-valid.pptx"
CORRUPT = FIXTURES / "corrupt.pptx"


# ---------- DB helpers (mirror test_signage_pptx_stuck_reset.py) ----------


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
        pytest.skip("POSTGRES_* not set — integration tests need a live DB")
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


async def _insert_pptx_row(
    dsn: str,
    *,
    conversion_status: str = "pending",
    conversion_started_at: datetime | None = None,
    uri: str = "fixture-directus-uuid",
) -> uuid.UUID:
    media_id = uuid.uuid4()
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "INSERT INTO signage_media"
            " (id, kind, title, uri, conversion_status, conversion_started_at)"
            " VALUES ($1, 'pptx', $2, $3, $4, $5)",
            media_id,
            f"fixture-{media_id.hex[:6]}.pptx",
            uri,
            conversion_status,
            conversion_started_at,
        )
    finally:
        await conn.close()
    return media_id


async def _fetch_row(dsn: str, media_id: uuid.UUID) -> dict:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        row = await conn.fetchrow(
            "SELECT conversion_status, conversion_error, slide_paths"
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


@pytest.fixture
def _wipe_slides_dir():
    """Track media ids and wipe /app/media/slides/<id>/ after the test."""
    created: list[uuid.UUID] = []
    yield created
    for mid in created:
        shutil.rmtree(Path(SLIDES_ROOT) / str(mid), ignore_errors=True)


def _patch_directus_fetch(monkeypatch, fixture_path: Path) -> None:
    """Replace the Directus download step with a local file copy.

    signage_pptx._download_pptx_from_directus(tempdir, directus_file_uuid)
    streams /assets/<uuid> into tempdir/input.pptx. Monkeypatch it to copy
    the fixture bytes into the same target path — preserves the contract
    _run_pipeline relies on (reads tempdir / "input.pptx").
    """
    async def _fake_fetch(tempdir: Path, directus_file_uuid: str) -> None:
        target = tempdir / "input.pptx"
        target.write_bytes(fixture_path.read_bytes())

    monkeypatch.setattr(
        "app.services.signage_pptx._download_pptx_from_directus", _fake_fetch
    )


# ---------- Real-pipeline tests (skip without binaries) ----------


@_SKIP_BINS
async def test_convert_pptx_happy_path(monkeypatch, _wipe_slides_dir):
    """Tiny valid PPTX → soffice → pdftoppm → done + 2 slides."""
    dsn = await _require_db()
    media_id = await _insert_pptx_row(dsn)
    _wipe_slides_dir.append(media_id)

    _patch_directus_fetch(monkeypatch, TINY_VALID)

    await convert_pptx(media_id)

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] == "done", row
    assert row["conversion_error"] is None, row
    slide_paths = row["slide_paths"]
    # slide_paths is stored as JSONB — asyncpg returns it as a JSON string.
    if isinstance(slide_paths, str):
        import json

        slide_paths = json.loads(slide_paths)
    assert isinstance(slide_paths, list) and len(slide_paths) >= 1
    for p in slide_paths:
        assert isinstance(p, str)
        assert p.startswith(f"slides/{media_id}/slide-")
        assert p.endswith(".png")
    # First slide must exist on disk.
    first_abs = Path(SLIDES_ROOT) / str(media_id) / "slide-001.png"
    assert first_abs.exists(), first_abs


@_SKIP_BINS
async def test_convert_pptx_corrupt_pptx(monkeypatch, _wipe_slides_dir):
    """Non-PPTX bytes → failed with soffice_failed or invalid_pptx."""
    dsn = await _require_db()
    media_id = await _insert_pptx_row(dsn)
    _wipe_slides_dir.append(media_id)

    _patch_directus_fetch(monkeypatch, CORRUPT)

    await convert_pptx(media_id)

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] == "failed", row
    assert row["conversion_error"] in {"soffice_failed", "invalid_pptx"}, row


# ---------- Skip-semantics test (always runs) ----------


async def test_convert_pptx_skipped_without_binaries():
    """Documents the skip contract. Always runs; only asserts on absent bins."""
    if _HAS_BINS:
        pytest.skip(
            "soffice + pdftoppm are installed — this guard test only fires "
            "on developer laptops without LibreOffice/poppler"
        )
    # On hosts without the binaries, the _SKIP_BINS marker above will have
    # skipped the two real-pipeline tests. Assert that marker evaluates to
    # skip to make the contract self-checking.
    assert shutil.which("soffice") is None or shutil.which("pdftoppm") is None


# ---------- Stuck-row reset end-to-end (no binary dep) ----------


async def test_pptx_stuck_reset_end_to_end():
    """Seed a 10-min-old processing PPTX row; hook flips it to failed."""
    dsn = await _require_db()
    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    media_id = await _insert_pptx_row(
        dsn,
        conversion_status="processing",
        conversion_started_at=stale,
    )

    await _run_pptx_stuck_reset()

    row = await _fetch_row(dsn, media_id)
    assert row["conversion_status"] == "failed", row
    assert row["conversion_error"] == "abandoned_on_restart", row
