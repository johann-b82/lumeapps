"""Unit tests for app.services.kpi_aggregation.aggregate_kpi_summary.

Covers the 4 semantic branches of the helper:
  1. Bounded window happy-path (rows inside + outside the window)
  2. Empty window returns None (DELTA-05 null-safety)
  3. No bounds returns all-time aggregation
  4. Zero/negative total_value rows excluded (legacy total_value > 0 filter)

Tests run against the real PostgreSQL test database via the module-level
AsyncSessionLocal factory. Each test seeds an isolated UploadBatch + its
SalesRecord children with a unique filename / order_number prefix so
parallel / sequential test isolation is guaranteed, and cleans up in a
finally block so no rows leak between tests.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import Auftrag, Revenue, UploadBatch
from app.services.kpi_aggregation import (
    aggregate_kpi_summary,
    aggregate_revenue_summary,
)

pytestmark = pytest.mark.asyncio


async def _seed(session, prefix: str, rows: list[tuple[date, Decimal]]) -> int:
    """v1.54: seed Auftrag rows (was SalesRecord pre-v1.54). Returns batch
    id for cleanup."""
    batch = UploadBatch(
        filename=f"{prefix}.txt",
        uploaded_at=datetime.now(timezone.utc),
        row_count=len(rows),
        error_count=0,
        status="success",
        kind="auftraege",
    )
    session.add(batch)
    await session.flush()
    now = datetime.now(timezone.utc)
    for idx, (d, v) in enumerate(rows):
        session.add(
            Auftrag(
                vorgang_nr=f"{prefix}-{idx}",
                typ="AUF",
                datum=d,
                wert_eur=v,
                upload_batch_id=batch.id,
                imported_at=now,
            )
        )
    await session.commit()
    return batch.id


async def _cleanup(session, batch_id: int) -> None:
    await session.execute(
        delete(Auftrag).where(Auftrag.upload_batch_id == batch_id)
    )
    await session.execute(delete(UploadBatch).where(UploadBatch.id == batch_id))
    await session.commit()


# All tests seed into far-future years (2099+) that are guaranteed to be
# outside any real uploaded data window, so bounded assertions can be exact
# regardless of other seed rows present in the shared dev database.


async def test_bounded_window_happy_path():
    """3 rows inside March window + 1 outside — only inside rows aggregated."""
    async with AsyncSessionLocal() as session:
        bid = await _seed(
            session,
            "agg-happy",
            [
                (date(2099, 3, 5), Decimal("100")),
                (date(2099, 3, 15), Decimal("200")),
                (date(2099, 3, 25), Decimal("300")),
                (date(2099, 4, 1), Decimal("999")),  # outside window
            ],
        )
        try:
            result = await aggregate_kpi_summary(
                session, date(2099, 3, 1), date(2099, 3, 31)
            )
            assert result is not None
            assert result["total_orders"] == 3
            assert result["total_revenue"] == Decimal("600")
            # Avg of 100, 200, 300 = 200
            assert result["avg_order_value"] == Decimal("200")
        finally:
            await _cleanup(session, bid)


async def test_empty_window_returns_none():
    """Zero matching rows -> None (DELTA-05: distinguishes no-data from zero)."""
    async with AsyncSessionLocal() as session:
        bid = await _seed(
            session,
            "agg-empty",
            [
                (date(2099, 4, 5), Decimal("100")),
                (date(2099, 4, 15), Decimal("200")),
            ],
        )
        try:
            # Query a far-future window with zero rows (no seeded rows and no
            # real data: the live db contains only 2026 orders).
            result = await aggregate_kpi_summary(
                session, date(2099, 2, 1), date(2099, 2, 28)
            )
            assert result is None
        finally:
            await _cleanup(session, bid)


async def test_no_bounds_returns_all_time():
    """start_date=None, end_date=None -> aggregates all matching rows.

    We can't assert an absolute total against a shared dev database that may
    already contain seed rows from other phases — instead we assert the
    *delta* introduced by our three seeded rows is exactly what we seeded.
    """
    async with AsyncSessionLocal() as session:
        before = await aggregate_kpi_summary(session, None, None)
        before_orders = before["total_orders"] if before else 0
        before_revenue = before["total_revenue"] if before else Decimal("0")

        bid = await _seed(
            session,
            "agg-alltime",
            [
                (date(2099, 2, 10), Decimal("50")),
                (date(2099, 3, 10), Decimal("150")),
                (date(2099, 4, 10), Decimal("250")),
            ],
        )
        try:
            after = await aggregate_kpi_summary(session, None, None)
            assert after is not None
            assert after["total_orders"] - before_orders == 3
            assert after["total_revenue"] - before_revenue == Decimal("450")
        finally:
            await _cleanup(session, bid)


async def test_zero_or_negative_total_value_excluded():
    """Rows with total_value <= 0 are filtered out via WHERE total_value > 0."""
    async with AsyncSessionLocal() as session:
        # Far-future window so the shared db cannot contaminate assertions.
        bid = await _seed(
            session,
            "agg-filter",
            [
                (date(2099, 6, 1), Decimal("100")),
                (date(2099, 6, 2), Decimal("400")),
                (date(2099, 6, 3), Decimal("0")),  # excluded (not > 0)
                (date(2099, 6, 4), Decimal("-50")),  # excluded (negative)
            ],
        )
        try:
            result = await aggregate_kpi_summary(
                session, date(2099, 6, 1), date(2099, 6, 30)
            )
            assert result is not None
            assert result["total_orders"] == 2
            assert result["total_revenue"] == Decimal("500")
            assert result["avg_order_value"] == Decimal("250")
        finally:
            await _cleanup(session, bid)


# ── v1.53 — Umsatz from revenues table ────────────────────────────────


async def _seed_revenues(prefix: str, rows: list[tuple[str, date, Decimal]]) -> int:
    """Seed (typ, datum, wert_eur) revenue rows under one batch. Returns
    batch id for cleanup."""
    async with AsyncSessionLocal() as session:
        batch = UploadBatch(
            filename=f"{prefix}.txt",
            uploaded_at=datetime.now(timezone.utc),
            row_count=len(rows),
            error_count=0,
            status="success",
            kind="revenues",
        )
        session.add(batch)
        await session.flush()
        now = datetime.now(timezone.utc)
        for idx, (typ, d, v) in enumerate(rows):
            session.add(
                Revenue(
                    vorgang_nr=f"{prefix}-{idx}",
                    typ=typ,
                    datum=d,
                    wert_eur=v,
                    upload_batch_id=batch.id,
                    imported_at=now,
                )
            )
        await session.commit()
        return batch.id


async def _cleanup_revenues(batch_id: int) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(Revenue).where(Revenue.upload_batch_id == batch_id)
        )
        await session.execute(delete(UploadBatch).where(UploadBatch.id == batch_id))
        await session.commit()


async def test_revenue_summary_sums_RG_minus_GS():
    """Net Umsatz = SUM(wert_eur) — GS rows carry negative wert and reduce
    the total."""
    bid = await _seed_revenues(
        "rev-net",
        [
            ("RG", date(2099, 5, 5), Decimal("1000")),
            ("RG", date(2099, 5, 10), Decimal("500")),
            ("GS", date(2099, 5, 12), Decimal("-200")),
        ],
    )
    try:
        async with AsyncSessionLocal() as session:
            total = await aggregate_revenue_summary(
                session, date(2099, 5, 1), date(2099, 5, 31)
            )
        assert total == Decimal("1300")  # 1000 + 500 - 200
    finally:
        await _cleanup_revenues(bid)


async def test_revenue_summary_empty_window_returns_none():
    """Zero matching rows -> None (DELTA-05 null-safety)."""
    bid = await _seed_revenues(
        "rev-empty",
        [("RG", date(2099, 5, 5), Decimal("100"))],
    )
    try:
        async with AsyncSessionLocal() as session:
            total = await aggregate_revenue_summary(
                session, date(2099, 6, 1), date(2099, 6, 30)
            )
        assert total is None
    finally:
        await _cleanup_revenues(bid)


async def test_revenue_summary_respects_date_window():
    """Only rows inside the window are summed."""
    bid = await _seed_revenues(
        "rev-window",
        [
            (("RG", date(2099, 4, 30), Decimal("999"))),  # outside (before)
            (("RG", date(2099, 5, 5), Decimal("100"))),
            (("RG", date(2099, 5, 25), Decimal("200"))),
            (("RG", date(2099, 6, 1), Decimal("888"))),  # outside (after)
        ],
    )
    try:
        async with AsyncSessionLocal() as session:
            total = await aggregate_revenue_summary(
                session, date(2099, 5, 1), date(2099, 5, 31)
            )
        assert total == Decimal("300")
    finally:
        await _cleanup_revenues(bid)
