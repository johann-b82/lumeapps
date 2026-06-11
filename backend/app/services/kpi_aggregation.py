"""KPI aggregation helpers for the Sales dashboard summary + chart.

Two compute paths feed the headline KPI tiles:

1. ``aggregate_kpi_summary`` — orders-side metrics from ``sales_records``:
   ``avg_order_value`` and ``total_orders``. (Pre-v1.53 this fn also
   returned ``total_revenue`` from the same source; that field moved to
   ``aggregate_revenue_summary`` when the dashboard's "Auftragswert" tile
   was renamed "Umsatz" and re-sourced from RG/GS invoice data.)

2. ``aggregate_revenue_summary`` — net Umsatz from the ``revenues`` table
   (RG = Rechnung, GS = Gutschrift with negative wert_eur). A simple
   ``SUM(wert_eur)`` over a date window yields net revenue including
   credit-note deductions.

Isolating these as pure-SQL helpers lets us reuse the same code for the
current window, previous_period window, and previous_year window without
drift (Phase 8 SC5).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Auftrag, Revenue


async def aggregate_kpi_summary(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict | None:
    """Aggregate order-side KPI totals over the ``auftraege`` table.

    v1.54: source switched from ``sales_records`` (60-col legacy export)
    to ``auftraege`` (18-col ``AswKpf_AUF.txt`` export). Excludes €0
    rows from the headline metrics, matching the legacy ``total_value > 0``
    behaviour so storno / null-value rows don't distort the average.

    Returns ``None`` when zero rows match, to distinguish "no data" from
    a legitimate zero per DELTA-05.
    """
    stmt = (
        select(
            func.sum(Auftrag.wert_eur).label("total_revenue"),
            func.avg(Auftrag.wert_eur).label("avg_order_value"),
            func.count(Auftrag.vorgang_nr).label("total_orders"),
        )
        .where(Auftrag.wert_eur > 0)
    )
    if start_date is not None:
        stmt = stmt.where(Auftrag.datum >= start_date)
    if end_date is not None:
        stmt = stmt.where(Auftrag.datum <= end_date)

    row = (await session.execute(stmt)).one()
    if (row.total_orders or 0) == 0:
        return None
    return {
        "total_revenue": row.total_revenue or Decimal("0"),
        "avg_order_value": row.avg_order_value or Decimal("0"),
        "total_orders": int(row.total_orders),
    }


async def aggregate_revenue_summary(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Decimal | None:
    """Net Umsatz from the ``revenues`` table for an optional date window.

    Sums ``wert_eur`` across RG (Rechnung) and GS (Gutschrift) rows. GS
    rows carry a negative value, so the sum yields net revenue including
    credit-note deductions. Returns ``None`` when zero rows match so the
    caller can distinguish "no data" from a legitimate zero (DELTA-05).
    """
    stmt = select(func.sum(Revenue.wert_eur), func.count(Revenue.vorgang_nr))
    if start_date is not None:
        stmt = stmt.where(Revenue.datum >= start_date)
    if end_date is not None:
        stmt = stmt.where(Revenue.datum <= end_date)

    row = (await session.execute(stmt)).one()
    total, n = row[0], row[1]
    if (n or 0) == 0:
        return None
    return total or Decimal("0")
