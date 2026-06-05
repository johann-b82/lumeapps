"""Phase 43 SGN-BE-02 + Phase 45 SGN-BE-05/SGN-DIFF-01: device-facing endpoints.

Per CONTEXT D-02: router-level ``get_current_device`` gate applies to every
endpoint in this module. ``/playlist`` and ``/heartbeat`` landed in Phase 43;
``/stream`` (SSE) was added in Phase 45 Plan 02.

Decisions enforced here:
  - D-09: GET /playlist serves an ETag derived from the tag-resolved playlist
    envelope. When the kiosk sends ``If-None-Match`` matching the server's
    current ETag, we return 304 with an empty body.
  - D-10: GET /playlist is pure-read. It does NOT update
    ``signage_devices.last_seen_at``; heartbeat owns presence.
  - D-11 / D-12: POST /heartbeat updates ``last_seen_at``, ``current_item_id``,
    and ``current_playlist_etag``, and flips ``status`` from ``offline`` to
    ``online`` on the first heartbeat after an offline window. Returns 200
    with a freshly-minted, non-expiring device JWT so the client's in-flight
    credential is continuously rolled (forward-secrecy hygiene; the token is
    revoke-only, so missed rotations never force a re-pair).
  - Phase 45 D-01 / D-03: GET /stream pushes ``{event,playlist_id,etag}`` SSE
    frames with 15s server pings, uses last-writer-wins semantics on
    reconnect, and re-raises ``asyncio.CancelledError`` in the generator's
    finally so the per-device queue is always cleaned up.

Compute-justified: clause 1 (SSE stream + resolver compute).
"""
from __future__ import annotations

import asyncio
import json
import uuid as uuid_lib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_async_db_session
from app.models.signage import SignageDevice, SignageHeartbeatEvent, SignageMedia
from app.schemas.signage import (
    HeartbeatRequest,
    HeartbeatResponse,
    PlaylistEnvelope,
    SignageCalibrationRead,
)
from app.security.device_auth import get_current_device
from app.services import signage_broadcast
from app.services.signage_pairing import mint_device_jwt
from app.services.signage_resolver import (
    compute_playlist_etag,
    resolve_playlist_for_device,
)

# Router-level device-token gate (D-02). No user-auth symbols may appear in
# this module — the Phase 43 dep-audit test (Plan 05) asserts only
# ``get_current_device`` appears in the auth surface of these routes.
router = APIRouter(
    prefix="/api/signage/player",
    tags=["signage-player"],
    dependencies=[Depends(get_current_device)],
)


@router.get("/playlist", response_model=None)
async def get_device_playlist(
    request: Request,
    response: Response,
    device: SignageDevice = Depends(get_current_device),
    db: AsyncSession = Depends(get_async_db_session),
):
    """D-06 / D-07 / D-09 / D-10: tag-resolved playlist with ETag/304.

    Does NOT update ``signage_devices.last_seen_at`` (D-10). Heartbeat owns
    presence. A matching ``If-None-Match`` header short-circuits to 304 with
    an empty body.
    """
    envelope = await resolve_playlist_for_device(db, device)
    etag = compute_playlist_etag(envelope)
    quoted = f'"{etag}"'
    client_etag = request.headers.get("If-None-Match", "").strip()
    if client_etag and client_etag.strip('"') == etag:
        return Response(
            status_code=304,
            headers={"ETag": quoted, "Cache-Control": "no-cache"},
        )
    response.headers["ETag"] = quoted
    response.headers["Cache-Control"] = "no-cache"
    return envelope


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def post_heartbeat(
    payload: HeartbeatRequest,
    device: SignageDevice = Depends(get_current_device),
    db: AsyncSession = Depends(get_async_db_session),
) -> HeartbeatResponse:
    """D-11 / D-12: update presence and roll the device JWT.

    Writes ``last_seen_at`` / ``current_item_id`` / ``current_playlist_etag``,
    and flips ``status`` to ``online`` if the device was previously offline.

    The response carries a freshly-minted device JWT so the client's
    in-flight credential is continuously rolled. Device tokens are
    non-expiring (revoke-only), so the rolling rotation is forward-secrecy
    hygiene rather than a re-pair-avoidance mechanism — a kiosk that misses
    every rotation still keeps working until its row is revoked.
    """
    now = datetime.now(timezone.utc)
    values: dict = {
        "last_seen_at": now,
        "current_item_id": payload.current_item_id,
        "current_playlist_etag": payload.playlist_etag,
    }
    if device.status == "offline":
        values["status"] = "online"
    # v1.50: Pi sidecar reports identity each heartbeat. Only write columns
    # that arrived non-null so a browser-fallback heartbeat (which can't
    # see MAC/hostname/IP) doesn't clobber a previously-known value.
    if payload.mac_address is not None:
        values["mac_address"] = payload.mac_address
    if payload.hostname is not None:
        values["hostname"] = payload.hostname
    if payload.ip_address is not None:
        values["ip_address"] = payload.ip_address
    await db.execute(
        update(SignageDevice)
        .where(SignageDevice.id == device.id)
        .values(**values)
    )
    # Phase 53 SGN-ANA-01 — log heartbeat event for Analytics-lite uptime metric.
    # Idempotent on (device_id, ts) microsecond collision (e.g. network retry).
    hb_stmt = (
        pg_insert(SignageHeartbeatEvent)
        .values(device_id=device.id, ts=now)
        .on_conflict_do_nothing(index_elements=["device_id", "ts"])
    )
    await db.execute(hb_stmt)
    await db.commit()
    return HeartbeatResponse(token=mint_device_jwt(device.id))


@router.get("/stream")
async def stream_events(
    device: SignageDevice = Depends(get_current_device),
) -> EventSourceResponse:
    """SSE: streams playlist-changed events to connected players.

    Phase 45 SGN-BE-05 / SGN-DIFF-01. Payload shape per CONTEXT D-01:
    ``{"event": "playlist-changed", "playlist_id": <int>, "etag": "<weak-etag>"}``.

    - ``signage_broadcast.subscribe`` replaces any prior queue for this
      device (D-03 last-writer-wins).
    - The ``finally`` block pops with ``None`` default so the OLD generator
      tearing down AFTER a newer connection replaced its queue does NOT
      clobber the fresh registration (RESEARCH §Pitfall 1).
    - ``asyncio.CancelledError`` MUST be re-raised — swallowing it leaves a
      zombie coroutine (RESEARCH §Pitfall 2).
    - ``ping=15`` tells sse-starlette to emit a comment-line keepalive every
      15 seconds, keeping idle intermediaries from closing the connection.
    """
    queue = signage_broadcast.subscribe(device.id)

    async def event_generator():
        try:
            while True:
                payload = await queue.get()
                yield {"data": json.dumps(payload)}
        except asyncio.CancelledError:
            raise  # MUST re-raise — per Pitfall 2
        finally:
            # Fan-out cleanup: remove only THIS generator's queue from the
            # per-device subscriber list.  unsubscribe() uses identity (is)
            # comparison so other concurrent subscribers (e.g. the Pi sidecar
            # and the kiosk browser both subscribed simultaneously) are not
            # affected.  (pi-sidecar-sse-loop-silent fix.)
            signage_broadcast.unsubscribe(device.id, queue)

    return EventSourceResponse(event_generator(), ping=15)


# Phase 47 DEFECT-5: device-auth'd asset passthrough. Without this the envelope's
# `uri` (a bare Directus file UUID) has no base and <img src> falls back to
# /player/<uuid>, which the SPA fallback serves as index.html (text/html).
#
# Uploads directory is mounted ro via docker-compose (directus_uploads volume).
# filename_disk convention is "<uuid>.<ext>" — glob for the uuid prefix.
_UPLOADS_DIR = Path("/directus/uploads")
# PPTX slides are written by signage_pptx.py to /app/media/slides/<media_id>/slide-NNN.png.
# Same root used by SLIDES_ROOT over there; kept as a literal here to avoid
# importing the conversion module (which pulls in subprocess + httpx fixtures).
_MEDIA_ROOT = Path("/app/media")


@router.get("/asset/{media_id}")
async def get_media_asset(
    media_id: uuid_lib.UUID,
    device: SignageDevice = Depends(get_current_device),
    db: AsyncSession = Depends(get_async_db_session),
) -> FileResponse:
    media = (
        await db.execute(select(SignageMedia).where(SignageMedia.id == media_id))
    ).scalar_one_or_none()
    if media is None or not media.uri:
        raise HTTPException(status_code=404, detail="media not found")
    # `uri` stores the Directus file UUID; file on disk is <uuid>.<ext>.
    matches = sorted(_UPLOADS_DIR.glob(f"{media.uri}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="asset not on disk")
    return FileResponse(
        matches[0],
        media_type=media.mime_type or None,
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/asset/{media_id}/slide/{idx}")
async def get_pptx_slide(
    media_id: uuid_lib.UUID,
    idx: int,
    device: SignageDevice = Depends(get_current_device),
    db: AsyncSession = Depends(get_async_db_session),
) -> FileResponse:
    """Serve a single PPTX slide PNG with device auth.

    Conversion writes slides under /app/media/slides/<media_id>/, and the DB row
    persists their relative paths in signage_media.slide_paths. The kiosk addresses
    them by 1-based index; we look the path up in the row rather than reconstructing
    the filename so a future naming change in signage_pptx stays transparent here.
    """
    media = (
        await db.execute(select(SignageMedia).where(SignageMedia.id == media_id))
    ).scalar_one_or_none()
    if media is None or media.kind != "pptx" or not media.slide_paths:
        raise HTTPException(status_code=404, detail="slide not found")
    if idx < 1 or idx > len(media.slide_paths):
        raise HTTPException(status_code=404, detail="slide index out of range")
    rel = media.slide_paths[idx - 1]
    candidate = (_MEDIA_ROOT / rel).resolve()
    media_root = _MEDIA_ROOT.resolve()
    # Defense-in-depth: refuse anything that escaped /app/media/ via symlink or ../.
    if media_root not in candidate.parents and candidate != media_root:
        raise HTTPException(status_code=404, detail="slide path outside media root")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="slide file missing")
    return FileResponse(
        candidate,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/calibration", response_model=SignageCalibrationRead)
async def get_device_calibration(
    device: SignageDevice = Depends(get_current_device),
) -> SignageCalibrationRead:
    """Phase 62-01 CAL-BE-05 — device-auth calibration read.

    Scoped to the calling device via the router-level ``get_current_device``
    dep (D-02 / D-10). Sidecar calls this on every ``calibration-changed``
    SSE event (D-04 / D-08) to fetch the full state after the device_id-only
    event payload.
    """
    return SignageCalibrationRead(
        rotation=device.rotation,
        hdmi_mode=device.hdmi_mode,
        audio_enabled=device.audio_enabled,
    )
