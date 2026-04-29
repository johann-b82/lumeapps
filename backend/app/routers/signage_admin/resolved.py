"""Phase 70 D-01 — per-device resolved playlist computation.

Lifted from devices.py::_attach_resolved_playlist (lines 62-79). Returns the
same three fields the FE was reading off SignageDeviceRead:
current_playlist_id, current_playlist_name, tag_ids. Field names match
exactly so the FE merge is `{...directusRow, ...resolvedResponse}` with
zero rename (D-01).

Admin gate inherited from signage_admin package router (D-01c / cross-cutting
hazard #5) — do NOT add a second gate here.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import SignageDevice, SignageDeviceTagMap
from app.services.signage_resolver import resolve_playlist_for_device

router = APIRouter(prefix="/resolved", tags=["signage-admin-resolved"])


class ResolvedDeviceResponse(BaseModel):
    current_playlist_id: uuid.UUID | None = None
    current_playlist_name: str | None = None
    tag_ids: list[int] | None = None


@router.get("/{device_id}", response_model=ResolvedDeviceResponse)
async def get_resolved_for_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> ResolvedDeviceResponse:
    """Per-device resolved playlist + tag_ids. 404 on unknown device."""
    row = (
        await db.execute(
            select(SignageDevice).where(SignageDevice.id == device_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "device not found")
    envelope = await resolve_playlist_for_device(db, row)
    tag_rows = await db.execute(
        select(SignageDeviceTagMap.tag_id).where(
            SignageDeviceTagMap.device_id == device_id
        )
    )
    tag_ids = [tid for (tid,) in tag_rows.fetchall()]
    return ResolvedDeviceResponse(
        current_playlist_id=envelope.playlist_id,
        current_playlist_name=envelope.name,
        tag_ids=tag_ids or None,
    )
