"""Einkauf (procurement) KPI endpoints (v1.60).

First section: Liefertermintreue / OTD. The two planned sections (On Quality
Werkbänke, Material Lieferanten) dock onto this router later.

Router-level viewer gate per CLAUDE.md §"Auth gate placement". The admin
write path (file upload) lives in the uploads router.

Compute-justified: clause 2 (server-side aggregation) — the OTD rate, history
buckets, and verification list are computed over ``delivery_reliability`` and
cannot be served as a plain Directus collection read.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.routers.hr_kpis import _bucket_windows, _validate_range
from app.schemas import OtdHistoryPoint, OtdRow, OtdValue
from app.security.directus_auth import get_current_user
from app.services.hr_kpi_aggregation import _month_bounds
from app.services.otd_aggregation import (
    compute_otd,
    compute_otd_history,
    list_otd,
)


router = APIRouter(
    prefix="/api/procurement",
    tags=["procurement-kpis"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/otd", response_model=OtdValue)
async def get_otd(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> OtdValue:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    payload = await compute_otd(db, date_from, date_to)
    return OtdValue(**payload)


@router.get("/otd/history", response_model=list[OtdHistoryPoint])
async def get_otd_history(
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
) -> list[OtdHistoryPoint]:
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    buckets = _bucket_windows(date_from, date_to, granularity)
    points = await compute_otd_history(db, buckets)
    return [OtdHistoryPoint(**p) for p in points]


@router.get("/otd/list", response_model=list[OtdRow])
async def get_otd_list(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[OtdRow]:
    """Delivery positions for the verification table under the OTD chart."""
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    rows = await list_otd(db, date_from, date_to)
    return [OtdRow.model_validate(r) for r in rows]
