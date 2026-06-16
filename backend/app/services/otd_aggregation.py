"""Liefertermintreue / OTD aggregation (Einkauf, v1.60).

Formula
-------
    rate = count(punctual positions)        within [first, last]
           ─────────────────────────────
           count(all positions)              within [first, last]

* A position is *punctual* when ``verzug_tage <= 0`` (delivered on or before
  the confirmed target; early counts as punctual).
* Counted by position, not quantity.
* Window filter is ``delivered_date`` (actual goods-receipt date), keeping OTD
  consistent with the other KPIs' date selector.

Returns the rate as a fraction (e.g. ``0.92`` = 92 %). Higher is better — the
opposite polarity of the complaint rate; the frontend colours deltas
accordingly.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DeliveryReliabilityRecord
from app.services.hr_kpi_aggregation import (
    prior_window_same_length,
    same_window_prior_year,
)

# On time when the delay is zero or negative (early).
PUNCTUAL_MAX_VERZUG = 0


async def _counts_for_window(
    db: AsyncSession, first: date, last: date
) -> tuple[int, int, float, int]:
    """Return (total, punctual, delay_sum, delay_count) for the window.

    ``delay_count`` excludes rows with a NULL ``verzug_tage`` so the average
    delay isn't diluted by positions the export left blank.
    """
    R = DeliveryReliabilityRecord
    base = (R.delivered_date >= first, R.delivered_date <= last)

    total = (
        await db.execute(select(func.count(R.id)).where(*base))
    ).scalar_one() or 0
    punctual = (
        await db.execute(
            select(func.count(R.id)).where(
                *base, R.verzug_tage <= PUNCTUAL_MAX_VERZUG
            )
        )
    ).scalar_one() or 0
    delay_sum = (
        await db.execute(
            select(func.coalesce(func.sum(R.verzug_tage), 0)).where(*base)
        )
    ).scalar_one() or 0
    delay_count = (
        await db.execute(select(func.count(R.verzug_tage)).where(*base))
    ).scalar_one() or 0

    return int(total), int(punctual), float(delay_sum), int(delay_count)


def _rate(punctual: int, total: int) -> float | None:
    """rate = punctual / total. Undefined → None (avoids 0/0)."""
    if total <= 0:
        return None
    return punctual / total


def _avg_delay(delay_sum: float, delay_count: int) -> float | None:
    if delay_count <= 0:
        return None
    return delay_sum / delay_count


async def compute_otd(db: AsyncSession, first: date, last: date) -> dict:
    """OTD rate for the window with prev-period / prev-year baselines."""
    total, punctual, dsum, dcount = await _counts_for_window(db, first, last)

    p_first, p_last = prior_window_same_length(first, last)
    p_total, p_punctual, _, _ = await _counts_for_window(db, p_first, p_last)

    y_first, y_last = same_window_prior_year(first, last)
    y_total, y_punctual, _, _ = await _counts_for_window(db, y_first, y_last)

    return {
        "rate": _rate(punctual, total),
        "punctual_count": punctual,
        "total_count": total,
        "avg_delay": _avg_delay(dsum, dcount),
        "previous_period": _rate(p_punctual, p_total),
        "previous_year": _rate(y_punctual, y_total),
    }


async def compute_otd_history(
    db: AsyncSession, buckets: list[tuple[str, date, date]]
) -> list[dict]:
    """Per-bucket OTD rate; ``buckets`` from ``_bucket_windows``."""
    points: list[dict] = []
    for label, b_first, b_last in buckets:
        total, punctual, _, _ = await _counts_for_window(db, b_first, b_last)
        points.append({
            "month": label,
            "rate": _rate(punctual, total),
            "punctual_count": punctual,
            "total_count": total,
        })
    return points


async def list_otd(
    db: AsyncSession,
    first: date,
    last: date,
    *,
    limit: int = 500,
) -> list[DeliveryReliabilityRecord]:
    """Delivery positions for the verification table (window on delivered_date)."""
    R = DeliveryReliabilityRecord
    stmt = (
        select(R)
        .where(R.delivered_date >= first, R.delivered_date <= last)
        .order_by(R.delivered_date.desc(), R.auftrag.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
