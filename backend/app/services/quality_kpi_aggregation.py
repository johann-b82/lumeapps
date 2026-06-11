"""Quality KPI aggregation (v1.49).

Two count KPIs over [first_day, last_day] filtered by audit-type list:
    * level_1 — count of QualityRecord rows with level=1 (Audit Major)
    * level_2 — count of QualityRecord rows with level=2 (Audit Minor)

The four supported audit-type codes are kept in :data:`AUDIT_ART_CODES`.
Rows with ``art`` outside that set are excluded (reserved for the later
Reklamationen branch). Sequential awaits on the shared AsyncSession
(no asyncio.gather), matching the HR aggregation pattern.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QualityRecord
from app.services.hr_kpi_aggregation import (
    prior_window_same_length,
    same_window_prior_year,
)


# Single source of truth — the router exposes the same list as the
# default filter when the caller omits ``audit_types``.
AUDIT_ART_CODES: tuple[str, ...] = ("BH AUD", "EX AUD", "IN AUD", "KU AUD")


def _normalise_art_filter(audit_types: list[str] | None) -> list[str]:
    """Return the effective art-filter list (defaults to all four codes).

    Unknown codes are dropped silently — the router validates the
    incoming query string against AUDIT_ART_CODES before we get here,
    but we belt-and-braces filter at the SQL layer too so the count
    can never include rows from outside the audit domain.
    """
    if not audit_types:
        return list(AUDIT_ART_CODES)
    allowed = set(AUDIT_ART_CODES)
    return [a for a in audit_types if a in allowed] or list(AUDIT_ART_CODES)


def _level_art_key(level: int, art: str) -> str:
    """Flat dict key for the (level, art) breakdown — matches the frontend
    Recharts dataKey contract (e.g. ``level_1_BH_AUD``).
    """
    return f"level_{level}_{art.replace(' ', '_')}"


async def _counts_for_window(
    db: AsyncSession,
    first: date,
    last: date,
    art_filter: list[str],
) -> tuple[int, int]:
    """Return (level_1_count, level_2_count) for the window — total counts only."""
    stmt = (
        select(QualityRecord.level, func.count())
        .where(
            QualityRecord.report_date >= first,
            QualityRecord.report_date <= last,
            QualityRecord.art.in_(art_filter),
            QualityRecord.level.in_([1, 2]),
        )
        .group_by(QualityRecord.level)
    )
    rows = (await db.execute(stmt)).all()
    counts = {int(level): int(n) for level, n in rows}
    return counts.get(1, 0), counts.get(2, 0)


async def _counts_by_art_for_window(
    db: AsyncSession,
    first: date,
    last: date,
    art_filter: list[str],
) -> dict[str, int]:
    """Return a flat ``{level_<n>_<ART_CODE>: count}`` dict for the window.

    Every (level, art) combination in ``art_filter`` is present in the result
    with at least 0 — the frontend can rely on dataKey lookups never returning
    undefined.
    """
    stmt = (
        select(QualityRecord.level, QualityRecord.art, func.count())
        .where(
            QualityRecord.report_date >= first,
            QualityRecord.report_date <= last,
            QualityRecord.art.in_(art_filter),
            QualityRecord.level.in_([1, 2]),
        )
        .group_by(QualityRecord.level, QualityRecord.art)
    )
    rows = (await db.execute(stmt)).all()

    # Seed every key to 0 so the frontend never has to special-case missing
    # buckets when stacking Bars.
    result: dict[str, int] = {
        _level_art_key(level, art): 0
        for level in (1, 2)
        for art in art_filter
    }
    for level, art, n in rows:
        result[_level_art_key(int(level), str(art))] = int(n)
    return result


async def compute_audit_findings(
    db: AsyncSession,
    first: date,
    last: date,
    audit_types: list[str] | None = None,
) -> dict[str, int | None]:
    """Compute Audit-Findings counts for the window with delta baselines.

    Returns the dict shape consumed by ``AuditFindingsValue``.
    """
    art = _normalise_art_filter(audit_types)
    cur_l1, cur_l2 = await _counts_for_window(db, first, last, art)

    prev_first, prev_last = prior_window_same_length(first, last)
    prev_l1, prev_l2 = await _counts_for_window(db, prev_first, prev_last, art)

    ya_first, ya_last = same_window_prior_year(first, last)
    ya_l1, ya_l2 = await _counts_for_window(db, ya_first, ya_last, art)

    return {
        "level_1": cur_l1,
        "level_2": cur_l2,
        "previous_period_level_1": prev_l1,
        "previous_period_level_2": prev_l2,
        "previous_year_level_1": ya_l1,
        "previous_year_level_2": ya_l2,
    }


async def list_audit_findings(
    db: AsyncSession,
    first: date,
    last: date,
    audit_types: list[str] | None = None,
    *,
    limit: int = 500,
) -> list[QualityRecord]:
    """Return the raw QualityRecord rows that match the audit-type filter.

    Includes rows with ``level IS NULL`` so the verification table can
    surface reports whose ``Artikel`` text didn't match the Level 1 /
    Level 2 patterns — that is exactly the diagnostic the user needs to
    spot missing classifications. The KPI cards / charts apply the strict
    ``level IN (1, 2)`` filter at their own SQL layer.

    Ordered newest-first (report_date DESC, report_nr DESC). Hard cap of
    500 rows matches the sales/HR table limits.
    """
    art = _normalise_art_filter(audit_types)
    stmt = (
        select(QualityRecord)
        .where(
            QualityRecord.report_date >= first,
            QualityRecord.report_date <= last,
            QualityRecord.art.in_(art),
        )
        .order_by(QualityRecord.report_date.desc(), QualityRecord.report_nr.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def compute_audit_findings_history(
    db: AsyncSession,
    buckets: list[tuple[str, date, date]],
    audit_types: list[str] | None = None,
) -> list[dict[str, str | int]]:
    """Compute per-bucket finding counts split by (level, art).

    Each returned point carries:
      * ``month`` — bucket label from ``_bucket_windows``
      * ``level_1`` / ``level_2`` — totals (kept for backwards-compat and
        for tooltip totals)
      * ``level_<n>_<ART>`` — one field per (level, art) combination from
        the active filter (e.g. ``level_1_BH_AUD``). Frontend uses these
        as Recharts ``dataKey`` for the stacked-by-category bars.
    """
    art = _normalise_art_filter(audit_types)
    points: list[dict[str, str | int]] = []
    for label, b_first, b_last in buckets:
        by_art = await _counts_by_art_for_window(db, b_first, b_last, art)
        point: dict[str, str | int] = {"month": label, **by_art}
        # Totals derived from the breakdown so the two views can never
        # disagree on a bucket count.
        point["level_1"] = sum(
            v for k, v in by_art.items() if k.startswith("level_1_")
        )
        point["level_2"] = sum(
            v for k, v in by_art.items() if k.startswith("level_2_")
        )
        points.append(point)
    return points
