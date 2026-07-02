"""Personalkostenquote aggregation (Finanzperspektive, v1.72).

Formula
-------
    ratio = personnel_cost(window) / revenue(window)

where, over the window [first, last]:

* **personnel_cost** = Σ over employees of their gross cost in the window:
  - Salaried (``fix_salary`` > 0, always monthly here): the monthly gross is
    prorated day-by-day over the days the employee is *active* in the window
    (hire_date ≤ day ≤ termination_date). A full active month = one monthly
    salary; partial months are prorated by active-days / days-in-month.
  - Hourly (``hourly_salary`` > 0, no fix_salary): hourly gross × the actual
    hours worked in the window, taken from ``personio_attendance``
    (``end − start − break``).
  - Gross only — no employer-overhead factor (per the chosen config).
  - Salary is read from the Personio ``raw_json`` snapshot (current values,
    applied to every period — there is no salary history).
* **revenue** = ``SUM(revenues.wert_eur)`` over the window (RG/GS net Umsatz —
  the same denominator as the Materialkostenquote).

Returns the ratio as a fraction (0.30 → 30 %). Lower is better.

Privacy: this module only ever returns aggregates (company total + per-
department). Individual employee salaries are never exposed.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PersonioAttendance, PersonioEmployee, Revenue
from app.services.hr_kpi_aggregation import (
    prior_window_same_length,
    same_window_prior_year,
)


def _to_float(val) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


async def _salaries(
    db: AsyncSession,
) -> list[tuple[int, str | None, date | None, date | None, float | None, float | None]]:
    """Return (id, department, hire_date, termination_date, fix_salary, hourly_salary).

    Salary values are pulled from the Personio ``raw_json`` snapshot. ``fix_salary``
    is a monthly gross here (Personio ``fix_salary_interval`` = 'monthly').
    """
    E = PersonioEmployee
    stmt = select(
        E.id,
        E.department,
        E.hire_date,
        E.termination_date,
        E.raw_json["attributes"]["fix_salary"]["value"].astext,
        E.raw_json["attributes"]["hourly_salary"]["value"].astext,
    )
    rows = (await db.execute(stmt)).all()
    out = []
    for emp_id, dept, hire, term, fix_s, hourly_s in rows:
        out.append((emp_id, dept, hire, term, _to_float(fix_s), _to_float(hourly_s)))
    return out


async def _attendance_hours(
    db: AsyncSession, first: date, last: date
) -> dict[int, float]:
    """Worked hours per employee in [first, last] from attendance (end−start−break)."""
    A = PersonioAttendance
    hours_expr = (
        func.extract("epoch", A.end_time - A.start_time) / 3600.0
        - A.break_minutes / 60.0
    )
    stmt = (
        select(A.employee_id, func.coalesce(func.sum(hours_expr), 0.0))
        .where(
            A.date >= first,
            A.date <= last,
            A.start_time.isnot(None),
            A.end_time.isnot(None),
        )
        .group_by(A.employee_id)
    )
    rows = (await db.execute(stmt)).all()
    return {emp_id: max(0.0, float(h or 0)) for emp_id, h in rows}


def _fixed_cost_in_window(
    monthly: float,
    hire: date | None,
    term: date | None,
    first: date,
    last: date,
) -> float:
    """Monthly gross prorated by active days, month by month, across the window."""
    total = 0.0
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        dim = monthrange(y, m)[1]
        m_first, m_last = date(y, m, 1), date(y, m, dim)
        a_start = max(m_first, first, hire or m_first)
        a_end = min(m_last, last, term or m_last)
        if a_end >= a_start:
            active_days = (a_end - a_start).days + 1
            total += monthly * active_days / dim
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return total


def _personnel_cost(
    salaries: list[tuple[int, str | None, date | None, date | None, float | None, float | None]],
    attendance_hours: dict[int, float],
    first: date,
    last: date,
) -> tuple[float, int, dict[str, dict]]:
    """Return (total_cost, headcount, by_department).

    ``by_department`` maps department → {"cost": float, "headcount": int}.
    An employee is salaried when fix_salary > 0, else hourly when
    hourly_salary > 0; anyone with neither contributes nothing.
    """
    total = 0.0
    headcount = 0
    by_dept: dict[str, dict] = {}
    for emp_id, dept, hire, term, fix_s, hourly_s in salaries:
        if fix_s and fix_s > 0:
            cost = _fixed_cost_in_window(fix_s, hire, term, first, last)
        elif hourly_s and hourly_s > 0:
            cost = hourly_s * attendance_hours.get(emp_id, 0.0)
        else:
            continue
        if cost <= 0:
            continue
        total += cost
        headcount += 1
        key = dept or "—"
        d = by_dept.setdefault(key, {"cost": 0.0, "headcount": 0})
        d["cost"] += cost
        d["headcount"] += 1
    return total, headcount, by_dept


async def _revenue_for_window(db: AsyncSession, first: date, last: date) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(Revenue.wert_eur), 0)).where(
                Revenue.datum >= first, Revenue.datum <= last
            )
        )
    ).scalar_one() or 0
    return float(total)


def _ratio(cost: float, revenue: float) -> float | None:
    if revenue <= 0:
        return None
    return cost / revenue


async def _ratio_for_window(
    db: AsyncSession,
    salaries,
    first: date,
    last: date,
) -> float | None:
    cost, _, _ = _personnel_cost(
        salaries, await _attendance_hours(db, first, last), first, last
    )
    revenue = await _revenue_for_window(db, first, last)
    return _ratio(cost, revenue)


async def compute_personnel_cost_ratio(
    db: AsyncSession, first: date, last: date
) -> dict:
    """Personalkostenquote for the window with prev-period / prev-year baselines."""
    salaries = await _salaries(db)

    cost, headcount, _ = _personnel_cost(
        salaries, await _attendance_hours(db, first, last), first, last
    )
    revenue = await _revenue_for_window(db, first, last)

    p_first, p_last = prior_window_same_length(first, last)
    y_first, y_last = same_window_prior_year(first, last)

    return {
        "ratio": _ratio(cost, revenue),
        "personnel_cost": round(cost, 2),
        "revenue": round(revenue, 2),
        "headcount": headcount,
        "previous_period": await _ratio_for_window(db, salaries, p_first, p_last),
        "previous_year": await _ratio_for_window(db, salaries, y_first, y_last),
    }


async def compute_personnel_cost_ratio_history(
    db: AsyncSession, buckets: list[tuple[str, date, date]]
) -> list[dict]:
    """Per-bucket Personalkostenquote; ``buckets`` from ``_bucket_windows``."""
    salaries = await _salaries(db)
    points: list[dict] = []
    for label, b_first, b_last in buckets:
        cost, _, _ = _personnel_cost(
            salaries, await _attendance_hours(db, b_first, b_last), b_first, b_last
        )
        revenue = await _revenue_for_window(db, b_first, b_last)
        points.append({
            "month": label,
            "ratio": _ratio(cost, revenue),
            "personnel_cost": round(cost, 2),
            "revenue": round(revenue, 2),
        })
    return points


async def list_personnel_cost_ratio(
    db: AsyncSession, first: date, last: date
) -> list[dict]:
    """Per-department personnel-cost breakdown for the verification table.

    Aggregated per department (never per employee) so individual salaries are
    not exposed. Sorted by cost descending.
    """
    salaries = await _salaries(db)
    _, _, by_dept = _personnel_cost(
        salaries, await _attendance_hours(db, first, last), first, last
    )
    rows = [
        {
            "department": dept,
            "headcount": d["headcount"],
            "personnel_cost": round(d["cost"], 2),
        }
        for dept, d in by_dept.items()
    ]
    rows.sort(key=lambda r: r["personnel_cost"], reverse=True)
    return rows
