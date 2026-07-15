"""Maschinen-Wartung router — machine maintenance (v1.82, admin-only).

All endpoints are admin-gated at the router level (setup is admin work in
Phase 1). Routes:

    POST   /api/maintenance/machines                     create a machine
    GET    /api/maintenance/machines                     list machines
    GET    /api/maintenance/machines/{id}                machine + tasks + files
    PATCH  /api/maintenance/machines/{id}                edit machine
    DELETE /api/maintenance/machines/{id}                delete (cascade)
    POST   /api/maintenance/machines/{id}/tasks          add a task
    PATCH  /api/maintenance/tasks/{tid}                  edit a task
    DELETE /api/maintenance/tasks/{tid}                  delete a task
    POST   /api/maintenance/machines/{id}/files          upload a plan/archive
    GET    /api/maintenance/files/{fid}                  proxy the stored bytes
    DELETE /api/maintenance/files/{fid}                  delete a file
    GET    /api/maintenance/machines/{id}/sheet.pdf      printable KW/day sheet
"""
from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_db_session
from app.models import Machine, MaintenanceFile, MaintenanceTask
from app.schemas.maintenance import (
    FileKind,
    MachineDetail,
    MachineIn,
    MachineOut,
    MachinePatch,
    TaskIn,
    TaskOut,
    TaskPatch,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.maintenance_files import (
    fetch_directus_asset,
    upload_maintenance_file_to_directus,
)
from app.services.maintenance_pdf import generate_maintenance_pdf

router = APIRouter(
    prefix="/api/maintenance",
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

# ext -> canonical content-type accepted for plan/archive uploads.
_ALLOWED: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
}


def _ext(filename: str) -> str:
    return ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


def _safe_filename(stem: str) -> str:
    keep = "".join(ch if (ch.isalnum() or ch in " _-") else "_" for ch in stem)
    return keep.strip().replace(" ", "_") or "Wartungsnachweis"


async def _get_machine(db: AsyncSession, machine_id: uuid.UUID) -> Machine:
    machine = await db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="machine not found")
    return machine


# ── Machines ────────────────────────────────────────────────────────────


@router.post("/machines", response_model=MachineOut, status_code=201)
async def create_machine(
    payload: MachineIn,
    db: AsyncSession = Depends(get_async_db_session),
) -> Machine:
    machine = Machine(**payload.model_dump())
    db.add(machine)
    await db.commit()
    await db.refresh(machine)
    return machine


@router.get("/machines", response_model=list[MachineOut])
async def list_machines(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[Machine]:
    result = await db.execute(sa.select(Machine).order_by(Machine.name))
    return list(result.scalars().all())


@router.get("/machines/{machine_id}", response_model=MachineDetail)
async def get_machine(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Machine:
    result = await db.execute(
        sa.select(Machine)
        .where(Machine.id == machine_id)
        .options(selectinload(Machine.tasks), selectinload(Machine.files))
    )
    machine = result.scalar_one_or_none()
    if machine is None:
        raise HTTPException(status_code=404, detail="machine not found")
    return machine


@router.patch("/machines/{machine_id}", response_model=MachineOut)
async def patch_machine(
    machine_id: uuid.UUID,
    patch: MachinePatch,
    db: AsyncSession = Depends(get_async_db_session),
) -> Machine:
    machine = await _get_machine(db, machine_id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(machine, field, value)
    await db.commit()
    await db.refresh(machine)
    return machine


@router.delete("/machines/{machine_id}", status_code=204)
async def delete_machine(
    machine_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    machine = await _get_machine(db, machine_id)
    await db.delete(machine)
    await db.commit()
    return Response(status_code=204)


# ── Tasks ───────────────────────────────────────────────────────────────


@router.post(
    "/machines/{machine_id}/tasks", response_model=TaskOut, status_code=201
)
async def create_task(
    machine_id: uuid.UUID,
    payload: TaskIn,
    db: AsyncSession = Depends(get_async_db_session),
) -> MaintenanceTask:
    await _get_machine(db, machine_id)
    task = MaintenanceTask(machine_id=machine_id, **payload.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def patch_task(
    task_id: uuid.UUID,
    patch: TaskPatch,
    db: AsyncSession = Depends(get_async_db_session),
) -> MaintenanceTask:
    task = await db.get(MaintenanceTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    # Keep interval_weeks consistent with interval_type after the patch.
    if task.interval_type != "interval_weeks":
        task.interval_weeks = None
    elif task.interval_weeks is None:
        raise HTTPException(
            status_code=422,
            detail="interval_weeks is required when interval_type is 'interval_weeks'",
        )
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    task = await db.get(MaintenanceTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    await db.delete(task)
    await db.commit()
    return Response(status_code=204)


# ── Files ───────────────────────────────────────────────────────────────


@router.post(
    "/machines/{machine_id}/files", response_model=MachineDetail, status_code=201
)
async def upload_file(
    machine_id: uuid.UUID,
    file: UploadFile = File(...),
    file_kind: FileKind = Form(default="plan"),
    db: AsyncSession = Depends(get_async_db_session),
) -> Machine:
    """Upload a reference plan (``plan``) or a signed, scanned-back sheet
    (``archive``); stream it into Directus and attach it to the machine."""
    await _get_machine(db, machine_id)
    filename = file.filename or ""
    ext = _ext(filename)
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=422,
            detail="Nur PDF, Bilder (PNG/JPG), Excel oder Word werden akzeptiert.",
        )
    content_type = _ALLOWED[ext]

    async def _body_iter():
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    directus_uuid, _total = await upload_maintenance_file_to_directus(
        filename=filename or f"plan{ext}",
        content_type=content_type,
        body_stream=_body_iter(),
    )

    db.add(
        MaintenanceFile(
            machine_id=machine_id,
            directus_file_uuid=directus_uuid,
            filename=filename or f"plan{ext}",
            mime_type=content_type,
            file_kind=file_kind,
        )
    )
    await db.commit()
    return await get_machine(machine_id, db)


@router.get("/files/{file_id}")
async def download_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Proxy the stored file bytes from Directus to the authenticated SPA."""
    mf = await db.get(MaintenanceFile, file_id)
    if mf is None:
        raise HTTPException(status_code=404, detail="file not found")
    content, content_type = await fetch_directus_asset(mf.directus_file_uuid)
    return Response(
        content=content,
        media_type=mf.mime_type or content_type,
        headers={
            "Content-Disposition": f'inline; filename="{_safe_filename(mf.filename)}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete("/files/{file_id}", status_code=204)
async def delete_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    mf = await db.get(MaintenanceFile, file_id)
    if mf is None:
        raise HTTPException(status_code=404, detail="file not found")
    await db.delete(mf)
    await db.commit()
    return Response(status_code=204)


# ── Printable sheet ──────────────────────────────────────────────────────


@router.get("/machines/{machine_id}/sheet.pdf")
async def machine_sheet_pdf(
    machine_id: uuid.UUID,
    year: int | None = Query(default=None, ge=2000, le=2100),
    half: int = Query(default=0, ge=0, le=2),
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Generate the printable Wartungsnachweis (KW sheet + optional day sheet).

    ``year`` defaults to the current year; ``half`` (1 or 2) defaults to the
    half-year the current date falls in.
    """
    result = await db.execute(
        sa.select(Machine)
        .where(Machine.id == machine_id)
        .options(selectinload(Machine.tasks))
    )
    machine = result.scalar_one_or_none()
    if machine is None:
        raise HTTPException(status_code=404, detail="machine not found")

    today = date.today()
    resolved_year = year or today.year
    resolved_half = half or (1 if today.month <= 6 else 2)

    pdf = await generate_maintenance_pdf(
        machine, machine.tasks, resolved_year, resolved_half
    )
    fname = _safe_filename(
        f"Wartungsnachweis_{machine.name}_{resolved_year}_H{resolved_half}"
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'},
    )
