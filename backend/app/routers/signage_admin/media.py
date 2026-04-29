"""Signage media write surface — PATCH (SSE fanout), DELETE (structured 409
+ slide cleanup, D-16 hard delete with 409 on RESTRICT, D-21 option b),
POST /pptx (BackgroundTasks conversion), POST /{id}/reconvert
(BackgroundTasks). List/Get/Create live in Directus per ADR-0001.

All endpoints inherit the admin gate from the parent router. Do NOT add
the admin-role check or current-user dep here (see __init__.py).

Compute-justified: clause 1 (SSE fanout) + clause 4 (structured 409 playlist_ids) + clause 1 (BackgroundTasks for PPTX).
"""
from __future__ import annotations

import logging
import shutil
import uuid
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import SignageMedia, SignagePlaylistItem
from app.schemas.signage import SignageMediaRead
from app.services import signage_broadcast
from app.services.directus_uploads import MAX_UPLOAD_BYTES, upload_pptx_to_directus
from app.services.signage_pptx import convert_pptx, delete_slides_dir

log = logging.getLogger(__name__)

# D-10: canonical PPTX MIME; fallbacks accepted only with the .pptx extension.
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_PPTX_FALLBACK_MIMES = {"application/octet-stream", "application/zip"}

router = APIRouter(prefix="/media", tags=["signage-admin-media"])


class SignageMediaUpdate(BaseModel):
    kind: Literal["image", "video", "pdf", "pptx", "url", "html"] | None = None
    title: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=127)
    uri: str | None = None
    duration_ms: int | None = None
    html_content: str | None = None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


# v1.23 C-4: POST /api/signage/media (non-PPTX) removed — migrated to Directus
# `signage_media` collection (admin-only via admin_access:true). Non-PPTX
# kinds (image/video/pdf/url/html) are now inserted through the Directus SDK
# from signageApi.createMedia. PPTX uploads remain on FastAPI POST /pptx
# (BackgroundTasks PPTX-to-PNG conversion is compute-justified — clause 1).


# v1.23 C-2: GET /api/signage/media (list) removed — migrated to Directus
# `signage_media` collection (admin-only). Frontend calls
# directus.request(readItems('signage_media', ...)) via signageApi.listMedia.
# v1.23 C-3: GET /api/signage/media/{id} (item) removed — migrated to Directus
# (admin-only via admin_access:true; Viewer FORBIDDEN). FE uses
# directus.request(readItem('signage_media', id)) via signageApi.getMedia.
# PATCH, DELETE, POST /pptx, POST /{id}/reconvert remain here (D-21: PPTX
# uploads need backend conversion side-effects; DELETE returns the structured
# 409 {detail, playlist_ids} contract).


@router.patch("/{media_id}", response_model=SignageMediaRead)
async def update_media(
    media_id: uuid.UUID,
    payload: SignageMediaUpdate,
    db: AsyncSession = Depends(get_async_db_session),
) -> SignageMedia:
    row = (
        await db.execute(select(SignageMedia).where(SignageMedia.id == media_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "media not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.commit()
    await db.refresh(row)
    # Phase 45 D-02: media fields surfaced in the resolved envelope (kind, uri,
    # etc.) may have changed — notify every playlist that references this row.
    await signage_broadcast.notify_devices_for_media(db, media_id)
    return row


@router.delete("/{media_id}", status_code=204)
async def delete_media(
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Hard delete. Returns 409 JSONResponse if playlist_items reference this media.

    Pitfall 6: use JSONResponse (not HTTPException) for the 409 body so the
    response shape is flat `{detail, playlist_ids}` rather than FastAPI's
    nested `{detail: {...}}` structure.
    """
    exists = (
        await db.execute(select(SignageMedia.id).where(SignageMedia.id == media_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(404, "media not found")

    try:
        await db.execute(delete(SignageMedia).where(SignageMedia.id == media_id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        ref_result = await db.execute(
            select(SignagePlaylistItem.playlist_id)
            .where(SignagePlaylistItem.media_id == media_id)
            .distinct()
        )
        playlist_ids = [str(pid) for pid in ref_result.scalars().all()]
        return JSONResponse(
            status_code=409,
            content={
                "detail": "media in use by playlists",
                "playlist_ids": playlist_ids,
            },
        )

    # Post-commit slide cleanup (best-effort; never rolls back the response).
    try:
        shutil.rmtree(f"/app/media/slides/{media_id}", ignore_errors=True)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("media slide dir cleanup failed for %s: %s", media_id, exc)

    # 204 No Content
    return None


# ---------------------------------------------------------------------------
# PPTX upload + reconvert (Phase 44 Plan 03 — SGN-BE-07)
# ---------------------------------------------------------------------------


@router.post("/pptx", response_model=SignageMediaRead, status_code=201)
async def upload_pptx_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., max_length=255),
    db: AsyncSession = Depends(get_async_db_session),
) -> SignageMedia:
    """D-10: multipart PPTX upload.

    Streams the uploaded bytes into Directus, inserts a pending SignageMedia
    row, schedules conversion via BackgroundTasks, and returns 201 immediately.
    Enforces the 50MB cap (D-13) inside the stream iterator — HTTPException(413)
    is raised by ``upload_pptx_to_directus`` the moment the running total
    exceeds ``MAX_UPLOAD_BYTES``, BEFORE the whole body is read into memory.
    """
    # D-10: validate MIME / extension first (cheap rejection).
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    is_pptx_mime = content_type == PPTX_MIME
    is_pptx_ext = filename.endswith(".pptx")
    is_fallback = content_type in _PPTX_FALLBACK_MIMES and is_pptx_ext
    if not (is_pptx_mime or is_fallback):
        raise HTTPException(
            status_code=400,
            detail="file must be a .pptx presentation",
        )

    # Stream body -> Directus. The helper raises HTTPException(413) on cap breach,
    # BEFORE the whole body is read into memory (MAX_UPLOAD_BYTES=50MB).
    async def _body_iter():
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    directus_uuid, total_bytes = await upload_pptx_to_directus(
        filename=file.filename or "upload.pptx",
        content_type=PPTX_MIME,  # normalise — Directus stores the canonical MIME.
        body_stream=_body_iter(),
    )

    row = SignageMedia(
        kind="pptx",
        title=title,
        mime_type=PPTX_MIME,
        size_bytes=total_bytes,
        uri=directus_uuid,
        conversion_status="pending",
        slide_paths=None,
        conversion_error=None,
        conversion_started_at=None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    # D-08: schedule conversion AFTER the row is committed so the background
    # task can re-fetch it via its own session.
    background_tasks.add_task(convert_pptx, row.id)
    return row


@router.post("/{media_id}/reconvert", response_model=SignageMediaRead, status_code=202)
async def reconvert_pptx_media(
    media_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db_session),
) -> SignageMedia:
    """D-12: reset a PPTX row to pending, clear derived slides, re-schedule conversion."""
    row = (
        await db.execute(select(SignageMedia).where(SignageMedia.id == media_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="media not found")
    if row.kind != "pptx":
        raise HTTPException(status_code=409, detail="media is not a PPTX")
    if row.conversion_status == "processing":
        raise HTTPException(status_code=409, detail="conversion already in progress")

    row.conversion_status = "pending"
    row.slide_paths = None
    row.conversion_error = None
    row.conversion_started_at = None
    await db.commit()
    await db.refresh(row)

    # D-12: wipe the old derived slides dir BEFORE the new conversion starts.
    # delete_slides_dir is best-effort and non-raising (see plan 44-02).
    delete_slides_dir(media_id)

    background_tasks.add_task(convert_pptx, row.id)
    return row
