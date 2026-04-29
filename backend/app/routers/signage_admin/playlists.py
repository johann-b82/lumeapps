"""Phase 69 MIG-SIGN-03: surviving DELETE only.

POST/GET/PATCH/PUT-tags moved to Directus collections ``signage_playlists``
and ``signage_playlist_tag_map``. DELETE stays here to preserve the
structured ``409 {detail, schedule_ids}`` shape consumed by
``frontend/src/signage/components/PlaylistDeleteDialog.tsx`` (D-00
architectural lock). Uses the shared ``signage_broadcast.notify_playlist_changed``
helper — the surviving DELETE still fans out playlist-changed events
explicitly alongside the Phase 65 LISTEN/NOTIFY bridge.

All endpoints inherit the admin gate from the parent router.

Compute-justified: clause 1 (SSE fanout) + clause 4 (structured 409 schedule_ids).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import SignagePlaylist, SignageSchedule
from app.services import signage_broadcast
from app.services.signage_resolver import devices_affected_by_playlist

router = APIRouter(prefix="/playlists", tags=["signage-admin-playlists"])


# ---------------------------------------------------------------------------
# Surviving DELETE — preserves structured 409 ``{detail, schedule_ids}``
# (Phase 51 Plan 02 SGN-TIME-04 / RESEARCH Q2). Frontend
# PlaylistDeleteDialog consumes this exact shape.
# ---------------------------------------------------------------------------


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Hard delete. Returns 409 JSONResponse if signage_schedules reference the playlist.

    Phase 51 Plan 02 (SGN-TIME-04 / RESEARCH Q2): FK ``signage_schedules.playlist_id``
    is ``ON DELETE RESTRICT`` (same shape as the existing media→playlist_items FK).
    When a schedule blocks the delete, PostgreSQL raises an IntegrityError at
    commit time; we catch it and return a flat ``{detail, schedule_ids}`` body
    (mirrors the media DELETE 409 ``{detail, playlist_ids}`` convention,
    Pitfall 6 — use JSONResponse not HTTPException so the shape stays flat).
    """
    # Phase 45 D-02: capture affected devices BEFORE the delete commits — the
    # playlist-tag-map rows cascade on delete, which would make the tag-overlap
    # query return an empty list after commit. The notify fan-out happens
    # AFTER commit (Pitfall 3) using this pre-delete snapshot.
    affected = await devices_affected_by_playlist(db, playlist_id)
    try:
        result = await db.execute(
            delete(SignagePlaylist).where(SignagePlaylist.id == playlist_id)
        )
        if result.rowcount == 0:
            raise HTTPException(404, "playlist not found")
        await db.commit()
    except IntegrityError:
        await db.rollback()
        sched_rows = await db.execute(
            select(SignageSchedule.id).where(
                SignageSchedule.playlist_id == playlist_id
            )
        )
        schedule_ids = [str(sid) for sid in sched_rows.scalars().all()]
        return JSONResponse(
            status_code=409,
            content={
                "detail": "playlist has active schedules",
                "schedule_ids": schedule_ids,
            },
        )
    await signage_broadcast.notify_playlist_changed(
        db, playlist_id, affected=affected, deleted=True
    )
