"""FAIR router — drawing ballooning / Erstmusterprüfung (v1.63, admin-only).

All endpoints are admin-gated (upload + persistence + Directus proxy). Routes:

    POST   /api/fair/projects                 upload a drawing (PDF/PNG/JPG)
    GET    /api/fair/projects                 list projects
    GET    /api/fair/projects/{id}            project + its balloons
    PATCH  /api/fair/projects/{id}            rename / set page_count
    DELETE /api/fair/projects/{id}            delete project (cascade balloons)
    GET    /api/fair/projects/{id}/file       proxy the stored drawing bytes
    POST   /api/fair/projects/{id}/balloons   add a balloon (server numbers it)
    PATCH  /api/fair/balloons/{bid}           move bubble / edit value / re-page
    DELETE /api/fair/balloons/{bid}           delete + renumber remaining

Geometry is normalized [0,1]; the arrow tip is the region centre (derived on
the client). ``number`` is server-assigned and kept contiguous.

Compute-justified: clause 1 (file I/O + atomic renumber) — persists and proxies
uploaded drawing bytes and keeps server-assigned balloon numbers contiguous
across add/delete; not a plain Directus collection read.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_db_session
from app.models import FairBalloon, FairProject
from app.schemas.fair import (
    BalloonIn,
    BalloonOut,
    BalloonPatch,
    BalloonReorder,
    ProjectDetail,
    ProjectOut,
    ProjectPatch,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.fair_files import (
    fetch_directus_asset,
    upload_drawing_to_directus,
)

router = APIRouter(
    prefix="/api/fair",
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

# ext -> (file_kind, canonical content-type sent to Directus)
_ALLOWED: dict[str, tuple[str, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
}


def _ext(filename: str) -> str:
    return ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> FairProject:
    project = await db.get(FairProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


# ── Projects ────────────────────────────────────────────────────────────


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    file: UploadFile = File(...),
    name: str | None = Form(default=None, max_length=255),
    db: AsyncSession = Depends(get_async_db_session),
) -> FairProject:
    """Upload a drawing, stream it into Directus, persist a project row."""
    filename = file.filename or ""
    ext = _ext(filename)
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=422,
            detail="Unsupported file type. Only PDF, PNG and JPG drawings are accepted.",
        )
    file_kind, content_type = _ALLOWED[ext]

    async def _body_iter():
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    directus_uuid, _total = await upload_drawing_to_directus(
        filename=filename or f"drawing{ext}",
        content_type=content_type,
        body_stream=_body_iter(),
    )

    project = FairProject(
        name=(name or filename.rsplit(".", 1)[0] or "Zeichnung"),
        directus_file_uuid=directus_uuid,
        file_kind=file_kind,
        mime_type=content_type,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[FairProject]:
    result = await db.execute(
        sa.select(FairProject).order_by(FairProject.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> FairProject:
    result = await db.execute(
        sa.select(FairProject)
        .where(FairProject.id == project_id)
        .options(selectinload(FairProject.balloons))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def patch_project(
    project_id: uuid.UUID,
    patch: ProjectPatch,
    db: AsyncSession = Depends(get_async_db_session),
) -> FairProject:
    project = await _get_project(db, project_id)
    data = patch.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    project = await _get_project(db, project_id)
    await db.delete(project)
    await db.commit()
    return Response(status_code=204)


@router.get("/projects/{project_id}/file")
async def get_project_file(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Proxy the stored drawing bytes from Directus to the authenticated SPA."""
    project = await _get_project(db, project_id)
    content, content_type = await fetch_directus_asset(project.directus_file_uuid)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


# ── Balloons ────────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/balloons", response_model=BalloonOut, status_code=201
)
async def create_balloon(
    project_id: uuid.UUID,
    payload: BalloonIn,
    db: AsyncSession = Depends(get_async_db_session),
) -> FairBalloon:
    await _get_project(db, project_id)
    next_number = (
        await db.execute(
            sa.select(sa.func.coalesce(sa.func.max(FairBalloon.number), 0)).where(
                FairBalloon.project_id == project_id
            )
        )
    ).scalar_one() + 1

    balloon = FairBalloon(
        project_id=project_id,
        number=next_number,
        **payload.model_dump(),
    )
    db.add(balloon)
    await db.commit()
    await db.refresh(balloon)
    return balloon


@router.post(
    "/projects/{project_id}/balloons/reorder", response_model=list[BalloonOut]
)
async def reorder_balloons(
    project_id: uuid.UUID,
    payload: BalloonReorder,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[FairBalloon]:
    """Renumber a project's balloons 1..n in the given id order (drag & drop)."""
    await _get_project(db, project_id)
    rows = (
        (
            await db.execute(
                sa.select(FairBalloon).where(FairBalloon.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )
    by_id = {b.id: b for b in rows}
    if set(payload.ordered_ids) != set(by_id.keys()):
        raise HTTPException(
            status_code=400,
            detail="ordered_ids must list exactly the project's balloons",
        )
    ordered = [by_id[bid] for bid in payload.ordered_ids]
    # Two-phase offset keeps the (project_id, number) unique constraint satisfied.
    for offset, b in enumerate(ordered):
        b.number = 1_000_001 + offset
    await db.flush()
    for final, b in enumerate(ordered, start=1):
        b.number = final
    await db.commit()
    return ordered


@router.get("/balloons/{balloon_id}", response_model=BalloonOut)
async def get_balloon(
    balloon_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> FairBalloon:
    """Fetch a single balloon (used by the table's per-row reload)."""
    balloon = await db.get(FairBalloon, balloon_id)
    if balloon is None:
        raise HTTPException(status_code=404, detail="balloon not found")
    return balloon


@router.patch("/balloons/{balloon_id}", response_model=BalloonOut)
async def patch_balloon(
    balloon_id: uuid.UUID,
    patch: BalloonPatch,
    db: AsyncSession = Depends(get_async_db_session),
) -> FairBalloon:
    balloon = await db.get(FairBalloon, balloon_id)
    if balloon is None:
        raise HTTPException(status_code=404, detail="balloon not found")
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(balloon, field, value)
    await db.commit()
    await db.refresh(balloon)
    return balloon


@router.delete("/balloons/{balloon_id}", status_code=204)
async def delete_balloon(
    balloon_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    balloon = await db.get(FairBalloon, balloon_id)
    if balloon is None:
        raise HTTPException(status_code=404, detail="balloon not found")
    project_id = balloon.project_id
    await db.delete(balloon)
    await db.flush()

    # Renumber the survivors to 1..n. Two passes with a high temporary offset
    # keep the (project_id, number) unique constraint satisfied at every step
    # (a naive in-place shift can transiently collide).
    survivors = (
        (
            await db.execute(
                sa.select(FairBalloon)
                .where(FairBalloon.project_id == project_id)
                .order_by(FairBalloon.number)
            )
        )
        .scalars()
        .all()
    )
    for offset, b in enumerate(survivors):
        b.number = 1_000_001 + offset
    await db.flush()
    for final, b in enumerate(survivors, start=1):
        b.number = final
    await db.commit()
    return Response(status_code=204)
