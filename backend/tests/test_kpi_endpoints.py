"""Integration tests for /api/kpis with comparison query params.

Covers every response branch of the summary endpoint extended in Plan 08-02:

  1. Baseline (no prev_* params)               -> previous_period/year both None
  2. Both comparisons present + populated      -> all three objects populated
  3. Half-specified prev_period window          -> previous_period None
  4. Prev window matching zero rows              -> previous_period None (DELTA-05)
  5. Prev window where every row has total_value <= 0 -> previous_period None
     (WHERE total_value > 0 filter kicks in and drops the window to zero rows)

Tests seed into far-future 2099+ windows so the shared dev database's real
2026 data cannot contaminate bounded assertions. Each test uses a unique
batch filename + order_number prefix to guarantee test isolation even under
repeated runs.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import SalesRecord, UploadBatch

pytestmark = pytest.mark.asyncio


async def _seed(prefix: str, rows: list[tuple[date, Decimal]]) -> int:
    async with AsyncSessionLocal() as session:
        batch = UploadBatch(
            filename=f"{prefix}.csv",
            uploaded_at=datetime.now(timezone.utc),
            row_count=len(rows),
            error_count=0,
            status="success",
        )
        session.add(batch)
        await session.flush()
        for idx, (d, v) in enumerate(rows):
            session.add(
                SalesRecord(
                    upload_batch_id=batch.id,
                    order_number=f"{prefix}-{idx}",
                    order_date=d,
                    total_value=v,
                )
            )
        await session.commit()
        return batch.id


async def _cleanup(batch_id: int) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(SalesRecord).where(SalesRecord.upload_batch_id == batch_id)
        )
        await session.execute(delete(UploadBatch).where(UploadBatch.id == batch_id))
        await session.commit()


async def test_summary_baseline_no_prev_params(viewer_client):
    """No prev_* query params -> previous_period and previous_year both None (DELTA-04)."""
    bid = await _seed(
        "summary-baseline",
        [
            (date(2099, 4, 5), Decimal("100")),
            (date(2099, 4, 15), Decimal("200")),
        ],
    )
    try:
        res = await viewer_client.get(
            "/api/kpis",
            params={"start_date": "2099-04-01", "end_date": "2099-04-30"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total_orders"] == 2
        assert Decimal(body["total_revenue"]) == Decimal("300")
        assert Decimal(body["avg_order_value"]) == Decimal("150")
        assert body["previous_period"] is None
        assert body["previous_year"] is None
    finally:
        await _cleanup(bid)


async def test_summary_with_both_prev_periods_populated(viewer_client):
    """prev_period + prev_year windows both hit rows -> all three objects populated."""
    bid = await _seed(
        "summary-both",
        [
            # Current: Apr 2099
            (date(2099, 4, 5), Decimal("100")),
            (date(2099, 4, 15), Decimal("300")),
            # Prev period: Mar 2099
            (date(2099, 3, 10), Decimal("50")),
            (date(2099, 3, 20), Decimal("150")),
            # Prev year: Apr 2098
            (date(2098, 4, 5), Decimal("80")),
            (date(2098, 4, 15), Decimal("120")),
        ],
    )
    try:
        res = await viewer_client.get(
            "/api/kpis",
            params={
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                "prev_period_start": "2099-03-01",
                "prev_period_end": "2099-03-31",
                "prev_year_start": "2098-04-01",
                "prev_year_end": "2098-04-30",
            },
        )
        assert res.status_code == 200
        body = res.json()

        # Current window: 100 + 300 = 400, avg 200, 2 orders
        assert body["total_orders"] == 2
        assert Decimal(body["total_revenue"]) == Decimal("400")
        assert Decimal(body["avg_order_value"]) == Decimal("200")

        # Previous period (Mar 2099): 50 + 150 = 200, avg 100, 2 orders
        assert body["previous_period"] is not None
        assert body["previous_period"]["total_orders"] == 2
        assert Decimal(body["previous_period"]["total_revenue"]) == Decimal("200")
        assert Decimal(body["previous_period"]["avg_order_value"]) == Decimal("100")

        # Previous year (Apr 2098): 80 + 120 = 200, avg 100, 2 orders
        assert body["previous_year"] is not None
        assert body["previous_year"]["total_orders"] == 2
        assert Decimal(body["previous_year"]["total_revenue"]) == Decimal("200")
        assert Decimal(body["previous_year"]["avg_order_value"]) == Decimal("100")
    finally:
        await _cleanup(bid)


async def test_summary_with_half_prev_period_params_returns_null(viewer_client):
    """Only one of prev_period_start/prev_period_end -> previous_period is None.

    Half-specified windows are invalid; endpoint must not try to aggregate with
    an open-ended bound that would silently change meaning.
    """
    bid = await _seed(
        "summary-half",
        [
            (date(2099, 4, 5), Decimal("100")),
            (date(2099, 3, 5), Decimal("999")),  # would match if open-ended
        ],
    )
    try:
        res = await viewer_client.get(
            "/api/kpis",
            params={
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                # Only prev_period_start, no prev_period_end
                "prev_period_start": "2099-03-01",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["previous_period"] is None
        assert body["previous_year"] is None
    finally:
        await _cleanup(bid)


async def test_summary_prev_window_with_zero_rows_returns_null_not_zero_object(viewer_client):
    """DELTA-05 invariant: a prev window with zero matching rows returns None.

    Specifically NOT a zero-filled object like {"total_revenue": 0, ...} —
    that would be indistinguishable from a legitimate zero-revenue window and
    break the frontend's em-dash fallback (CARD-04).
    """
    bid = await _seed(
        "summary-zero-rows",
        [
            (date(2099, 4, 5), Decimal("100")),
            (date(2099, 4, 15), Decimal("200")),
        ],
    )
    try:
        res = await viewer_client.get(
            "/api/kpis",
            params={
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                # Feb 2099 has zero seeded rows
                "prev_period_start": "2099-02-01",
                "prev_period_end": "2099-02-28",
            },
        )
        assert res.status_code == 200
        body = res.json()
        # Must be exactly None — NOT a zero-valued object
        assert body["previous_period"] is None
        # And current window is still populated
        assert body["total_orders"] == 2
    finally:
        await _cleanup(bid)


async def test_summary_ignores_zero_or_negative_rows_in_comparison(viewer_client):
    """Prev window with only total_value <= 0 rows -> filter drops all, None.

    The WHERE total_value > 0 filter from the helper applies uniformly to
    every window. A prev window that only contains a negative and a zero row
    should therefore collapse to zero matching rows -> None.
    """
    bid = await _seed(
        "summary-filter",
        [
            # Current (Apr 2099): two positive rows so top-level is populated
            (date(2099, 4, 5), Decimal("100")),
            (date(2099, 4, 15), Decimal("200")),
            # Prev period (Feb 2099): only rows that the >0 filter excludes
            (date(2099, 2, 10), Decimal("-10")),
            (date(2099, 2, 20), Decimal("0")),
        ],
    )
    try:
        res = await viewer_client.get(
            "/api/kpis",
            params={
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                "prev_period_start": "2099-02-01",
                "prev_period_end": "2099-02-28",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total_orders"] == 2
        assert body["previous_period"] is None
    finally:
        await _cleanup(bid)
