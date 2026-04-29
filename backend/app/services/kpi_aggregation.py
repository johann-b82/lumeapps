"""Generic KPI aggregation helper for the summary and chart endpoints.

Single source of truth for the (total_revenue, avg_order_value, total_orders)
triple computed by /api/kpis and /api/kpis/chart. Isolating pure SQL from
endpoint wiring lets us unit-test the aggregation independently of FastAPI,
query-param parsing, and response serialization — and guarantees that the
current window, previous_period window, and previous_year window all go
through the exact same SQL, so delta semantics can never drift between the
card overlay and the chart overlay (Phase 8 SC5).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SalesRecord


async def aggregate_kpi_summary(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict | None:
    """Aggregate KPI totals over sales_records for an optional date window.

    Mirrors the ``WHERE total_value > 0`` filter from the legacy summary
    endpoint (``routers/kpis.py``) so every comparison window is semantically
    identical to the current window.

    Args:
        session: Async SQLAlchemy session bound to the asyncpg engine.
        start_date: Inclusive lower bound on ``SalesRecord.order_date``. When
            ``None`` the lower bound is omitted (all-time / open-left).
        end_date: Inclusive upper bound on ``SalesRecord.order_date``. When
            ``None`` the upper bound is omitted (all-time / open-right).

    Returns:
        A dict with keys ``total_revenue`` (Decimal), ``avg_order_value``
        (Decimal), and ``total_orders`` (int) when at least one row matches.
        Returns ``None`` when zero rows match — this distinguishes "no data"
        from "legitimate zero" per DELTA-05. Callers serialize ``None`` to
        the nullable ``previous_period`` / ``previous_year`` field on the
        summary response, or to a ``null`` chart series.
    """
    stmt = (
        select(
            func.sum(SalesRecord.total_value).label("total_revenue"),
            func.avg(SalesRecord.total_value).label("avg_order_value"),
            func.count(SalesRecord.id).label("total_orders"),
        )
        .where(SalesRecord.total_value > 0)
    )
    if start_date is not None:
        stmt = stmt.where(SalesRecord.order_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(SalesRecord.order_date <= end_date)

    row = (await session.execute(stmt)).one()
    if (row.total_orders or 0) == 0:
        return None
    return {
        "total_revenue": row.total_revenue or Decimal("0"),
        "avg_order_value": row.avg_order_value or Decimal("0"),
        "total_orders": int(row.total_orders),
    }
