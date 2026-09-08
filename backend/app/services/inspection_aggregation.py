"""Product-inspection aggregation.

Real SQL against ``inspection_records`` for the Qualitätsprüfung KPI. Two rates
are computed per size class (large / small / total), always as a **daily rate**
so a bucket stays comparable across granularities:

    qty             = SUM(buchungs_menge)
    person_days     = COUNT(DISTINCT (benutzer, pruef_datum))
    inspection_days = COUNT(DISTINCT pruef_datum)
    per_person_day  = qty / person_days      ("Teile pro Person und Tag")
    per_day         = qty / inspection_days   ("Teile pro Tag gesamt")

Filter for every metric: ``rsc == '70000' AND excluded == false`` and the date
window. Each denominator is built **per class separately** — "small" only counts
the person-days on which small parts were actually booked; "total" gets its own
denominator over all rows. Consequence (intended): large + small ≠ total.

Zero denominators (nothing booked) collapse to 0.0 rather than raising. Rates
are rounded to one decimal (values around 11–120, integer rounding lost too
much). Earlier versions used a cross-product denominator
(``distinct inspectors × distinct days``) which under-counted by 3–6× and made
the value shrink as the window grew — replaced here by real person-days.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InspectionRecord
from app.services.hr_kpi_aggregation import (
    prior_window_same_length,
    same_window_prior_year,
)

# v1.81 — only the "70000" Kostenschlüssel actually represents a real
# Qualitätsprüfung booking; every other RSC (60000, 16000, 41000, L xxxx…)
# is a stock-movement / Sonderbuchung and must not contribute to the KPI.
RSC_INSPECTION = "70000"


_CLASSES = ("large", "small", "total")


def _rate(num: float, den: int) -> float:
    """Daily rate rounded to one decimal; 0.0 when the denominator is 0."""
    return round(float(num) / den, 1) if den else 0.0


def _artikel_clause(artikel_filter: str):
    """WHERE-Klausel für den Artikel-Filter über den Präfix „H".

    - ``halbfertig``: nur Artikel mit „H" am Anfang (Halbfertigartikel, z. B.
      Zwischenprüfungen).
    - ``alle``: keine Einschränkung.
    - sonst (Default ``fertig``): alle Artikel OHNE „H" am Anfang; NULL-Artikel
      gelten als Fertigartikel.
    """
    if artikel_filter == "halbfertig":
        return InspectionRecord.artikel.ilike("H%")
    if artikel_filter == "alle":
        return sa.true()
    return sa.or_(
        InspectionRecord.artikel.is_(None),
        sa.not_(InspectionRecord.artikel.ilike("H%")),
    )


async def _class_metrics(
    db: AsyncSession,
    first: date,
    last: date,
    artikel_filter: str = "fertig",
) -> dict[str, float | int | list[str]]:
    """All inspection metrics for the window, per class (large/small/total).

    One query: quantities via ``SUM(...) FILTER``, person-days via
    ``COUNT(DISTINCT (benutzer, pruef_datum)) FILTER`` and inspection-days via
    ``COUNT(DISTINCT pruef_datum) FILTER``. "total" is the unfiltered aggregate
    (its own denominator over all rows), so large + small need not sum to it.
    """
    person_day = sa.tuple_(InspectionRecord.benutzer, InspectionRecord.pruef_datum)
    large_f = InspectionRecord.size_class == "large"
    small_f = InspectionRecord.size_class == "small"
    qty = InspectionRecord.buchungs_menge
    datum = InspectionRecord.pruef_datum

    stmt = sa.select(
        sa.func.coalesce(sa.func.sum(qty).filter(large_f), 0).label("qty_large"),
        sa.func.coalesce(sa.func.sum(qty).filter(small_f), 0).label("qty_small"),
        sa.func.coalesce(sa.func.sum(qty), 0).label("qty_total"),
        sa.func.count(sa.distinct(person_day)).filter(large_f).label("pd_large"),
        sa.func.count(sa.distinct(person_day)).filter(small_f).label("pd_small"),
        sa.func.count(sa.distinct(person_day)).label("pd_total"),
        sa.func.count(sa.distinct(datum)).filter(large_f).label("id_large"),
        sa.func.count(sa.distinct(datum)).filter(small_f).label("id_small"),
        sa.func.count(sa.distinct(datum)).label("id_total"),
        sa.func.count(sa.distinct(InspectionRecord.benutzer)).filter(large_f).label("ins_large"),
        sa.func.count(sa.distinct(InspectionRecord.benutzer)).filter(small_f).label("ins_small"),
        sa.func.count(sa.distinct(InspectionRecord.benutzer)).label("ins_total"),
        sa.func.array_agg(sa.distinct(InspectionRecord.benutzer)).filter(large_f).label("names_large"),
        sa.func.array_agg(sa.distinct(InspectionRecord.benutzer)).filter(small_f).label("names_small"),
        sa.func.array_agg(sa.distinct(InspectionRecord.benutzer)).label("names_total"),
    ).where(
        InspectionRecord.pruef_datum >= first,
        InspectionRecord.pruef_datum <= last,
        InspectionRecord.rsc == RSC_INSPECTION,
        InspectionRecord.excluded.is_(False),
        _artikel_clause(artikel_filter),
    )
    r = (await db.execute(stmt)).one()

    out: dict[str, float | int | list[str]] = {}
    for c in _CLASSES:
        q = float(getattr(r, f"qty_{c}") or 0)
        pd = int(getattr(r, f"pd_{c}") or 0)
        idd = int(getattr(r, f"id_{c}") or 0)
        out[f"{c}_qty"] = q
        out[f"{c}_person_days"] = pd
        out[f"{c}_inspection_days"] = idd
        out[f"{c}_inspectors"] = int(getattr(r, f"ins_{c}") or 0)
        names = getattr(r, f"names_{c}") or []
        out[f"{c}_inspector_names"] = sorted(n for n in names if n)
        out[f"{c}_per_person_day"] = _rate(q, pd)
        out[f"{c}_per_day"] = _rate(q, idd)
    return out


async def compute_inspections(
    db: AsyncSession,
    first: date,
    last: date,
    artikel_filter: str = "fertig",
) -> dict[str, float | None]:
    cur = await _class_metrics(db, first, last, artikel_filter)

    prev_first, prev_last = prior_window_same_length(first, last)
    prev = await _class_metrics(db, prev_first, prev_last, artikel_filter)

    ya_first, ya_last = same_window_prior_year(first, last)
    ya = await _class_metrics(db, ya_first, ya_last, artikel_filter)

    out: dict[str, float | None] = dict(cur)
    # Deltas only on the *_per_person_day headline; None when the comparison
    # window has no person-days (no basis for a delta).
    for c in _CLASSES:
        out[f"previous_period_{c}_per_person_day"] = (
            prev[f"{c}_per_person_day"] if prev[f"{c}_person_days"] else None
        )
        out[f"previous_year_{c}_per_person_day"] = (
            ya[f"{c}_per_person_day"] if ya[f"{c}_person_days"] else None
        )
    return out


async def compute_inspections_history(
    db: AsyncSession,
    buckets: list[tuple[str, date, date]],
    artikel_filter: str = "fertig",
) -> list[dict[str, str | float | int]]:
    points: list[dict[str, str | float | int]] = []
    for label, b_first, b_last in buckets:
        metrics = await _class_metrics(db, b_first, b_last, artikel_filter)
        points.append({"month": label, **metrics})
    return points


async def list_inspections(
    db: AsyncSession,
    first: date,
    last: date,
    artikel_filter: str = "fertig",
) -> list[dict[str, Any]]:
    """One aggregated row per (bezeichnung, size_class) in the window.

    Used by the verification table under the charts. Groups every
    inspection booking by product name + classification, so the user can
    scan which products got which classification and how often each was
    booked. Rejects (Ausschuss) are surfaced so scrap-heavy products
    stand out.
    """
    stmt = (
        sa.select(
            InspectionRecord.bezeichnung,
            InspectionRecord.size_class,
            sa.func.count(InspectionRecord.id).label("bookings"),
            sa.func.coalesce(
                sa.func.sum(InspectionRecord.buchungs_menge), 0
            ).label("total_qty"),
            sa.func.coalesce(
                sa.func.sum(InspectionRecord.ausschuss_menge), 0
            ).label("scrap_qty"),
            sa.func.count(sa.func.distinct(InspectionRecord.benutzer)).label(
                "inspectors"
            ),
            sa.func.min(InspectionRecord.pruef_datum).label("first_date"),
            sa.func.max(InspectionRecord.pruef_datum).label("last_date"),
            sa.func.max(InspectionRecord.produktgruppe).label("produktgruppe"),
        )
        .where(
            InspectionRecord.pruef_datum >= first,
            InspectionRecord.pruef_datum <= last,
            InspectionRecord.rsc == RSC_INSPECTION,
            InspectionRecord.excluded.is_(False),
            _artikel_clause(artikel_filter),
        )
        .group_by(InspectionRecord.bezeichnung, InspectionRecord.size_class)
        .order_by(sa.func.sum(InspectionRecord.buchungs_menge).desc().nulls_last())
    )
    result = await db.execute(stmt)

    rows: list[dict[str, Any]] = []
    for row in result.all():
        total = float(row.total_qty or 0)
        scrap = float(row.scrap_qty or 0)
        scrap_rate = (scrap / total) if total > 0 else None
        rows.append({
            "bezeichnung": row.bezeichnung,
            "size_class": row.size_class,
            "produktgruppe": row.produktgruppe,
            "bookings": int(row.bookings or 0),
            "total_qty": total,
            "scrap_qty": scrap,
            "scrap_rate": scrap_rate,
            "inspectors": int(row.inspectors or 0),
            "first_date": row.first_date.isoformat() if row.first_date else None,
            "last_date": row.last_date.isoformat() if row.last_date else None,
        })
    return rows


async def list_inspection_bookings(
    db: AsyncSession,
    first: date,
    last: date,
    artikel_filter: str = "fertig",
) -> list[dict[str, Any]]:
    """One row per real Qualitätsprüfung booking in the window.

    Only ``rsc == '70000'`` rows are returned — the other Kostenschlüssel
    are stock-movement bookings the ERP mixes into the same export and
    they don't belong in the verification table. Excluded rows *are*
    returned (with ``excluded=true``) so the frontend can render the
    checkbox in its correct state.
    """
    stmt = (
        sa.select(
            InspectionRecord.id,
            InspectionRecord.pruef_datum,
            InspectionRecord.pruef_zeit,
            InspectionRecord.benutzer,
            InspectionRecord.fa,
            InspectionRecord.artikel,
            InspectionRecord.bezeichnung,
            InspectionRecord.size_class,
            InspectionRecord.produktgruppe,
            InspectionRecord.buchungs_menge,
            InspectionRecord.ausschuss_menge,
            InspectionRecord.excluded,
        )
        .where(
            InspectionRecord.pruef_datum >= first,
            InspectionRecord.pruef_datum <= last,
            InspectionRecord.rsc == RSC_INSPECTION,
            _artikel_clause(artikel_filter),
        )
        .order_by(
            InspectionRecord.pruef_datum.desc(),
            InspectionRecord.id.desc(),
        )
    )
    result = await db.execute(stmt)
    return [
        {
            "id": r.id,
            "pruef_datum": r.pruef_datum.isoformat() if r.pruef_datum else None,
            "pruef_zeit": r.pruef_zeit.isoformat() if r.pruef_zeit else None,
            "benutzer": r.benutzer,
            "fa": r.fa,
            "artikel": r.artikel,
            "bezeichnung": r.bezeichnung,
            "size_class": r.size_class,
            "produktgruppe": r.produktgruppe,
            "buchungs_menge": float(r.buchungs_menge or 0),
            "ausschuss_menge": float(r.ausschuss_menge or 0),
            "excluded": bool(r.excluded),
        }
        for r in result.all()
    ]


async def set_booking_excluded(
    db: AsyncSession,
    booking_id: int,
    excluded: bool,
) -> dict[str, Any] | None:
    """Toggle a booking's KPI opt-out flag. Returns the updated row dict,
    or None when the id doesn't match anything."""
    result = await db.execute(
        sa.update(InspectionRecord)
        .where(InspectionRecord.id == booking_id)
        .values(excluded=excluded)
        .returning(
            InspectionRecord.id,
            InspectionRecord.pruef_datum,
            InspectionRecord.pruef_zeit,
            InspectionRecord.benutzer,
            InspectionRecord.fa,
            InspectionRecord.artikel,
            InspectionRecord.bezeichnung,
            InspectionRecord.size_class,
            InspectionRecord.produktgruppe,
            InspectionRecord.buchungs_menge,
            InspectionRecord.ausschuss_menge,
            InspectionRecord.excluded,
        )
    )
    row = result.first()
    if row is None:
        await db.rollback()
        return None
    await db.commit()
    return {
        "id": row.id,
        "pruef_datum": row.pruef_datum.isoformat() if row.pruef_datum else None,
        "pruef_zeit": row.pruef_zeit.isoformat() if row.pruef_zeit else None,
        "benutzer": row.benutzer,
        "fa": row.fa,
        "artikel": row.artikel,
        "bezeichnung": row.bezeichnung,
        "size_class": row.size_class,
        "produktgruppe": row.produktgruppe,
        "buchungs_menge": float(row.buchungs_menge or 0),
        "ausschuss_menge": float(row.ausschuss_menge or 0),
        "excluded": bool(row.excluded),
    }
