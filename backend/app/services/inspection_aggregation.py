"""Product-inspection aggregation (v1.79).

Fills the compute_inspections / compute_inspections_history stubs with the
real SQL against ``inspection_records``. The KPI unit is
``Produkte / Tag / Mitarbeiter``:

    counted_products = SUM(buchungs_menge)
    inspectors       = COUNT(DISTINCT benutzer)        WHERE …
    inspection_days  = COUNT(DISTINCT pruef_datum)     WHERE …
    kpi              = counted_products / (inspectors * inspection_days)

Zero denominators (nothing booked in the window) collapse to 0 rather
than raising — the chart just shows a bar of height 0. All three
metrics are computed twice per window (large / small) because they
depend on which rows are in-scope: an inspector who only worked on
Curtains does not count as an inspector for the small-product KPI.
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


async def _per_class_counts(
    db: AsyncSession,
    first: date,
    last: date,
) -> tuple[int, int]:
    """Return ``(large_count, small_count)`` for the window.

    Each count is normalised per inspector-day: totalled Buchungs-Menge
    for the class divided by a **shared** ``(distinct Prüfer × distinct
    Prüftage)`` denominator across the whole window. Grouping the
    denominator per class would double-count inspectors who work on both
    tiers and drop a class's KPI when only a subset of the workforce
    booked it — the customer wants a single "how many products per
    inspector-day" rate, so the head-count stays global.
    """
    # 1) Numerators — one sum per size class. Excluded bookings (per
    # user's row-level opt-out flag, v1.80) are skipped so a fat-finger
    # ERP booking doesn't wreck the KPI.
    totals_stmt = (
        sa.select(
            InspectionRecord.size_class,
            sa.func.coalesce(
                sa.func.sum(InspectionRecord.buchungs_menge), 0
            ).label("total"),
        )
        .where(
            InspectionRecord.pruef_datum >= first,
            InspectionRecord.pruef_datum <= last,
            InspectionRecord.rsc == RSC_INSPECTION,
            InspectionRecord.excluded.is_(False),
        )
        .group_by(InspectionRecord.size_class)
    )
    totals = {
        row.size_class: float(row.total or 0)
        for row in (await db.execute(totals_stmt)).all()
    }

    # 2) Shared denominator — distinct inspectors × distinct inspection
    # days over the whole window, regardless of class. Also filters
    # excluded bookings so a lone excluded row doesn't push its
    # inspector into the head-count.
    denom_stmt = sa.select(
        sa.func.count(sa.func.distinct(InspectionRecord.benutzer)),
        sa.func.count(sa.func.distinct(InspectionRecord.pruef_datum)),
    ).where(
        InspectionRecord.pruef_datum >= first,
        InspectionRecord.pruef_datum <= last,
        InspectionRecord.rsc == RSC_INSPECTION,
        InspectionRecord.excluded.is_(False),
    )
    inspectors, days = (await db.execute(denom_stmt)).one()
    denom = (inspectors or 0) * (days or 0)
    if denom <= 0:
        return 0, 0

    large = round(totals.get("large", 0.0) / denom)
    small = round(totals.get("small", 0.0) / denom)
    return large, small


async def compute_inspections(
    db: AsyncSession,
    first: date,
    last: date,
) -> dict[str, int | None]:
    cur_large, cur_small = await _per_class_counts(db, first, last)

    prev_first, prev_last = prior_window_same_length(first, last)
    prev_large, prev_small = await _per_class_counts(db, prev_first, prev_last)

    ya_first, ya_last = same_window_prior_year(first, last)
    ya_large, ya_small = await _per_class_counts(db, ya_first, ya_last)

    return {
        "large_count": cur_large,
        "small_count": cur_small,
        "previous_period_large": prev_large,
        "previous_period_small": prev_small,
        "previous_year_large": ya_large,
        "previous_year_small": ya_small,
    }


async def compute_inspections_history(
    db: AsyncSession,
    buckets: list[tuple[str, date, date]],
) -> list[dict[str, str | int]]:
    points: list[dict[str, str | int]] = []
    for label, b_first, b_last in buckets:
        large, small = await _per_class_counts(db, b_first, b_last)
        points.append({"month": label, "large_count": large, "small_count": small})
    return points


async def list_inspections(
    db: AsyncSession,
    first: date,
    last: date,
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
