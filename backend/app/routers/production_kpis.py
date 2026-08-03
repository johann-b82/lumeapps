"""Produktion (production) KPI endpoints (v1.76).

First section: "Aufträge in Verzug (Seriengeschäft)" — the share of
Seriengeschäft orders whose latest Lieferschein-Lieferdatum overran the
order's confirmed Lieferdatum (Zieltermin). The planned second section
("Aufträge mit Verzugsgefahr") docks onto this router later.

Router-level viewer gate per CLAUDE.md §"Auth gate placement". The admin
write path (AswKpf_AUF / AswKpf_LS uploads) lives in the uploads router.

Compute-justified: clause 2 (server-side aggregation) — the Verzug rate is
computed by joining ``auftraege`` and ``delivery_records`` and cannot be served
as a plain Directus collection read.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.routers.hr_kpis import _bucket_windows, _validate_range
from app.schemas import (
    ProductionOverdueRow,
    ProductionVerzugHistoryPoint,
    ProductionVerzugRow,
    ProductionVerzugValue,
)
from app.security.directus_auth import require_dashboard_read
from app.services.hr_kpi_aggregation import _month_bounds
from app.services.production_kpi_aggregation import (
    compute_verzug,
    compute_verzug_history,
    list_overdue_open,
    list_verzug,
)


router = APIRouter(
    prefix="/api/production",
    tags=["production-kpis"],
    dependencies=[Depends(require_dashboard_read)],
)


@router.get("/verzug", response_model=ProductionVerzugValue)
async def get_verzug(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> ProductionVerzugValue:
    """Share of Seriengeschäft orders delivered after their Zieltermin."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    payload = await compute_verzug(db, date_from, date_to)
    return ProductionVerzugValue(**payload)


@router.get("/verzug/history", response_model=list[ProductionVerzugHistoryPoint])
async def get_verzug_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    granularity: str | None = Query(
        None,
        description=(
            "Override the auto-picked bucket granularity. "
            "Allowed: weekly, monthly, quarterly, yearly. Omit for auto."
        ),
    ),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[ProductionVerzugHistoryPoint]:
    """Verzug rate per time bucket over the window."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    buckets = _bucket_windows(date_from, date_to, granularity)
    points = await compute_verzug_history(db, buckets)
    return [ProductionVerzugHistoryPoint(**p) for p in points]


@router.get("/verzug/list", response_model=list[ProductionVerzugRow])
async def get_verzug_list(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[ProductionVerzugRow]:
    """Orders in Verzug in the window — the list behind the headline number."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_verzug(db, date_from, date_to)
    return [ProductionVerzugRow(**r) for r in rows]


@router.get("/verzug/overdue", response_model=list[ProductionOverdueRow])
async def get_verzug_overdue(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[ProductionOverdueRow]:
    """Open & overdue orders (no Lieferschein, Zieltermin in window and past)."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_overdue_open(db, date_from, date_to)
    return [ProductionOverdueRow(**r) for r in rows]
