"""KPI summary + chart endpoints for the sales dashboard.

Compute-justified: clause 3 (multi-row KPI aggregation across periods).
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import require_dashboard_read
from app.models import Revenue, SalesRecord, UploadBatch
from app.schemas import (
    ChartPoint,
    ChartResponse,
    KpiSummary,
    KpiSummaryComparison,
    LatestUploadResponse,
)
from app.services.kpi_aggregation import (
    aggregate_kpi_summary,
    aggregate_revenue_summary,
)

_TRUNC_MAP: dict[str, str] = {"daily": "day", "weekly": "week", "monthly": "month"}

router = APIRouter(
    prefix="/api/kpis",
    tags=["kpis"],
    dependencies=[Depends(require_dashboard_read)],
)


@router.get("", response_model=KpiSummary)
async def get_kpi_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    prev_period_start: date | None = Query(None),
    prev_period_end: date | None = Query(None),
    prev_year_start: date | None = Query(None),
    prev_year_end: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> KpiSummary:
    """Return current-window KPI totals plus optional previous_period / previous_year siblings.

    Comparison windows are opt-in: both start+end params must be present for a
    comparison to be computed. A half-specified window (only start or only end)
    yields a ``None`` comparison object — this is intentional so Phase 9's
    preset-to-bounds mapper can cleanly emit no-comparison for presets like
    "Dieses Jahr" (per CONTEXT decision D) by omitting the params.

    All three aggregations share the same SQL helper (aggregate_kpi_summary)
    so the current and comparison windows can never drift semantically
    (Phase 8 SC5). Sequential awaits on a single AsyncSession rather than
    asyncio.gather: SQLAlchemy AsyncSession is not safe for concurrent
    execute() calls on one connection — gather() would raise InvalidRequestError
    intermittently. The latency cost is <100ms for three single-row aggregates
    and the simpler code is more robust. See 08-02 SUMMARY for details.
    """

    async def _maybe_orders(s: date | None, e: date | None) -> dict | None:
        if s is None or e is None:
            return None
        return await aggregate_kpi_summary(db, s, e)

    async def _maybe_umsatz(s: date | None, e: date | None) -> Decimal | None:
        if s is None or e is None:
            return None
        return await aggregate_revenue_summary(db, s, e)

    # avg_order_value + total_orders stay sourced from sales_records.
    # total_revenue (= Umsatz) moves to the revenues table (v1.53).
    current_orders = await aggregate_kpi_summary(db, start_date, end_date)
    current_umsatz = await aggregate_revenue_summary(db, start_date, end_date)
    prev_period_orders = await _maybe_orders(prev_period_start, prev_period_end)
    prev_period_umsatz = await _maybe_umsatz(prev_period_start, prev_period_end)
    prev_year_orders = await _maybe_orders(prev_year_start, prev_year_end)
    prev_year_umsatz = await _maybe_umsatz(prev_year_start, prev_year_end)

    if current_orders is None:
        current_orders = {"avg_order_value": Decimal("0"), "total_orders": 0}

    def _merge(orders: dict | None, umsatz: Decimal | None) -> dict | None:
        # Mirror the legacy DELTA-05 null-safety: a comparison window is
        # only emitted when at least one of its two sources has data.
        if orders is None and umsatz is None:
            return None
        return {
            "total_revenue": umsatz if umsatz is not None else Decimal("0"),
            "avg_order_value": (orders or {}).get("avg_order_value", Decimal("0")),
            "total_orders": (orders or {}).get("total_orders", 0),
        }

    prev_period = _merge(prev_period_orders, prev_period_umsatz)
    prev_year = _merge(prev_year_orders, prev_year_umsatz)

    return KpiSummary(
        total_revenue=current_umsatz if current_umsatz is not None else Decimal("0"),
        avg_order_value=current_orders["avg_order_value"],
        total_orders=current_orders["total_orders"],
        previous_period=KpiSummaryComparison(**prev_period) if prev_period else None,
        previous_year=KpiSummaryComparison(**prev_year) if prev_year else None,
    )


async def _bucketed_series(
    db: AsyncSession,
    start: date | None,
    end: date | None,
    granularity: Literal["daily", "weekly", "monthly"],
) -> list[tuple[date, Decimal]]:
    """Bucketed Umsatzwachstum series from the ``revenues`` table.

    v1.53: re-sourced from ``revenues`` (RG + GS) to match the renamed
    Umsatz / Umsatzwachstum KPI tiles. GS rows have negative wert_eur,
    so the SUM is net revenue per bucket.
    """
    bucket = func.date_trunc(_TRUNC_MAP[granularity], Revenue.datum).label("bucket")
    stmt = (
        select(bucket, func.sum(Revenue.wert_eur).label("revenue"))
        .group_by(bucket)
        .order_by(bucket)
    )
    if start is not None:
        stmt = stmt.where(Revenue.datum >= start)
    if end is not None:
        stmt = stmt.where(Revenue.datum <= end)

    result = await db.execute(stmt)
    return [(row.bucket.date(), row.revenue or Decimal("0")) for row in result.all()]


@router.get("/chart", response_model=ChartResponse)
async def get_chart_data(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: Literal["daily", "weekly", "monthly"] = Query("monthly"),
    prev_start: date | None = Query(None),
    prev_end: date | None = Query(None),
    comparison: Literal["previous_period", "previous_year", "none"] = Query("none"),
    db: AsyncSession = Depends(get_async_db_session),
) -> ChartResponse:
    """Return wrapped ChartResponse { current, previous }.

    Phase 8 breaking change vs. v1.1's bare ``list[ChartPoint]``. Frontend
    consumers read ``response.current`` (see plan 08-03 atomic migration).

    The optional ``previous`` series is populated only when ``comparison``
    is not ``"none"`` AND both ``prev_start`` and ``prev_end`` are present.
    Half-specified or opted-out comparisons return ``previous=null`` —
    symmetric with the summary endpoint's comparison semantics.

    Alignment strategy (CHART-01 + CHART-03): the prior series is
    positionally aligned to the current series — ``prior_rows[i]`` pairs
    with ``current_rows[i]`` and the resulting ``ChartPoint.date`` is
    rewritten to the current bucket's ISO date. When the prior window
    produces fewer buckets than the current window, trailing buckets
    emit ``revenue=None`` so Recharts renders a gap rather than a false
    zero. When the prior window produces more buckets, the excess is
    dropped because the current range is authoritative for the X axis.

    Sequential awaits (not ``asyncio.gather``) for the same SQLAlchemy
    AsyncSession safety reason documented on ``get_kpi_summary`` above.
    """
    want_prior = (
        comparison != "none"
        and prev_start is not None
        and prev_end is not None
    )

    current_rows = await _bucketed_series(db, start_date, end_date, granularity)
    prior_rows: list[tuple[date, Decimal]] | None = None
    if want_prior:
        prior_rows = await _bucketed_series(db, prev_start, prev_end, granularity)

    current = [ChartPoint(date=d.isoformat(), revenue=r) for d, r in current_rows]

    previous: list[ChartPoint] | None = None
    if prior_rows is not None:
        aligned: list[ChartPoint] = []
        for i, (current_date, _) in enumerate(current_rows):
            if i < len(prior_rows):
                aligned.append(
                    ChartPoint(date=current_date.isoformat(), revenue=prior_rows[i][1])
                )
            else:
                aligned.append(
                    ChartPoint(date=current_date.isoformat(), revenue=None)
                )
        previous = aligned

    return ChartResponse(current=current, previous=previous)


@router.get("/latest-upload", response_model=LatestUploadResponse)
async def get_latest_upload(
    db: AsyncSession = Depends(get_async_db_session),
) -> LatestUploadResponse:
    result = await db.execute(select(func.max(UploadBatch.uploaded_at)))
    ts = result.scalar()
    return LatestUploadResponse(uploaded_at=ts)
