"""Produktion — "Aufträge in Verzug" aggregation (v1.76).

Formula (Gesamtfertigstellung)
------------------------------
    rate = count(orders in Verzug)   within [first, last]
           ───────────────────────
           count(orders total)        within [first, last]

Per order:
* ``target``  = MAX(``auftrag_positionen.lieferdatum``) — the latest confirmed
  Zieltermin across the order's positions (when the whole order should be done).
* ``actual``  = MAX(``delivery_records.delivery_date``) — the latest Lieferschein
  date across the order's delivered positions (when it was actually finished).
* An order is *in Verzug* when ``actual − target > 0`` days.

Joined on order number (``auftrag_positionen.vorgang_nr = delivery_records
.order_nr``). Window filter is the *actual* completion date, keeping the KPI
consistent with the other perspectives' date selector.

Orders without any positional Zieltermin, or with no Lieferschein yet, are
excluded (Verzug undefined / order still open — the latter is the domain of the
planned "Verzugsgefahr" section). ``rate`` is a fraction (0.12 → 12 %); lower is
better, deltas render in Termintreue-complement space on the frontend.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuftragPosition, DeliveryRecord
from app.services.hr_kpi_aggregation import (
    prior_window_same_length,
    same_window_prior_year,
)

# An order is in Verzug when the delay exceeds this many days (0 = any late).
IN_VERZUG_MIN_DAYS = 0

# ─────────────────────────────────────────────────────────────────────────────
# ⚠️  CONFIG — 'Pos Typ 2'-Werte, die Seriengeschäft kennzeichnen.
#
# Leer  → KEIN Filter: alle Aufträge werden gezählt (aktuell gewählt).
# Sonst → nur Aufträge, die mindestens eine Position mit einem dieser
#          'Pos Typ 2'-Werte haben. Mögliche Werte im Export: AV-F, AV-P,
#          AV-S, OWB, AB. Sobald der Serien-Code feststeht, hier eintragen, z. B.:
#              SERIENGESCHAEFT_POS_TYP_2 = frozenset({"AV-S"})
# ─────────────────────────────────────────────────────────────────────────────
SERIENGESCHAEFT_POS_TYP_2: frozenset[str] = frozenset()


async def _counts_for_window(
    db: AsyncSession, first: date, last: date
) -> tuple[int, int, float]:
    """Return (total, in_verzug, delay_sum) for orders completed in the window.

    ``total``     — orders whose latest LS delivery falls in the window and that
                    have a positional Zieltermin.
    ``in_verzug`` — subset whose latest delivery overran the latest Zieltermin.
    ``delay_sum`` — Σ (actual − target) days across ``total`` (signed).
    """
    # Latest confirmed Zieltermin per order (optionally Seriengeschäft-filtered).
    auf_where = [AuftragPosition.lieferdatum.isnot(None)]
    if SERIENGESCHAEFT_POS_TYP_2:
        auf_where.append(
            AuftragPosition.pos_typ_2.in_(SERIENGESCHAEFT_POS_TYP_2)
        )
    auf = (
        select(
            AuftragPosition.vorgang_nr.label("vorgang_nr"),
            func.max(AuftragPosition.lieferdatum).label("target"),
        )
        .where(*auf_where)
        .group_by(AuftragPosition.vorgang_nr)
        .subquery()
    )

    # Latest actual delivery per order.
    ls = (
        select(
            DeliveryRecord.order_nr.label("order_nr"),
            func.max(DeliveryRecord.delivery_date).label("actual"),
        )
        .where(
            DeliveryRecord.order_nr.isnot(None),
            DeliveryRecord.delivery_date.isnot(None),
        )
        .group_by(DeliveryRecord.order_nr)
        .subquery()
    )

    # date − date → integer days in PostgreSQL.
    verzug = ls.c.actual - auf.c.target

    stmt = (
        select(
            func.count(),
            func.count().filter(verzug > IN_VERZUG_MIN_DAYS),
            func.coalesce(func.sum(verzug), 0),
        )
        .select_from(auf)
        .join(ls, auf.c.vorgang_nr == ls.c.order_nr)
        .where(ls.c.actual >= first, ls.c.actual <= last)
    )

    total, in_verzug, delay_sum = (await db.execute(stmt)).one()
    return int(total or 0), int(in_verzug or 0), float(delay_sum or 0)


def _rate(in_verzug: int, total: int) -> float | None:
    """rate = in_verzug / total. Undefined → None (avoids 0/0)."""
    if total <= 0:
        return None
    return in_verzug / total


def _avg_delay(delay_sum: float, total: int) -> float | None:
    if total <= 0:
        return None
    return delay_sum / total


async def compute_verzug(db: AsyncSession, first: date, last: date) -> dict:
    """Verzug rate for the window with prev-period / prev-year baselines."""
    total, in_verzug, dsum = await _counts_for_window(db, first, last)

    p_first, p_last = prior_window_same_length(first, last)
    p_total, p_in_verzug, _ = await _counts_for_window(db, p_first, p_last)

    y_first, y_last = same_window_prior_year(first, last)
    y_total, y_in_verzug, _ = await _counts_for_window(db, y_first, y_last)

    return {
        "rate": _rate(in_verzug, total),
        "in_verzug_count": in_verzug,
        "total_count": total,
        "avg_delay": _avg_delay(dsum, total),
        "previous_period": _rate(p_in_verzug, p_total),
        "previous_year": _rate(y_in_verzug, y_total),
    }


async def compute_verzug_history(
    db: AsyncSession, buckets: list[tuple[str, date, date]]
) -> list[dict]:
    """Per-bucket Verzug rate; ``buckets`` from ``_bucket_windows``."""
    points: list[dict] = []
    for label, b_first, b_last in buckets:
        total, in_verzug, _ = await _counts_for_window(db, b_first, b_last)
        points.append({
            "month": label,
            "rate": _rate(in_verzug, total),
            "in_verzug_count": in_verzug,
            "total_count": total,
        })
    return points


async def list_verzug(
    db: AsyncSession, first: date, last: date, *, limit: int = 500
) -> list[dict]:
    """Orders in Verzug in the window (most-delayed first), one row per order.

    Same per-order Gesamtfertigstellung join as the KPI, filtered to
    ``actual − target > 0`` — the actionable list behind the headline number.
    """
    AP = AuftragPosition
    DR = DeliveryRecord

    auf_where = [AP.lieferdatum.isnot(None)]
    if SERIENGESCHAEFT_POS_TYP_2:
        auf_where.append(AP.pos_typ_2.in_(SERIENGESCHAEFT_POS_TYP_2))
    auf = (
        select(
            AP.vorgang_nr.label("vorgang_nr"),
            func.max(AP.lieferdatum).label("target"),
            func.max(AP.customer_name).label("customer_name"),
            func.max(AP.customer_id).label("adr_nr"),
        )
        .where(*auf_where)
        .group_by(AP.vorgang_nr)
        .subquery()
    )
    ls = (
        select(
            DR.order_nr.label("order_nr"),
            func.max(DR.delivery_date).label("actual"),
        )
        .where(DR.order_nr.isnot(None), DR.delivery_date.isnot(None))
        .group_by(DR.order_nr)
        .subquery()
    )
    verzug = ls.c.actual - auf.c.target

    stmt = (
        select(
            auf.c.vorgang_nr,
            auf.c.customer_name,
            auf.c.adr_nr,
            auf.c.target.label("target_date"),
            ls.c.actual.label("actual_date"),
            verzug.label("verzug_tage"),
        )
        .select_from(auf)
        .join(ls, auf.c.vorgang_nr == ls.c.order_nr)
        .where(
            ls.c.actual >= first,
            ls.c.actual <= last,
            verzug > IN_VERZUG_MIN_DAYS,
        )
        .order_by(verzug.desc(), auf.c.vorgang_nr)
        .limit(limit)
    )
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()]
