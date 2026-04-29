"""Integration tests for /api/kpis/chart (Plan 08-03 wrapped ChartResponse).

Covers four branches of the chart endpoint:

  1. No comparison requested              -> previous is null, current populated
  2. Comparison with full prior data      -> previous aligned positionally to current
  3. Comparison with partial prior data   -> trailing buckets emit revenue=None (CHART-03)
  4. Contract test (Phase 8 SC5)          -> sum(previous) == summary.previous_period.total_revenue

Seeds into far-future year 2099 (same pattern as 08-01/08-02) so bounded
assertions cannot collide with real 2026 data in the shared dev database.
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


async def test_chart_no_comparison_returns_previous_null(client):
    """Baseline: no comparison params -> {current: [...], previous: null}."""
    bid = await _seed(
        "chart-baseline",
        [
            (date(2099, 4, 5), Decimal("100")),
            (date(2099, 4, 10), Decimal("200")),
            (date(2099, 4, 20), Decimal("300")),
        ],
    )
    try:
        res = await client.get(
            "/api/kpis/chart",
            params={
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                "granularity": "daily",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "current" in body
        assert "previous" in body
        assert body["previous"] is None
        assert isinstance(body["current"], list)
        assert len(body["current"]) == 3
        # Concrete revenues (never None) in the current series.
        assert all(p["revenue"] is not None for p in body["current"])
        # Ordered ascending.
        dates = [p["date"] for p in body["current"]]
        assert dates == sorted(dates)
    finally:
        await _cleanup(bid)


async def test_chart_with_previous_period_returns_aligned_series(client):
    """comparison=previous_period with matching bucket counts.

    Current April 2099 (3 daily rows) + prior March 2099 (3 daily rows).
    Expect previous to have 3 points, with dates rewritten to the April
    bucket dates (positional alignment) and revenue values from March.
    """
    bid = await _seed(
        "chart-pp-aligned",
        [
            # Current: April
            (date(2099, 4, 5), Decimal("400")),
            (date(2099, 4, 10), Decimal("500")),
            (date(2099, 4, 15), Decimal("600")),
            # Prior: March
            (date(2099, 3, 3), Decimal("40")),
            (date(2099, 3, 8), Decimal("50")),
            (date(2099, 3, 12), Decimal("60")),
        ],
    )
    try:
        res = await client.get(
            "/api/kpis/chart",
            params={
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                "granularity": "daily",
                "prev_start": "2099-03-01",
                "prev_end": "2099-03-31",
                "comparison": "previous_period",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["previous"] is not None
        assert len(body["previous"]) == len(body["current"]) == 3

        # Positional alignment: prior dates rewritten to current dates.
        for cur, prev in zip(body["current"], body["previous"]):
            assert prev["date"] == cur["date"]

        # Prior revenues are the March values positionally paired with April.
        prev_revenues = [Decimal(str(p["revenue"])) for p in body["previous"]]
        assert prev_revenues == [Decimal("40"), Decimal("50"), Decimal("60")]
    finally:
        await _cleanup(bid)


async def test_chart_partial_prior_data_emits_nulls(client):
    """CHART-03: trailing prior buckets beyond prior data emit revenue=None."""
    # Seed current window with 5 daily rows and prior with only 2 rows.
    bid = await _seed(
        "chart-partial",
        [
            # Current: April 2099 (5 buckets)
            (date(2099, 4, 1), Decimal("100")),
            (date(2099, 4, 2), Decimal("200")),
            (date(2099, 4, 3), Decimal("300")),
            (date(2099, 4, 4), Decimal("400")),
            (date(2099, 4, 5), Decimal("500")),
            # Prior: March 2099 (only 2 buckets)
            (date(2099, 3, 1), Decimal("10")),
            (date(2099, 3, 2), Decimal("20")),
        ],
    )
    try:
        res = await client.get(
            "/api/kpis/chart",
            params={
                "start_date": "2099-04-01",
                "end_date": "2099-04-30",
                "granularity": "daily",
                "prev_start": "2099-03-01",
                "prev_end": "2099-03-31",
                "comparison": "previous_period",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert len(body["current"]) == 5
        assert body["previous"] is not None
        assert len(body["previous"]) == 5

        # First 2 positions have concrete revenues from the March seed.
        assert body["previous"][0]["revenue"] is not None
        assert Decimal(str(body["previous"][0]["revenue"])) == Decimal("10")
        assert body["previous"][1]["revenue"] is not None
        assert Decimal(str(body["previous"][1]["revenue"])) == Decimal("20")

        # Trailing 3 positions are explicit null (not zero).
        for i in range(2, 5):
            assert body["previous"][i]["revenue"] is None
            # Dates still rewritten to current X-axis dates.
            assert body["previous"][i]["date"] == body["current"][i]["date"]
    finally:
        await _cleanup(bid)


async def test_chart_prior_sum_equals_summary_previous_period(client):
    """Phase 8 SC5 contract test: sum(chart.previous) == summary.previous_period.total_revenue.

    Proves "SQL reuse, no drift" (CHART-02) by running both endpoints against
    the same bounds + granularity and comparing the aggregated totals as
    exact Decimal — no pytest.approx fudge.
    """
    bid = await _seed(
        "chart-contract",
        [
            # Current: April 2099 — 4 daily buckets so positional alignment
            # has enough "slots" to hold every prior seed (no data drop).
            (date(2099, 4, 5), Decimal("123.45")),
            (date(2099, 4, 10), Decimal("200.00")),
            (date(2099, 4, 18), Decimal("678.90")),
            (date(2099, 4, 25), Decimal("300.00")),
            # Prior: March 2099 — 4 daily buckets (matched count) so sum
            # equality holds. Positional alignment will map them 1:1 into
            # the first 4 April slots. The "positional dates don't match
            # calendar dates" is intentional (see decision E in 08-CONTEXT).
            (date(2099, 3, 2), Decimal("11.11")),
            (date(2099, 3, 9), Decimal("22.22")),
            (date(2099, 3, 17), Decimal("33.33")),
            (date(2099, 3, 28), Decimal("44.44")),
        ],
    )
    try:
        # Matched seed counts (4 current daily buckets, 4 prior daily
        # buckets) so the positional alignment in get_chart_data cannot
        # drop any prior buckets. In production Phase 9 always ships
        # equal-width windows, so this mirrors real callers — and
        # exposes any SQL drift cleanly.
        common = {
            "start_date": "2099-04-01",
            "end_date": "2099-04-30",
        }

        # Summary endpoint — carries the canonical previous_period total.
        summary_res = await client.get(
            "/api/kpis",
            params={
                **common,
                "prev_period_start": "2099-03-01",
                "prev_period_end": "2099-03-31",
            },
        )
        assert summary_res.status_code == 200
        summary_body = summary_res.json()
        assert summary_body["previous_period"] is not None
        summary_prev_total = Decimal(
            str(summary_body["previous_period"]["total_revenue"])
        )

        # Chart endpoint — same bounds, daily granularity so every prior row
        # becomes its own bucket and nothing rolls up lossily.
        chart_res = await client.get(
            "/api/kpis/chart",
            params={
                **common,
                "granularity": "daily",
                "prev_start": "2099-03-01",
                "prev_end": "2099-03-31",
                "comparison": "previous_period",
            },
        )
        assert chart_res.status_code == 200
        chart_body = chart_res.json()
        assert chart_body["previous"] is not None

        chart_prev_sum = sum(
            (
                Decimal(str(p["revenue"]))
                for p in chart_body["previous"]
                if p["revenue"] is not None
            ),
            start=Decimal("0"),
        )

        # Exact equality — this is the whole point of the contract test.
        assert summary_prev_total == chart_prev_sum, (
            f"Drift detected: summary={summary_prev_total} chart_sum={chart_prev_sum}"
        )
        # And it should equal the seed total: 11.11+22.22+33.33+44.44 = 111.10
        assert summary_prev_total == Decimal("111.10")
    finally:
        await _cleanup(bid)
