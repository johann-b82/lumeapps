"""Signage device admin endpoints — calibration PATCH + remote commands.

Phase 70 (v1.22 MIG-SIGN-04): list/get/patch-name/delete/put-tags migrated to
Directus. Only the calibration PATCH survives here. Device row CRUD lives at
the ``signage_devices`` Directus collection. Per-device resolved playlist
lives at ``/api/signage/resolved/{device_id}`` (resolved.py).

Remote commands (``POST .../reload`` and ``POST .../reboot``) push a
one-shot event onto the device's player SSE stream: the kiosk browser
handles ``reload`` (page reload), the Pi sidecar handles ``reboot``
(``systemctl reboot`` via logind + polkit rule). Nothing is persisted —
if no subscriber is connected the command is simply lost and the response
says so (``delivered: 0``).

Compute-justified: clause 1 (SSE fanout).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import SignageDevice, SignageDeviceTagMap
from app.schemas.signage import (
    SignageCalibrationUpdate,
    SignageDeviceCommandResult,
    SignageDeviceRead,
)
from app.services import signage_broadcast
from app.services.signage_resolver import (
    compute_playlist_etag,
    resolve_playlist_for_device,
)

router = APIRouter(prefix="/devices", tags=["signage-admin-devices"])


@router.patch("/{device_id}/calibration", response_model=SignageDeviceRead)
async def update_device_calibration(
    device_id: uuid.UUID,
    payload: SignageCalibrationUpdate,
    db: AsyncSession = Depends(get_async_db_session),
) -> SignageDeviceRead:
    """Phase 62-01 CAL-BE-03 — admin partial-update of calibration fields.

    Phase 70 D-00j: this is the ONLY device write that stays in FastAPI.
    List/get/patch-name/delete/put-tags moved to Directus; per-device
    resolved playlist moved to /api/signage/resolved/{device_id}.

    Admin gate is inherited from the package router (one source of truth per
    admin-package invariant — do NOT add a second gate). Pydantic's
    ``Literal[0, 90, 180, 270]`` on rotation rejects invalid values with
    HTTP 422 automatically (D-10 — no hand-rolled validation).

    On commit, emits a per-device SSE event (CAL-BE-04 / D-04 / D-08) that
    instructs the player to refetch calibration state. Payload is device_id
    only; full state is fetched via GET /api/signage/player/calibration.
    """
    row = (
        await db.execute(select(SignageDevice).where(SignageDevice.id == device_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "device not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.commit()
    await db.refresh(row)
    # CAL-BE-04 / D-08: payload is device_id only (sidecar refetches).
    signage_broadcast.notify_device(
        device_id,
        {"event": "calibration-changed", "device_id": str(device_id)},
    )
    # Inline the resolved-playlist + tag_ids attachment that the previous
    # helper used to provide. Calibration response shape is preserved
    # verbatim from v1.21 (D-00j).
    envelope = await resolve_playlist_for_device(db, row)
    out = SignageDeviceRead.model_validate(row)
    out.current_playlist_id = envelope.playlist_id
    out.current_playlist_name = envelope.name
    tag_rows = await db.execute(
        select(SignageDeviceTagMap.tag_id).where(
            SignageDeviceTagMap.device_id == row.id
        )
    )
    tag_ids = [tid for (tid,) in tag_rows.fetchall()]
    out.tag_ids = tag_ids or None
    return out


async def _send_device_command(
    db: AsyncSession, device_id: uuid.UUID, event: str
) -> SignageDeviceCommandResult:
    exists = (
        await db.execute(
            select(SignageDevice.id).where(SignageDevice.id == device_id)
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(404, "device not found")
    delivered = signage_broadcast.notify_device(
        device_id, {"event": event, "device_id": str(device_id)}
    )
    return SignageDeviceCommandResult(
        event=event, device_id=device_id, delivered=delivered
    )


@router.post(
    "/{device_id}/reload",
    response_model=SignageDeviceCommandResult,
    status_code=202,
)
async def reload_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> SignageDeviceCommandResult:
    """Ask the kiosk browser to reload the player page (SSE ``reload``).

    Admin gate inherited from the package router. Fire-and-forget: 202 with
    ``delivered`` = number of live SSE subscribers that received the event.
    """
    return await _send_device_command(db, device_id, "reload")


@router.post(
    "/{device_id}/reboot",
    response_model=SignageDeviceCommandResult,
    status_code=202,
)
async def reboot_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> SignageDeviceCommandResult:
    """Ask the Pi sidecar to reboot the device (SSE ``reboot``).

    The sidecar runs ``systemctl reboot``; see pi-sidecar/sidecar.py
    ``_reboot_device`` and the polkit rule in scripts/polkit/. Same 202 +
    ``delivered`` contract as ``reload``.
    """
    return await _send_device_command(db, device_id, "reboot")
