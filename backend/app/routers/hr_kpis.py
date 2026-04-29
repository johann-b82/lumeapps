"""HR KPI endpoints — aggregated over arbitrary [date_from, date_to] windows.

Phase 60 reverses the original D-03 (fixed calendar month windows only).
Both /kpis and /kpis/history now accept date_from + date_to query params;
when both are omitted, endpoints fall back to current-month (/kpis) or
last-12-months (/kpis/history) for backward compatibility with the
thisYear landing experience.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import get_current_user
from app.models import AppSettings
from app.schemas import HrKpiHistoryPoint, HrKpiResponse
from app.services.hr_kpi_aggregation import (
    _fluctuation,
    _month_bounds,
    _overtime_ratio,
    _prev_month,
    _revenue_per_production_employee,
    _sick_leave_ratio,
    compute_hr_kpis,
    prior_window_same_length,
    same_window_prior_year,
)

router = APIRouter(
    prefix="/api/hr",
    tags=["hr-kpis"],
    dependencies=[Depends(get_current_user)],
)


def _validate_range(date_from: date | None, date_to: date | None) -> None:
    """Raise 400 if exactly one bound is provided, or if bounds are inverted."""
    if (date_from is None) != (date_to is None):
        raise HTTPException(
            status_code=400,
            detail="date_from and date_to must be provided together",
        )
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from must be <= date_to",
        )


def _bucket_windows(first: date, last: date) -> list[tuple[str, date, date]]:
    """Return ordered [(label, bucket_first, bucket_last), ...] covering [first, last].

    Bucket granularity (D-06):
      length_days <= 31  -> daily   (label "YYYY-MM-DD")
      length_days <= 91  -> weekly  (label "YYYY-Www", ISO week)
      length_days <= 731 -> monthly (label "YYYY-MM")
      else               -> quarterly (label "YYYY-Qn")

    Bucket edges are clipped to [first, last]. Order is oldest-first.
    """
    length_days = (last - first).days + 1
    buckets: list[tuple[str, date, date]] = []

    if length_days <= 0:
        return buckets

    if length_days <= 31:
        # Daily
        d = first
        while d <= last:
            buckets.append((d.isoformat(), d, d))
            d += timedelta(days=1)
        return buckets

    if length_days <= 91:
        # Weekly (ISO week, Mon-Sun)
        d = first
        while d <= last:
            # Walk back to Monday
            weekday = d.weekday()  # Mon=0
            week_start = d - timedelta(days=weekday)
            week_end = week_start + timedelta(days=6)
            bucket_first = max(week_start, first)
            bucket_last = min(week_end, last)
            iso_year, iso_week, _ = d.isocalendar()
            label = f"{iso_year}-W{iso_week:02d}"
            buckets.append((label, bucket_first, bucket_last))
            # Advance to the Monday of next week
            d = week_end + timedelta(days=1)
        return buckets

    if length_days <= 731:
        # Monthly
        y, m = first.year, first.month
        while (y, m) <= (last.year, last.month):
            mf, ml = _month_bounds(y, m)
            bucket_first = max(mf, first)
            bucket_last = min(ml, last)
            label = f"{y}-{m:02d}"
            buckets.append((label, bucket_first, bucket_last))
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
        return buckets

    # Quarterly
    y = first.year
    q = (first.month - 1) // 3 + 1
    while True:
        q_first_month = (q - 1) * 3 + 1
        q_last_month = q_first_month + 2
        qf, _ = _month_bounds(y, q_first_month)
        _, ql = _month_bounds(y, q_last_month)
        if qf > last:
            break
        bucket_first = max(qf, first)
        bucket_last = min(ql, last)
        label = f"{y}-Q{q}"
        buckets.append((label, bucket_first, bucket_last))
        if q == 4:
            y, q = y + 1, 1
        else:
            q += 1
    return buckets


@router.get("/kpis", response_model=HrKpiResponse)
async def get_hr_kpis(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> HrKpiResponse:
    """Return all 5 HR KPIs for [date_from, date_to].

    If both params are omitted, falls back to the current calendar month
    (thisYear-landing parity). If exactly one is provided, raises 400.
    """
    _validate_range(date_from, date_to)
    if date_from is None:
        today = date.today()
        date_from, date_to = _month_bounds(today.year, today.month)
    return await compute_hr_kpis(db, date_from, date_to)


@router.get("/kpis/history", response_model=list[HrKpiHistoryPoint])
async def get_hr_kpi_history(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[HrKpiHistoryPoint]:
    """Return per-bucket HR KPIs across [date_from, date_to].

    Bucketing (D-06):
      length_days <= 31  -> daily   (label "YYYY-MM-DD")
      length_days <= 91  -> weekly  (label "YYYY-Www", ISO week)
      length_days <= 731 -> monthly (label "YYYY-MM")
      else               -> quarterly (label "YYYY-Qn")

    Omitted params fall back to last-12-months monthly (D-07 thisYear parity).
    """
    _validate_range(date_from, date_to)

    settings_row = (
        await db.execute(sa_select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()

    sick_type_ids: list[int] = (settings_row.personio_sick_leave_type_id or []) if settings_row else []
    prod_depts: list[str] = (settings_row.personio_production_dept or []) if settings_row else []

    if date_from is None:
        # Legacy fallback: last 12 calendar months, oldest-first (thisYear parity).
        today = date.today()
        months: list[tuple[int, int]] = []
        y, m = today.year, today.month
        for _ in range(12):
            months.append((y, m))
            y, m = _prev_month(y, m)
        months.reverse()

        points: list[HrKpiHistoryPoint] = []
        for year, month in months:
            first, last = _month_bounds(year, month)
            ot = await _overtime_ratio(db, first, last)
            sl = await _sick_leave_ratio(db, first, last, sick_type_ids) if sick_type_ids else None
            fl = await _fluctuation(db, first, last)
            rpe = await _revenue_per_production_employee(db, first, last, prod_depts) if prod_depts else None
            points.append(HrKpiHistoryPoint(
                month=f"{year}-{month:02d}",
                overtime_ratio=ot,
                sick_leave_ratio=sl,
                fluctuation=fl,
                revenue_per_production_employee=rpe,
            ))
        return points

    # Arbitrary range — bucket by length
    buckets = _bucket_windows(date_from, date_to)
    points: list[HrKpiHistoryPoint] = []
    for label, b_first, b_last in buckets:
        ot = await _overtime_ratio(db, b_first, b_last)
        sl = await _sick_leave_ratio(db, b_first, b_last, sick_type_ids) if sick_type_ids else None
        fl = await _fluctuation(db, b_first, b_last)
        rpe = await _revenue_per_production_employee(db, b_first, b_last, prod_depts) if prod_depts else None
        points.append(HrKpiHistoryPoint(
            month=label,
            overtime_ratio=ot,
            sick_leave_ratio=sl,
            fluctuation=fl,
            revenue_per_production_employee=rpe,
        ))
    return points
