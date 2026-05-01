"""Sales KPI compute endpoints (v1.41)."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.schemas import ContactsWeeklyResponse, OrdersDistributionResponse
from app.security.directus_auth import get_current_user
from app.services.sales_kpi_aggregation import (
    compute_contacts_weekly,
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
