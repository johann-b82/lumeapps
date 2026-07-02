"""Finanzperspektive (finance) KPI endpoints (v1.63).

Sections: Materialkostenquote (material cost / revenue) and Personalkostenquote
(personnel cost / revenue). Umsatzrendite docks onto this router later.

Router-level viewer gate per CLAUDE.md §"Auth gate placement". The admin write
path (file uploads) lives in the uploads router.

Compute-justified: clause 2 (server-side aggregation) — the ratio joins
``material_movements`` against the newest ``material_prices`` price and divides
by ``revenues``; it cannot be served as a plain Directus collection read.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.routers.hr_kpis import _bucket_windows, _validate_range
from app.schemas import (
    MaterialCostRatioHistoryPoint,
    MaterialCostRatioRow,
    MaterialCostRatioValue,
    PersonnelCostRatioHistoryPoint,
    PersonnelCostRatioRow,
    PersonnelCostRatioValue,
)
from app.security.directus_auth import get_current_user
from app.services.hr_kpi_aggregation import _month_bounds
from app.services.material_cost_aggregation import (
    compute_material_cost_ratio,
    compute_material_cost_ratio_history,
    list_material_cost_ratio,
)
from app.services.personnel_cost_aggregation import (
    compute_personnel_cost_ratio,
    compute_personnel_cost_ratio_history,
    list_personnel_cost_ratio,
)


router = APIRouter(
    prefix="/api/finance",
    tags=["finance-kpis"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/material-cost-ratio", response_model=MaterialCostRatioValue)
async def get_material_cost_ratio(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> MaterialCostRatioValue:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    payload = await compute_material_cost_ratio(db, date_from, date_to)
    return MaterialCostRatioValue(**payload)


@router.get(
    "/material-cost-ratio/history",
    response_model=list[MaterialCostRatioHistoryPoint],
)
async def get_material_cost_ratio_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    granularity: str | None = Query(
        None,
        description=(
            "Override the auto-picked bucket granularity. "
            "Allowed: weekly, monthly, quarterly, yearly. "
            "Omit for auto (length-based)."
        ),
    ),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[MaterialCostRatioHistoryPoint]:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    buckets = _bucket_windows(date_from, date_to, granularity)
    points = await compute_material_cost_ratio_history(db, buckets)
    return [MaterialCostRatioHistoryPoint(**p) for p in points]


@router.get(
    "/material-cost-ratio/list",
    response_model=list[MaterialCostRatioRow],
)
async def get_material_cost_ratio_list(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[MaterialCostRatioRow]:
    """Per-article breakdown for the verification table under the chart."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_material_cost_ratio(db, date_from, date_to)
    return [MaterialCostRatioRow(**r) for r in rows]


# ── Personalkostenquote (personnel cost / revenue) ──────────────────────


@router.get("/personnel-cost-ratio", response_model=PersonnelCostRatioValue)
async def get_personnel_cost_ratio(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> PersonnelCostRatioValue:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    payload = await compute_personnel_cost_ratio(db, date_from, date_to)
    return PersonnelCostRatioValue(**payload)


@router.get(
    "/personnel-cost-ratio/history",
    response_model=list[PersonnelCostRatioHistoryPoint],
)
async def get_personnel_cost_ratio_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    granularity: str | None = Query(
        None,
        description=(
            "Override the auto-picked bucket granularity. "
            "Allowed: weekly, monthly, quarterly, yearly. "
            "Omit for auto (length-based)."
        ),
    ),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[PersonnelCostRatioHistoryPoint]:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    buckets = _bucket_windows(date_from, date_to, granularity)
    points = await compute_personnel_cost_ratio_history(db, buckets)
    return [PersonnelCostRatioHistoryPoint(**p) for p in points]


@router.get(
    "/personnel-cost-ratio/list",
    response_model=list[PersonnelCostRatioRow],
)
async def get_personnel_cost_ratio_list(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[PersonnelCostRatioRow]:
    """Per-department personnel-cost breakdown for the verification table."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_personnel_cost_ratio(db, date_from, date_to)
    return [PersonnelCostRatioRow(**r) for r in rows]
