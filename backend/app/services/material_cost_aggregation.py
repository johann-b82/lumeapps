"""Materialkostenquote aggregation (Finanzperspektive, v1.63).

Formula
-------
    ratio = material_cost(window) / revenue(window)

where, over the window [first, last]:

* **material_cost** = Σ over articles ( consumed_qty × unit_price )
  - ``consumed_qty`` = ``-SUM(bewegungsmenge)`` over ``material_movements``
    rows with ``buchtyp IN ('M','SM')`` (M issues are negative, SM reversals
    positive — so the negated sum is the net material consumed).
  - ``unit_price`` = ``pos_wert / menge`` of the *newest* ``material_prices``
    row for that Artnr (newest by ``datum``, across all WE data — the current
    purchase price). Robust against the source's price-unit, since the raw
    ``preis`` column can be quoted per 100/1000 while ``pos_wert / menge`` is
    always the real per-unit cost.
  - Articles consumed but with no WE price are *unmatched*: excluded from the
    cost and surfaced via ``unmatched_articles`` / the verification list.
* **revenue** = ``SUM(revenues.wert_eur)`` over the window (RG/GS net Umsatz —
  the existing Umsatz definition, GS Gutschriften are negative).

Returns the ratio as a fraction (0.34 → 34 %). Lower is better — the frontend
colours deltas accordingly (a falling material-cost ratio is good).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MaterialMovement, MaterialPrice, Revenue
from app.services.hr_kpi_aggregation import (
    prior_window_same_length,
    same_window_prior_year,
)

# Stock-movement types that count toward material consumption.
CONSUMPTION_BUCHTYPEN = ("M", "SM")


async def _latest_prices(db: AsyncSession) -> dict[str, float]:
    """Effective unit price per Artnr from the newest WE row.

    ``DISTINCT ON (artnr)`` keeps, per article, the row with the newest
    ``datum`` (tie-break: highest id). Rows with a zero/NULL ``menge`` or NULL
    ``pos_wert`` are filtered out first so the price is always defined and
    sourced from a row that actually carries a value.
    """
    G = MaterialPrice
    stmt = (
        select(G.artnr, G.pos_wert, G.menge)
        .where(
            G.menge.isnot(None),
            G.menge != 0,
            G.pos_wert.isnot(None),
            G.datum.isnot(None),
        )
        .order_by(G.artnr, G.datum.desc(), G.id.desc())
        .distinct(G.artnr)
    )
    rows = (await db.execute(stmt)).all()
    prices: dict[str, float] = {}
    for artnr, pos_wert, menge in rows:
        if menge and float(menge) != 0.0:
            prices[artnr] = float(pos_wert) / float(menge)
    return prices


async def _consumed_by_article(
    db: AsyncSession, first: date, last: date
) -> list[tuple[str, float, str | None]]:
    """Return [(artikelnr, consumed_qty, article_name), ...] for the window.

    ``consumed_qty`` = ``-SUM(bewegungsmenge)`` over the consumption buchtypen.
    Articles whose movements net to exactly zero are dropped.
    """
    M = MaterialMovement
    stmt = (
        select(
            M.artikelnr,
            func.coalesce(func.sum(M.bewegungsmenge), 0),
            func.max(M.article_name),
        )
        .where(
            M.buchtyp.in_(CONSUMPTION_BUCHTYPEN),
            M.buch_datum >= first,
            M.buch_datum <= last,
        )
        .group_by(M.artikelnr)
    )
    rows = (await db.execute(stmt)).all()
    out: list[tuple[str, float, str | None]] = []
    for artikelnr, menge_sum, name in rows:
        consumed = -float(menge_sum or 0)
        if consumed == 0.0:
            continue
        out.append((artikelnr, consumed, name))
    return out


async def _revenue_for_window(db: AsyncSession, first: date, last: date) -> float:
    """Net Umsatz = SUM(revenues.wert_eur) over the window."""
    total = (
        await db.execute(
            select(func.coalesce(func.sum(Revenue.wert_eur), 0)).where(
                Revenue.datum >= first, Revenue.datum <= last
            )
        )
    ).scalar_one() or 0
    return float(total)


def _material_cost(
    consumed: list[tuple[str, float, str | None]], prices: dict[str, float]
) -> tuple[float, int, int]:
    """Return (material_cost, matched_articles, unmatched_articles)."""
    cost = 0.0
    matched = 0
    unmatched = 0
    for artikelnr, qty, _name in consumed:
        price = prices.get(artikelnr)
        if price is None:
            unmatched += 1
            continue
        cost += qty * price
        matched += 1
    return cost, matched, unmatched


def _ratio(cost: float, revenue: float) -> float | None:
    """ratio = material_cost / revenue. Undefined → None (avoids /0)."""
    if revenue <= 0:
        return None
    return cost / revenue


async def _ratio_for_window(
    db: AsyncSession, prices: dict[str, float], first: date, last: date
) -> float | None:
    consumed = await _consumed_by_article(db, first, last)
    cost, _, _ = _material_cost(consumed, prices)
    revenue = await _revenue_for_window(db, first, last)
    return _ratio(cost, revenue)


async def compute_material_cost_ratio(
    db: AsyncSession, first: date, last: date
) -> dict:
    """Materialkostenquote for the window with prev-period / prev-year baselines."""
    prices = await _latest_prices(db)

    consumed = await _consumed_by_article(db, first, last)
    cost, matched, unmatched = _material_cost(consumed, prices)
    revenue = await _revenue_for_window(db, first, last)

    p_first, p_last = prior_window_same_length(first, last)
    y_first, y_last = same_window_prior_year(first, last)

    return {
        "ratio": _ratio(cost, revenue),
        "material_cost": round(cost, 2),
        "revenue": round(revenue, 2),
        "matched_articles": matched,
        "unmatched_articles": unmatched,
        "previous_period": await _ratio_for_window(db, prices, p_first, p_last),
        "previous_year": await _ratio_for_window(db, prices, y_first, y_last),
    }


async def compute_material_cost_ratio_history(
    db: AsyncSession, buckets: list[tuple[str, date, date]]
) -> list[dict]:
    """Per-bucket Materialkostenquote; ``buckets`` from ``_bucket_windows``."""
    prices = await _latest_prices(db)
    points: list[dict] = []
    for label, b_first, b_last in buckets:
        consumed = await _consumed_by_article(db, b_first, b_last)
        cost, _, _ = _material_cost(consumed, prices)
        revenue = await _revenue_for_window(db, b_first, b_last)
        points.append({
            "month": label,
            "ratio": _ratio(cost, revenue),
            "material_cost": round(cost, 2),
            "revenue": round(revenue, 2),
        })
    return points


async def list_material_cost_ratio(
    db: AsyncSession,
    first: date,
    last: date,
    *,
    limit: int = 500,
) -> list[dict]:
    """Per-article breakdown for the verification table (window on buch_datum).

    One row per consumed article: consumed qty, the unit price used (or null
    when unmatched), and the resulting material cost. Sorted by material cost
    descending so the biggest cost drivers — and the unmatched articles
    (cost null) — are easy to spot.
    """
    prices = await _latest_prices(db)
    consumed = await _consumed_by_article(db, first, last)

    rows: list[dict] = []
    for artikelnr, qty, name in consumed:
        price = prices.get(artikelnr)
        cost = qty * price if price is not None else None
        rows.append({
            "artikelnr": artikelnr,
            "article_name": name,
            "consumed_qty": round(qty, 3),
            "unit_price": round(price, 4) if price is not None else None,
            "material_cost": round(cost, 2) if cost is not None else None,
            "has_price": price is not None,
        })

    # Cost drivers first; unmatched (None cost) sink to the bottom.
    rows.sort(key=lambda r: (r["material_cost"] is not None, r["material_cost"] or 0.0), reverse=True)
    return rows[:limit]
