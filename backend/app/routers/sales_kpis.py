"""Sales KPI compute endpoints (v1.41).

Compute-justified: clause 1 (server-side ISO-week aggregation across
sales_contacts + sales_records — Directus collections do not support
the JOIN through the alias table or the Kommentar→order_number bridge
needed for orders_per_week_per_rep).
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Literal

from app.database import get_async_db_session
from app.schemas import (
    ContactsWeeklyResponse,
    CustomerShareResponse,
    OrdersDistributionResponse,
)
from app.security.directus_auth import get_current_user
from app.services.sales_kpi_aggregation import (
    compute_contacts_weekly,
    compute_customer_share,
    compute_orders_distribution,
)

router = APIRouter(
    prefix="/api/data/sales",
    dependencies=[Depends(get_current_user)],
    tags=["sales-kpis"],
)


def _default_range() -> tuple[date, date]:
    """Default = last 12 ISO weeks, ending in the current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return (monday - timedelta(weeks=11), monday + timedelta(days=6))


@router.get("/contacts-weekly", response_model=ContactsWeeklyResponse)
async def contacts_weekly(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_async_db_session),
) -> ContactsWeeklyResponse:
    if not date_from or not date_to:
        d_from, d_to = _default_range()
        date_from = date_from or d_from
        date_to = date_to or d_to
    payload = await compute_contacts_weekly(db, date_from, date_to)
    return ContactsWeeklyResponse(**payload)


@router.get("/orders-distribution", response_model=OrdersDistributionResponse)
async def orders_distribution(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_async_db_session),
) -> OrdersDistributionResponse:
    if not date_from or not date_to:
        d_from, d_to = _default_range()
        date_from = date_from or d_from
        date_to = date_to or d_to
    payload = await compute_orders_distribution(db, date_from, date_to)
    return OrdersDistributionResponse(**payload)


@router.get("/customer-share", response_model=CustomerShareResponse)
async def customer_share(
    source: Literal["auftraege", "revenues"] = Query(...),
    top_n: int = Query(14, ge=1, le=50),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_async_db_session),
) -> CustomerShareResponse:
    """Top-N customer share from either ``auftraege`` or ``revenues``.

    Used twice on the dashboard — one card per source — so a single
    parametrised endpoint keeps the SQL DRY. ``top_n`` defaults to 14
    (matches the Kundenanteil waterfall card's expand-to-14 toggle);
    range-checked 1..50 to bound the response shape.
    """
    if not date_from or not date_to:
        d_from, d_to = _default_range()
        date_from = date_from or d_from
        date_to = date_to or d_to
    payload = await compute_customer_share(db, source, date_from, date_to, top_n)
    return CustomerShareResponse(source=source, top_n=top_n, **payload)
