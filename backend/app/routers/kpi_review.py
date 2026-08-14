"""KPI-Bewertung & Maßnahmen router (v1.107).

The KVP loop on KPIs: comment/evaluate a KPI, derive measures, assign (Personio)
and plan them, track to done. Mixed-gate router (see CLAUDE.md "Auth gate
placement"): the router-level dependency requires an authenticated user; the
GET reads are viewer-visible (the dashboards are), all writes add
``require_admin`` per route.

Viewer-readable GETs (registry, summary, comments, measures) are allowlisted in
tests/test_admin_gate_audit.py.

    GET    /api/kpi-review/registry                KPI keys + domains
    GET    /api/kpi-review/summary                 per-KPI comment/measure roll-up
    GET    /api/kpi-review/comments?kpi_key=       comments for a KPI
    POST   /api/kpi-review/comments                add a comment           (admin)
    DELETE /api/kpi-review/comments/{id}           delete a comment        (admin)
    GET    /api/kpi-review/measures?kpi_key=&status= measures (filterable)
    POST   /api/kpi-review/measures                add a measure           (admin)
    PATCH  /api/kpi-review/measures/{id}           edit / set status       (admin)
    DELETE /api/kpi-review/measures/{id}           delete a measure        (admin)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import KpiComment, KpiMeasure
from app.schemas import (
    CurrentUser,
    KpiCommentCreate,
    KpiCommentRead,
    KpiMeasureCreate,
    KpiMeasureRead,
    KpiMeasureUpdate,
    KpiRegistryItem,
    KpiSummaryItem,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.kpi_registry import KPI_REGISTRY, is_known_kpi

router = APIRouter(
    prefix="/api/kpi-review",
    tags=["kpi-review"],
    dependencies=[Depends(get_current_user)],
)

_OPEN_STATES = ("open", "in_progress")


def _require_known(kpi_key: str) -> None:
    if not is_known_kpi(kpi_key):
        raise HTTPException(status_code=422, detail=f"unknown kpi_key: {kpi_key}")


# ── Registry + summary ───────────────────────────────────────────────────
@router.get("/registry", response_model=list[KpiRegistryItem])
async def get_registry() -> list[KpiRegistryItem]:
    return [KpiRegistryItem(**item) for item in KPI_REGISTRY]


@router.get("/summary", response_model=list[KpiSummaryItem])
async def get_summary(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[KpiSummaryItem]:
    """Per-KPI roll-up over the full registry (KPIs with no activity → zeros)."""
    comment_counts = dict(
        (
            await db.execute(
                select(KpiComment.kpi_key, func.count()).group_by(KpiComment.kpi_key)
            )
        ).all()
    )
    open_counts = dict(
        (
            await db.execute(
                select(KpiMeasure.kpi_key, func.count())
                .where(KpiMeasure.status.in_(_OPEN_STATES))
                .group_by(KpiMeasure.kpi_key)
            )
        ).all()
    )
    # Latest rating per KPI (most recent comment carrying a rating).
    latest_rating: dict[str, str] = {}
    rating_rows = (
        await db.execute(
            select(KpiComment.kpi_key, KpiComment.rating, KpiComment.created_at)
            .where(KpiComment.rating.is_not(None))
            .order_by(KpiComment.created_at.desc())
        )
    ).all()
    for key, rating, _ in rating_rows:
        latest_rating.setdefault(key, rating)

    return [
        KpiSummaryItem(
            kpi_key=item["key"],
            domain=item["domain"],
            comment_count=int(comment_counts.get(item["key"], 0)),
            open_measure_count=int(open_counts.get(item["key"], 0)),
            last_rating=latest_rating.get(item["key"]),
        )
        for item in KPI_REGISTRY
    ]


# ── Comments ─────────────────────────────────────────────────────────────
@router.get("/comments", response_model=list[KpiCommentRead])
async def list_comments(
    kpi_key: str = Query(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[KpiCommentRead]:
    rows = await db.execute(
        select(KpiComment)
        .where(KpiComment.kpi_key == kpi_key)
        .order_by(KpiComment.created_at.desc())
    )
    return [KpiCommentRead.model_validate(r) for r in rows.scalars().all()]


@router.post(
    "/comments",
    response_model=KpiCommentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_comment(
    payload: KpiCommentCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> KpiCommentRead:
    _require_known(payload.kpi_key)
    has_region = None not in (
        payload.region_x, payload.region_y, payload.region_w, payload.region_h
    )
    number = None
    if has_region:
        # Contiguous bubble number per KPI (max + 1).
        current_max = (
            await db.execute(
                select(func.max(KpiComment.number)).where(
                    KpiComment.kpi_key == payload.kpi_key
                )
            )
        ).scalar()
        number = (current_max or 0) + 1
    row = KpiComment(
        kpi_key=payload.kpi_key,
        body=payload.body.strip(),
        rating=payload.rating,
        author_id=current_user.id,
        author_name=(payload.author_name or None),
        number=number,
        region_x=payload.region_x if has_region else None,
        region_y=payload.region_y if has_region else None,
        region_w=payload.region_w if has_region else None,
        region_h=payload.region_h if has_region else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return KpiCommentRead.model_validate(row)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    result = await db.execute(delete(KpiComment).where(KpiComment.id == comment_id))
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="comment not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Measures ─────────────────────────────────────────────────────────────
@router.get("/measures", response_model=list[KpiMeasureRead])
async def list_measures(
    kpi_key: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[KpiMeasureRead]:
    stmt = select(KpiMeasure)
    if kpi_key:
        stmt = stmt.where(KpiMeasure.kpi_key == kpi_key)
    if status_filter:
        stmt = stmt.where(KpiMeasure.status == status_filter)
    stmt = stmt.order_by(KpiMeasure.created_at.desc())
    rows = await db.execute(stmt)
    return [KpiMeasureRead.model_validate(r) for r in rows.scalars().all()]


@router.post(
    "/measures",
    response_model=KpiMeasureRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_measure(
    payload: KpiMeasureCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> KpiMeasureRead:
    _require_known(payload.kpi_key)
    row = KpiMeasure(
        kpi_key=payload.kpi_key,
        comment_id=payload.comment_id,
        title=payload.title.strip(),
        description=payload.description or "",
        assignee_personio_id=payload.assignee_personio_id,
        assignee_name=payload.assignee_name,
        due_date=payload.due_date,
        priority=payload.priority,
        created_by_id=current_user.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return KpiMeasureRead.model_validate(row)


@router.patch(
    "/measures/{measure_id}",
    response_model=KpiMeasureRead,
    dependencies=[Depends(require_admin)],
)
async def update_measure(
    measure_id: uuid.UUID,
    payload: KpiMeasureUpdate,
    db: AsyncSession = Depends(get_async_db_session),
) -> KpiMeasureRead:
    row = await db.get(KpiMeasure, measure_id)
    if row is None:
        raise HTTPException(status_code=404, detail="measure not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(row, field, value)
    # Stamp/clear done_at when the status crosses the done boundary.
    if "status" in data:
        row.done_at = datetime.now(timezone.utc) if data["status"] == "done" else None
    await db.commit()
    await db.refresh(row)
    return KpiMeasureRead.model_validate(row)


@router.delete(
    "/measures/{measure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_measure(
    measure_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    result = await db.execute(delete(KpiMeasure).where(KpiMeasure.id == measure_id))
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="measure not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
