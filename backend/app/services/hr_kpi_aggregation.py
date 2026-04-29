"""HR KPI aggregation service — computes all 5 HR KPIs for arbitrary [first_day, last_day] windows.

Fluctuation denominator is average active headcount across the window (D-03 Phase 60;
replaces end-of-month snapshot). Sequential awaits only on the shared AsyncSession
(no asyncio.gather per Pitfall 2).
"""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select, and_, or_, cast, Integer as SAInteger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AppSettings,
    PersonioAbsence,
    PersonioAttendance,
    PersonioEmployee,
    SalesRecord,
)
from app.schemas import HrKpiResponse, HrKpiValue
from app.services.kpi_aggregation import aggregate_kpi_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return (first_day, last_day) for a calendar month."""
    last_day_num = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day_num)


def _prev_month(year: int, month: int) -> tuple[int, int]:
    """Return (year, month) for the previous calendar month.

    Handles January underflow (Pitfall 4 in RESEARCH.md).
    """
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _weekday_count(first_day: date, last_day: date) -> int:
    """Count weekdays (Mon-Fri) in the inclusive date range."""
    count = 0
    d = first_day
    while d <= last_day:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count


def prior_window_same_length(first_day: date, last_day: date) -> tuple[date, date]:
    """Return the window of identical length ending the day before first_day.

    Used by HR KPI endpoints to produce D-02 deltas (prior window of same length).
    45-day range → prior 45 days. (2026-04-01, 2026-04-15) → (2026-03-17, 2026-03-31).
    """
    length_days = (last_day - first_day).days + 1
    prev_last = first_day - timedelta(days=1)
    prev_first = prev_last - timedelta(days=length_days - 1)
    return prev_first, prev_last


def same_window_prior_year(first_day: date, last_day: date) -> tuple[date, date]:
    """Return the same-length window shifted 365 days earlier.

    Leap-day drift is acceptable per CONTEXT discretion — we keep range length
    identical rather than attempting calendar-aware anniversary math.
    """
    return first_day - timedelta(days=365), last_day - timedelta(days=365)


# ---------------------------------------------------------------------------
# Headcount helpers
# ---------------------------------------------------------------------------


async def _headcount_at_eom(
    session: AsyncSession,
    last_day: date,
    departments: list[str] | None = None,
) -> int:
    """Count active employees as of *last_day*.

    Active = hire_date <= last_day AND (termination_date IS NULL OR termination_date > last_day).
    When *departments* is given, filter by IN match (any selected department).

    Retained for point-in-time denominators (skill development, revenue/production-dept);
    fluctuation no longer uses this helper — see `_fluctuation` (D-03 Phase 60).
    """
    stmt = select(func.count(PersonioEmployee.id)).where(
        PersonioEmployee.hire_date <= last_day,
        or_(
            PersonioEmployee.termination_date.is_(None),
            PersonioEmployee.termination_date > last_day,
        ),
    )
    if departments:
        stmt = stmt.where(PersonioEmployee.department.in_(departments))
    result = await session.execute(stmt)
    return result.scalar_one() or 0


async def _avg_active_headcount_across_range(
    session: AsyncSession,
    first_day: date,
    last_day: date,
    departments: list[str] | None = None,
) -> float:
    """Return mean active-employee count over every calendar day in [first_day, last_day].

    For each day d in range: active = hire_date <= d AND (termination_date IS NULL OR termination_date > d).
    Computed in Python from a single SELECT of (hire_date, termination_date) rows whose
    contracts overlap the range.
    """
    total_days = (last_day - first_day).days + 1
    if total_days <= 0:
        return 0.0

    stmt = select(
        PersonioEmployee.hire_date,
        PersonioEmployee.termination_date,
    ).where(
        PersonioEmployee.hire_date <= last_day,
        or_(
            PersonioEmployee.termination_date.is_(None),
            PersonioEmployee.termination_date >= first_day,
        ),
    )
    if departments:
        stmt = stmt.where(PersonioEmployee.department.in_(departments))

    rows = (await session.execute(stmt)).all()
    if not rows:
        return 0.0

    total_active_day_count = 0
    d = first_day
    while d <= last_day:
        count = 0
        for row in rows:
            if row.hire_date is None or row.hire_date > d:
                continue
            if row.termination_date is not None and row.termination_date <= d:
                continue
            count += 1
        total_active_day_count += count
        d += timedelta(days=1)

    return total_active_day_count / total_days


# ---------------------------------------------------------------------------
# Individual KPI computations
# ---------------------------------------------------------------------------


async def _overtime_ratio(
    session: AsyncSession,
    first_day: date,
    last_day: date,
) -> float | None:
    """HRKPI-01: overtime hours / total hours from attendance records.

    Overtime per record = max(0, worked_hours - daily_quota).
    Daily quota = weekly_working_hours / 5.
    """
    stmt = (
        select(
            PersonioAttendance.start_time,
            PersonioAttendance.end_time,
            PersonioAttendance.break_minutes,
            PersonioEmployee.weekly_working_hours,
        )
        .join(
            PersonioEmployee,
            PersonioAttendance.employee_id == PersonioEmployee.id,
        )
        .where(
            PersonioAttendance.date >= first_day,
            PersonioAttendance.date <= last_day,
        )
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return None

    total_hours = 0.0
    overtime_hours = 0.0

    for row in rows:
        if row.start_time is None or row.end_time is None:
            continue
        start_minutes = row.start_time.hour * 60 + row.start_time.minute
        end_minutes = row.end_time.hour * 60 + row.end_time.minute
        worked = (end_minutes - start_minutes - (row.break_minutes or 0)) / 60.0
        if worked <= 0:
            continue

        total_hours += worked

        if row.weekly_working_hours is not None:
            daily_quota = float(row.weekly_working_hours) / 5.0
            overtime_hours += max(0.0, worked - daily_quota)

    if total_hours == 0:
        return None
    return overtime_hours / total_hours


async def _sick_leave_ratio(
    session: AsyncSession,
    first_day: date,
    last_day: date,
    sick_leave_type_ids: list[int],
) -> float | None:
    """HRKPI-02: sick leave hours / total scheduled hours.

    Uses overlap logic: start_date <= last_day AND end_date >= first_day (Pitfall 1).
    """
    # Numerator: sick hours
    absence_stmt = (
        select(
            PersonioAbsence.start_date,
            PersonioAbsence.end_date,
            PersonioAbsence.time_unit,
            PersonioAbsence.hours,
            PersonioAbsence.employee_id,
        )
        .where(
            PersonioAbsence.absence_type_id.in_(sick_leave_type_ids),
            PersonioAbsence.start_date <= last_day,
            PersonioAbsence.end_date >= first_day,
        )
    )
    absences = (await session.execute(absence_stmt)).all()

    # Fetch employee weekly hours for per-employee daily rate
    emp_hours_stmt = select(
        PersonioEmployee.id,
        PersonioEmployee.weekly_working_hours,
    )
    emp_rows = (await session.execute(emp_hours_stmt)).all()
    emp_weekly: dict[int, float] = {
        r.id: float(r.weekly_working_hours) if r.weekly_working_hours is not None else 40.0
        for r in emp_rows
    }

    sick_hours = 0.0
    for ab in absences:
        clipped_start = max(ab.start_date, first_day)
        clipped_end = min(ab.end_date, last_day)
        clipped_days = (clipped_end - clipped_start).days + 1
        if clipped_days <= 0:
            continue

        if ab.time_unit == "hours" and ab.hours is not None:
            total_absence_days = (ab.end_date - ab.start_date).days + 1
            if total_absence_days > 0:
                sick_hours += float(ab.hours) * clipped_days / total_absence_days
        else:
            daily_rate = emp_weekly.get(ab.employee_id, 40.0) / 5.0
            sick_hours += daily_rate * clipped_days

    # Denominator: total scheduled hours for all active employees
    weekdays = _weekday_count(first_day, last_day)
    if weekdays == 0:
        return None

    # Active employees at end of month
    active_stmt = select(
        PersonioEmployee.weekly_working_hours,
    ).where(
        PersonioEmployee.hire_date <= last_day,
        or_(
            PersonioEmployee.termination_date.is_(None),
            PersonioEmployee.termination_date > last_day,
        ),
    )
    active_emps = (await session.execute(active_stmt)).all()
    if not active_emps:
        return None

    total_scheduled = 0.0
    for emp in active_emps:
        weekly = float(emp.weekly_working_hours) if emp.weekly_working_hours is not None else 40.0
        total_scheduled += (weekly / 5.0) * weekdays

    if total_scheduled == 0:
        return None
    return sick_hours / total_scheduled


async def _fluctuation(
    session: AsyncSession,
    first_day: date,
    last_day: date,
) -> float | None:
    """HRKPI-03: leavers_in_range / avg_active_headcount_across_range (D-03 Phase 60).

    Denominator is the mean active headcount across every calendar day in the window
    (replaces the prior end-of-month snapshot). Returns None when the average is 0
    or the window is degenerate.
    """
    if (last_day - first_day).days + 1 <= 0:
        return None

    leavers_stmt = select(func.count(PersonioEmployee.id)).where(
        PersonioEmployee.termination_date >= first_day,
        PersonioEmployee.termination_date <= last_day,
    )
    leavers = (await session.execute(leavers_stmt)).scalar_one() or 0

    avg_headcount = await _avg_active_headcount_across_range(session, first_day, last_day)
    if avg_headcount == 0:
        return None
    return leavers / avg_headcount


async def _skill_development(
    session: AsyncSession,
    last_day: date,
    skill_attr_keys: list[str],
) -> float | None:
    """HRKPI-04: employees with non-null configured skill attribute / total headcount.

    Proxy metric: employees with current non-null value for ANY of the configured
    attributes. No historical snapshot table exists — point-in-time snapshot at `last_day`.
    """
    headcount = await _headcount_at_eom(session, last_day)
    if headcount == 0:
        return None

    # Query active employees with non-null skill attribute value in raw_json
    # JSONB path: raw_json -> 'attributes' -> key -> 'value' for any of skill_attr_keys
    skilled_stmt = select(func.count(PersonioEmployee.id)).where(
        PersonioEmployee.hire_date <= last_day,
        or_(
            PersonioEmployee.termination_date.is_(None),
            PersonioEmployee.termination_date > last_day,
        ),
        PersonioEmployee.raw_json.isnot(None),
        or_(*(
            PersonioEmployee.raw_json["attributes"][key]["value"].as_string().notin_(["null", ""])
            for key in skill_attr_keys
        )),
    )
    skilled = (await session.execute(skilled_stmt)).scalar_one() or 0
    return skilled / headcount


async def _revenue_per_production_employee(
    session: AsyncSession,
    first_day: date,
    last_day: date,
    production_depts: list[str],
) -> float | None:
    """HRKPI-05: total range revenue / production dept headcount.

    Revenue numerator reuses aggregate_kpi_summary (same SQL as Sales dashboard).
    Denominator is production-department headcount at end of range.
    """
    summary = await aggregate_kpi_summary(session, first_day, last_day)
    if summary is None:
        return None
    revenue = float(summary["total_revenue"])
    if revenue <= 0:
        return None

    headcount = await _headcount_at_eom(session, last_day, departments=production_depts)
    if headcount == 0:
        return None
    return revenue / headcount


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def compute_hr_kpis(db: AsyncSession, first: date, last: date) -> HrKpiResponse:
    """Compute all 5 HR KPIs over [first, last] as a single window (D-01/D-04/D-05).

    Deltas:
      - previous_period: same-length window immediately before `first` (D-02).
      - previous_year: same-length window shifted 365 days earlier (back-compat).

    Sequential awaits on the shared AsyncSession (no asyncio.gather per Pitfall 2).
    """
    cur_first, cur_last = first, last
    prev_first, prev_last = prior_window_same_length(first, last)
    ya_first, ya_last = same_window_prior_year(first, last)

    # Load singleton settings
    from sqlalchemy import select as sa_select

    settings_row = (
        await db.execute(sa_select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()

    sick_type_ids: list[int] = (settings_row.personio_sick_leave_type_id or []) if settings_row else []
    prod_depts: list[str] = (settings_row.personio_production_dept or []) if settings_row else []
    skill_keys: list[str] = (settings_row.personio_skill_attr_key or []) if settings_row else []

    # --- Overtime Ratio (always configured) ---
    ot_cur = await _overtime_ratio(db, first, last)
    ot_prev = await _overtime_ratio(db, prev_first, prev_last)
    ot_ya = await _overtime_ratio(db, ya_first, ya_last)

    # --- Sick Leave Ratio (needs sick_leave_type_id) ---
    if sick_type_ids:
        sl_cur = await _sick_leave_ratio(db, first, last, sick_type_ids)
        sl_prev = await _sick_leave_ratio(db, prev_first, prev_last, sick_type_ids)
        sl_ya = await _sick_leave_ratio(db, ya_first, ya_last, sick_type_ids)
        sick_kpi = HrKpiValue(
            value=sl_cur, previous_period=sl_prev, previous_year=sl_ya
        )
    else:
        sick_kpi = HrKpiValue(value=None, is_configured=False)

    # --- Fluctuation (always configured) ---
    fl_cur = await _fluctuation(db, first, last)
    fl_prev = await _fluctuation(db, prev_first, prev_last)
    fl_ya = await _fluctuation(db, ya_first, ya_last)

    # --- Skill Development (needs skill_attr_keys; point-in-time at last) ---
    if skill_keys:
        sd_cur = await _skill_development(db, cur_last, skill_keys)
        sd_prev = await _skill_development(db, prev_last, skill_keys)
        sd_ya = await _skill_development(db, ya_last, skill_keys)
        skill_kpi = HrKpiValue(
            value=sd_cur, previous_period=sd_prev, previous_year=sd_ya
        )
    else:
        skill_kpi = HrKpiValue(value=None, is_configured=False)

    # --- Revenue per Production Employee (needs production_depts) ---
    if prod_depts:
        rpe_cur = await _revenue_per_production_employee(db, first, last, prod_depts)
        rpe_prev = await _revenue_per_production_employee(db, prev_first, prev_last, prod_depts)
        rpe_ya = await _revenue_per_production_employee(db, ya_first, ya_last, prod_depts)
        rpe_kpi = HrKpiValue(
            value=rpe_cur, previous_period=rpe_prev, previous_year=rpe_ya
        )
    else:
        rpe_kpi = HrKpiValue(value=None, is_configured=False)

    return HrKpiResponse(
        overtime_ratio=HrKpiValue(
            value=ot_cur, previous_period=ot_prev, previous_year=ot_ya
        ),
        sick_leave_ratio=sick_kpi,
        fluctuation=HrKpiValue(
            value=fl_cur, previous_period=fl_prev, previous_year=fl_ya
        ),
        skill_development=skill_kpi,
        revenue_per_production_employee=rpe_kpi,
    )
