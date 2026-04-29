"""PPTX conversion pipeline (SGN-BE-07/08 — Phase 44).

soffice --headless --convert-to pdf  ->  pdftoppm -r 144 -scale-to-x 1920
-scale-to-y 1080 -png.

One-at-a-time across the container via module-level asyncio.Semaphore(1);
60s total-pipeline budget via outer asyncio.wait_for; per-invocation
LibreOffice profile dir and tempdir always cleaned in finally. All
terminal status writes go through a single AsyncSessionLocal() block per
invocation.

D-14 taxonomy (conversion_error codes written by this module):
    timeout
    soffice_failed
    pdftoppm_failed
    no_slides_produced
    invalid_pptx

The `abandoned_on_restart` code is set by the scheduler startup hook
(plan 44-04), NOT here.

Hazard #7: this module MUST NOT use sync subprocess. The CI grep guards
in tests/test_signage_ci_guards.py enforce this — the sync
``subprocess`` APIs (run/Popen/call) are all forbidden; use
``asyncio.create_subprocess_exec`` only.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select, update

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import SignageMedia

log = logging.getLogger(__name__)

# D-04: serialise all conversions across the single-worker api container.
_CONVERSION_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(1)
# D-03: 60s total pipeline budget.
CONVERSION_TIMEOUT_S: int = 60
# D-06: derived slides live on backend disk (not Directus).
SLIDES_ROOT: str = "/app/media/slides"
# Last N bytes of subprocess stderr to log (D-15 keeps it out of the DB).
_STDERR_TAIL_BYTES: int = 2048
# Directus fetch budget — independent of the pipeline budget so a slow
# download can't silently eat the whole 60s wait_for window for the
# subprocesses. Deliberately shorter than CONVERSION_TIMEOUT_S.
_DIRECTUS_FETCH_TIMEOUT_S: float = 30.0


# ---------------------------------------------------------------------------
# State-machine write helpers
# ---------------------------------------------------------------------------


async def _set_failed(media_id: _uuid.UUID, code: str) -> None:
    """Terminal failure write — conversion_status='failed', conversion_error=code (D-14)."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(SignageMedia)
                .where(SignageMedia.id == media_id)
                .values(conversion_status="failed", conversion_error=code)
            )
            await session.commit()
    except Exception:
        # State-machine write must never raise out of the background task
        # (BackgroundTasks swallows exceptions silently — we'd lose signal).
        log.exception("signage_pptx: _set_failed(%s, %s) db write failed", media_id, code)


async def _set_done(media_id: _uuid.UUID, slide_paths: list[str]) -> None:
    """Terminal success write.

    Phase 45 Plan 02: on the ``processing → done`` transition, fan a
    ``playlist-changed`` frame out to every device whose resolved playlist
    references this media. Notify is wrapped in try/except — a broadcast
    failure must NEVER roll back or mask the state write.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(SignageMedia)
                .where(SignageMedia.id == media_id)
                .values(
                    conversion_status="done",
                    slide_paths=slide_paths,
                    conversion_error=None,
                )
            )
            await session.commit()
            # Post-commit notify — AFTER commit per Pitfall 3.
            try:
                await _notify_media_referenced_playlists(session, media_id)
            except Exception:  # noqa: BLE001
                log.warning(
                    "signage_pptx: post-done broadcast failed for %s",
                    media_id,
                    exc_info=True,
                )
    except Exception:
        log.exception("signage_pptx: _set_done(%s) db write failed", media_id)


async def _notify_media_referenced_playlists(session, media_id: _uuid.UUID) -> None:
    """Phase 45 D-02: PPTX reconvert-done notify helper.

    Duplicated locally (per plan 45-02) to avoid import-cycle with
    ``app.routers.signage_admin.media`` and to keep the pptx service's blast
    radius minimal. Query + fanout are two lines each.
    """
    from app.models import SignageDevice as _Dev
    from app.models import SignagePlaylistItem as _Item
    from app.services import signage_broadcast
    from app.services.signage_resolver import (
        compute_playlist_etag,
        devices_affected_by_playlist,
        resolve_playlist_for_device,
    )

    rows = await session.execute(
        select(_Item.playlist_id).where(_Item.media_id == media_id).distinct()
    )
    playlist_ids = [pid for (pid,) in rows.fetchall()]
    for pl_id in playlist_ids:
        affected = await devices_affected_by_playlist(session, pl_id)
        for device_id in affected:
            dev = (
                await session.execute(select(_Dev).where(_Dev.id == device_id))
            ).scalar_one_or_none()
            if dev is None:
                continue
            envelope = await resolve_playlist_for_device(session, dev)
            signage_broadcast.notify_device(
                device_id,
                {
                    "event": "playlist-changed",
                    "playlist_id": str(pl_id),
                    "etag": compute_playlist_etag(envelope),
                },
            )


async def _set_processing(media_id: _uuid.UUID) -> None:
    """Mark row 'processing' + stamp conversion_started_at (D-08)."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(SignageMedia)
            .where(SignageMedia.id == media_id)
            .values(
                conversion_status="processing",
                conversion_started_at=datetime.now(timezone.utc),
                conversion_error=None,
            )
        )
        await session.commit()


async def _load_media(media_id: _uuid.UUID) -> SignageMedia | None:
    async with AsyncSessionLocal() as session:
        stmt = select(SignageMedia).where(SignageMedia.id == media_id)
        return (await session.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def delete_slides_dir(media_uuid: _uuid.UUID) -> None:
    """Best-effort cleanup of `/app/media/slides/<uuid>/`.

    Used by the reconvert endpoint (plan 44-03) to clear the derived
    slide directory before re-running the pipeline against the same
    media_id. Never raises.
    """
    try:
        shutil.rmtree(Path(SLIDES_ROOT) / str(media_uuid), ignore_errors=True)
    except Exception:
        log.warning(
            "signage_pptx: delete_slides_dir failed for %s", media_uuid, exc_info=True
        )


async def convert_pptx(media_id: _uuid.UUID) -> None:
    """BackgroundTask entry point — convert the PPTX referenced by media_id.

    Never raises: all terminal states (success or failure) are recorded
    on the signage_media row. Any unexpected exception is logged and
    recorded as conversion_error='soffice_failed' (conservative fallback).
    """
    # Pre-semaphore guardrails: missing row / wrong kind / no Directus uri.
    media = await _load_media(media_id)
    if media is None:
        log.warning("signage_pptx: media_id=%s not found; skipping", media_id)
        return
    if media.kind != "pptx":
        log.warning(
            "signage_pptx: media_id=%s has kind=%r (not pptx); skipping",
            media_id,
            media.kind,
        )
        return
    if not media.uri:
        log.warning(
            "signage_pptx: media_id=%s has no uri (Directus file UUID); failing",
            media_id,
        )
        await _set_failed(media_id, "invalid_pptx")
        return

    directus_file_uuid = media.uri

    async with _CONVERSION_SEMAPHORE:
        await _set_processing(media_id)

        tempdir = Path(f"/tmp/pptx_{_uuid.uuid4()}")
        lo_profile = Path(f"/tmp/lo_{_uuid.uuid4()}")

        try:
            tempdir.mkdir(parents=True, exist_ok=True)

            # Pull the raw PPTX bytes from Directus and stage on disk for
            # soffice. _run_pipeline reads `tempdir / "input.pptx"`.
            try:
                await _download_pptx_from_directus(tempdir, directus_file_uuid)
            except Exception:
                log.exception(
                    "signage_pptx: directus download failed for media_id=%s",
                    media_id,
                )
                await _set_failed(media_id, "invalid_pptx")
                return

            try:
                await asyncio.wait_for(
                    _run_pipeline(tempdir, lo_profile, media_id),
                    timeout=CONVERSION_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                log.warning(
                    "signage_pptx: media_id=%s pipeline exceeded %ss budget",
                    media_id,
                    CONVERSION_TIMEOUT_S,
                )
                await _set_failed(media_id, "timeout")
                return
            except Exception:
                # Unknown/unexpected error inside the pipeline — conservative
                # fallback so the row never stays in 'processing' silently.
                log.exception(
                    "signage_pptx: unexpected error for media_id=%s", media_id
                )
                await _set_failed(media_id, "soffice_failed")
                return
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)
            shutil.rmtree(lo_profile, ignore_errors=True)


# ---------------------------------------------------------------------------
# Directus fetch helper (internal — distinct from the upload helper in
# services.directus_uploads because this is a pure download path).
# ---------------------------------------------------------------------------


async def _download_pptx_from_directus(
    tempdir: Path, directus_file_uuid: str
) -> None:
    """Stream /assets/<uuid> from Directus into `tempdir/input.pptx`.

    Uses the admin token (same settings as services.directus_uploads) so
    the request can resolve files regardless of public-asset permissions.
    """
    url = f"{settings.DIRECTUS_URL.rstrip('/')}/assets/{directus_file_uuid}"
    headers = {"Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}"}
    target = tempdir / "input.pptx"

    async with httpx.AsyncClient(timeout=_DIRECTUS_FETCH_TIMEOUT_S) as http:
        async with http.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            with open(target, "wb") as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)


# ---------------------------------------------------------------------------
# The subprocess pipeline
# ---------------------------------------------------------------------------


async def _run_pipeline(
    tempdir: Path, lo_profile: Path, media_id: _uuid.UUID
) -> None:
    """Run soffice -> pdftoppm inside the outer wait_for budget.

    On any failure branch this helper calls _set_failed(...) directly and
    returns — it NEVER raises to the caller except for asyncio.TimeoutError
    (propagated by wait_for) or truly unexpected exceptions.
    """
    input_path = tempdir / "input.pptx"

    # ---- soffice: PPTX -> PDF ------------------------------------------------
    soffice_proc = await asyncio.create_subprocess_exec(
        "soffice",
        "--headless",
        f"-env:UserInstallation=file://{lo_profile}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(tempdir),
        str(input_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, soffice_stderr = await soffice_proc.communicate()
    except asyncio.CancelledError:
        # Timeout reached — kill and re-raise so wait_for sees TimeoutError.
        try:
            soffice_proc.kill()
        except ProcessLookupError:
            pass
        raise

    if soffice_proc.returncode != 0:
        _log_stderr_tail("soffice", soffice_stderr)
        await _set_failed(media_id, "soffice_failed")
        return

    # Locate the PDF soffice produced.
    try:
        pdf_path = next(tempdir.glob("*.pdf"))
    except StopIteration:
        log.warning(
            "signage_pptx: soffice exited 0 but produced no PDF for %s", media_id
        )
        await _set_failed(media_id, "invalid_pptx")
        return

    # ---- pdftoppm: PDF -> PNG slides ----------------------------------------
    pdftoppm_proc = await asyncio.create_subprocess_exec(
        "pdftoppm",
        "-r",
        "144",
        "-scale-to-x",
        "1920",
        "-scale-to-y",
        "1080",
        "-png",
        str(pdf_path),
        str(tempdir / "slide"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, pdftoppm_stderr = await pdftoppm_proc.communicate()
    except asyncio.CancelledError:
        try:
            pdftoppm_proc.kill()
        except ProcessLookupError:
            pass
        raise

    if pdftoppm_proc.returncode != 0:
        _log_stderr_tail("pdftoppm", pdftoppm_stderr)
        await _set_failed(media_id, "pdftoppm_failed")
        return

    # Collect produced PNGs (pdftoppm names them slide-1.png, slide-2.png, ...).
    produced = sorted(tempdir.glob("slide-*.png"))
    if not produced:
        await _set_failed(media_id, "no_slides_produced")
        return

    # ---- Rename to zero-padded 3-digit scheme and move to SLIDES_ROOT -------
    out_dir = Path(SLIDES_ROOT) / str(media_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    slide_paths: list[str] = []
    for idx, src in enumerate(produced, start=1):
        dest = out_dir / f"slide-{idx:03d}.png"
        shutil.move(str(src), str(dest))
        slide_paths.append(f"slides/{media_id}/slide-{idx:03d}.png")

    await _set_done(media_id, slide_paths)


def _log_stderr_tail(tool: str, stderr: bytes | None) -> None:
    """Log the last 2KB of a subprocess stderr at WARNING (D-15).

    The tail stays OUT of conversion_error on the DB row; only the short
    machine code from the D-14 taxonomy is persisted.
    """
    if not stderr:
        return
    tail = stderr[-_STDERR_TAIL_BYTES:]
    try:
        decoded = tail.decode("utf-8", errors="replace")
    except Exception:
        decoded = repr(tail)
    log.warning("signage_pptx: %s stderr tail: %s", tool, decoded)
