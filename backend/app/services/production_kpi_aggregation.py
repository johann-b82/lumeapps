"""Produktion — "Aufträge in Verzug" aggregation (v1.76 / v1.78).

Definition (v1.78 — windowed by Zieltermin, includes overdue-open orders)
-------------------------------------------------------------------------
An order belongs to the period of its **Zieltermin** = MAX(auftrag_positionen
.lieferdatum). Within [first, last] an order is *counted* once its outcome is
decided — i.e. it has been delivered, or its Zieltermin already passed (open &
overdue). Not-yet-due open orders (future Zieltermin, no delivery) are pending
and excluded from both numerator and denominator.

    effective = COALESCE(MAX(LS delivery_date), today)
    delay     = effective − Zieltermin           (integer days)
    counted   = delivered OR Zieltermin < today
    in Verzug = counted AND delay > 0

So "in Verzug" spans two categories:
  * delivered late  — has an LS, actual > Zieltermin
  * open & overdue  — no LS, Zieltermin < today

    rate = count(in Verzug) / count(counted)     within the Zieltermin window

``rate`` is a fraction; lower is better. Joined on order number
(``auftrag_positionen.vorgang_nr = delivery_records.order_nr``) via LEFT JOIN so
undelivered orders survive.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
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
# Leer = KEIN Filter (alle Aufträge). Sonst nur Aufträge mit mind. einer Position
# dieser Werte. Beispielwerte im Export: AV-F, AV-P, AV-S, OWB, AB.
# ─────────────────────────────────────────────────────────────────────────────
SERIENGESCHAEFT_POS_TYP_2: frozenset[str] = frozenset()


def _auf_subquery():
    """Per-order Zieltermin (MAX lieferdatum) + a representative customer."""
    where = [AuftragPosition.lieferdatum.isnot(None)]
    if SERIENGESCHAEFT_POS_TYP_2:
        where.append(AuftragPosition.pos_typ_2.in_(SERIENGESCHAEFT_POS_TYP_2))
    return (
        select(
            AuftragPosition.vorgang_nr.label("vorgang_nr"),
            func.max(AuftragPosition.lieferdatum).label("target"),
            func.max(AuftragPosition.customer_name).label("customer_name"),
            func.max(AuftragPosition.customer_id).label("adr_nr"),
        )
        .where(*where)
        .group_by(AuftragPosition.vorgang_nr)
        .subquery()
    )


def _ls_subquery():
    """Per-order actual completion = MAX LS delivery_date."""
    return (
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


async def _counts_for_window(
    db: AsyncSession, first: date, last: date, today: date
) -> tuple[int, int, float]:
    """Return (total, in_verzug, delay_sum) for orders whose Zieltermin is in
    the window and whose outcome is decided (delivered or overdue)."""
    auf = _auf_subquery()
    ls = _ls_subquery()

    effective = func.coalesce(ls.c.actual, today)  # actual delivery, else today
    delay = effective - auf.c.target               # int days (PostgreSQL)
    counted = or_(ls.c.actual.isnot(None), auf.c.target < today)

    stmt = (
        select(
            func.count(),
            func.count().filter(delay > IN_VERZUG_MIN_DAYS),
            func.coalesce(func.sum(delay), 0),
        )
        .select_from(auf)
        .join(ls, auf.c.vorgang_nr == ls.c.order_nr, isouter=True)
        .where(auf.c.target >= first, auf.c.target <= last, counted)
    )
    total, in_verzug, delay_sum = (await db.execute(stmt)).one()
    return int(total or 0), int(in_verzug or 0), float(delay_sum or 0)


def _rate(in_verzug: int, total: int) -> float | None:
    if total <= 0:
        return None
    return in_verzug / total


def _avg_delay(delay_sum: float, total: int) -> float | None:
    if total <= 0:
        return None
    return delay_sum / total


async def compute_verzug(db: AsyncSession, first: date, last: date) -> dict:
    """Verzug rate for the window with prev-period / prev-year baselines."""
    today = date.today()
    total, in_verzug, dsum = await _counts_for_window(db, first, last, today)

    p_first, p_last = prior_window_same_length(first, last)
    p_total, p_in_verzug, _ = await _counts_for_window(db, p_first, p_last, today)

    y_first, y_last = same_window_prior_year(first, last)
    y_total, y_in_verzug, _ = await _counts_for_window(db, y_first, y_last, today)

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
    """Per-bucket Verzug rate; ``buckets`` from ``_bucket_windows`` (by Zieltermin)."""
    today = date.today()
    points: list[dict] = []
    for label, b_first, b_last in buckets:
        total, in_verzug, _ = await _counts_for_window(db, b_first, b_last, today)
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
    """Delivered-late orders (Zieltermin in window, actual > Zieltermin)."""
    auf = _auf_subquery()
    ls = _ls_subquery()
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
        .join(ls, auf.c.vorgang_nr == ls.c.order_nr)  # inner: delivered only
        .where(
            auf.c.target >= first,
            auf.c.target <= last,
            ls.c.actual > auf.c.target,
        )
        .order_by(verzug.desc(), auf.c.vorgang_nr)
        .limit(limit)
    )
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()]


async def list_overdue_open(
    db: AsyncSession, first: date, last: date, *, limit: int = 500
) -> list[dict]:
    """Open & overdue orders: no Lieferschein at all and Zieltermin already past."""
    today = date.today()
    auf = _auf_subquery()
    ls = _ls_subquery()
    days_overdue = today - auf.c.target

    stmt = (
        select(
            auf.c.vorgang_nr,
            auf.c.customer_name,
            auf.c.adr_nr,
            auf.c.target.label("target_date"),
            days_overdue.label("days_overdue"),
        )
        .select_from(auf)
        .join(ls, auf.c.vorgang_nr == ls.c.order_nr, isouter=True)
        .where(
            auf.c.target >= first,
            auf.c.target <= last,
            ls.c.actual.is_(None),        # no delivery at all
            auf.c.target < today,          # overdue
        )
        .order_by(days_overdue.desc(), auf.c.vorgang_nr)
        .limit(limit)
    )
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()]
