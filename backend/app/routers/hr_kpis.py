"""HR KPI endpoints — aggregated over arbitrary [date_from, date_to] windows.

Phase 60 reverses the original D-03 (fixed calendar month windows only).
Both /kpis and /kpis/history now accept date_from + date_to query params;
when both are omitted, endpoints fall back to current-month (/kpis) or
last-12-months (/kpis/history) for backward compatibility with the
thisYear landing experience.

Compute-justified: clause 3 (multi-row HR KPI aggregation).
"""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import require_dashboard_read
from app.security.fernet import decrypt_credential
from app.models import AppSettings, PersonioEmployee
from app.schemas import HrKpiHistoryPoint, HrKpiResponse
from app.services.personio_client import PersonioAPIError, PersonioClient
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
    dependencies=[Depends(require_dashboard_read)],
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


def _bucket_windows(
    first: date,
    last: date,
    granularity: str | None = None,
) -> list[tuple[str, date, date]]:
    """Return ordered [(label, bucket_first, bucket_last), ...] covering [first, last].

    Default (``granularity=None``) auto-picks by range length (D-06):
      length_days <= 31  -> daily   (label "YYYY-MM-DD")
      length_days <= 91  -> weekly  (label "YYYY-Www", ISO week)
      length_days <= 731 -> monthly (label "YYYY-MM")
      else               -> quarterly (label "YYYY-Qn")

    Explicit ``granularity`` overrides the auto-pick:
      "daily" / "weekly" / "monthly" / "quarterly" / "yearly"

    Yearly label: "YYYY". Bucket edges are always clipped to [first, last].
    Order is oldest-first.
    """
    length_days = (last - first).days + 1
    buckets: list[tuple[str, date, date]] = []

    if length_days <= 0:
        return buckets

    if granularity is None:
        if length_days <= 31:
            granularity = "daily"
        elif length_days <= 91:
            granularity = "weekly"
        elif length_days <= 731:
            granularity = "monthly"
        else:
            granularity = "quarterly"

    if granularity == "daily":
        d = first
        while d <= last:
            buckets.append((d.isoformat(), d, d))
            d += timedelta(days=1)
        return buckets

    if granularity == "weekly":
        # ISO week, Mon-Sun
        d = first
        while d <= last:
            weekday = d.weekday()  # Mon=0
            week_start = d - timedelta(days=weekday)
            week_end = week_start + timedelta(days=6)
            bucket_first = max(week_start, first)
            bucket_last = min(week_end, last)
            iso_year, iso_week, _ = d.isocalendar()
            label = f"{iso_year}-W{iso_week:02d}"
            buckets.append((label, bucket_first, bucket_last))
            d = week_end + timedelta(days=1)
        return buckets

    if granularity == "monthly":
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

    if granularity == "quarterly":
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

    if granularity == "yearly":
        for y in range(first.year, last.year + 1):
            yf = date(y, 1, 1)
            yl = date(y, 12, 31)
            bucket_first = max(yf, first)
            bucket_last = min(yl, last)
            buckets.append((str(y), bucket_first, bucket_last))
        return buckets

    raise HTTPException(
        status_code=400,
        detail=(
            f"Unknown granularity={granularity!r}. "
            "Allowed: daily, weekly, monthly, quarterly, yearly"
        ),
    )
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


# ---------------------------------------------------------------------------
# Birthdays — current-week roster from Personio raw_json
# ---------------------------------------------------------------------------


class BirthdayEntry(BaseModel):
    """One employee with a birthday in the current ISO week."""

    employee_id: int
    first_name: str | None
    last_name: str | None
    department: str | None
    birthday: date          # full DOB (YYYY-MM-DD)
    weekday: int            # 0 = Monday … 6 = Sunday — week-relative
    occurs_on: date         # this year's anniversary date (handles Feb 29)
    age_turning: int        # age the employee turns on `occurs_on`
    # True when Personio's raw_json carries a non-null Profile Picture URL.
    # The frontend uses this to decide whether to attempt the photo proxy
    # endpoint (skipping the fetch avoids a 404 per employee with no photo).
    has_photo: bool


class JoinerEntry(BaseModel):
    """One active employee who started in the last 2 weeks."""

    employee_id: int
    first_name: str | None
    last_name: str | None
    department: str | None
    hire_date: date
    days_with_company: int  # today - hire_date (0 if hire_date == today)
    has_photo: bool


def _is_currently_active(status: str | None, termination_date: date | None, today: date) -> bool:
    """Personio 'active' OR future termination_date — i.e. still on the books today.

    Onboarding employees haven't started yet (no hire_date / future hire_date)
    so they're excluded from both feeds.
    """
    if status != "active":
        return False
    if termination_date is not None and termination_date <= today:
        return False
    return True


def _find_birthday_in_raw(raw: Any) -> str | None:
    """Walk Personio's nested raw_json and return the `value` of any node whose
    `label == "Geburtsdatum"`. Returns None if absent or not a string.

    Personio shape varies: birthday lives inside ``attributes.<key>.{label, value}``
    in the v1 API but can also appear under nested ``children`` arrays. We do a
    plain recursive scan instead of pinning a path so the resolver survives
    Personio's schema drift.
    """
    if isinstance(raw, dict):
        if raw.get("label") == "Geburtsdatum":
            v = raw.get("value")
            return v if isinstance(v, str) and v else None
        for v in raw.values():
            found = _find_birthday_in_raw(v)
            if found is not None:
                return found
    elif isinstance(raw, list):
        for item in raw:
            found = _find_birthday_in_raw(item)
            if found is not None:
                return found
    return None


def _parse_birthday(raw_value: str) -> date | None:
    """Accept the ISO-ish strings Personio uses (full timestamp or plain date)."""
    # Personio returns "1977-02-15T00:00:00+01:00" — fromisoformat handles both.
    try:
        parsed = datetime.fromisoformat(raw_value)
        return parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(raw_value[:10])
        except ValueError:
            return None


def _anniversary_in_year(dob: date, year: int) -> date:
    """Project a DOB onto the given year. Feb 29 → Feb 28 in non-leap years."""
    try:
        return dob.replace(year=year)
    except ValueError:
        return dob.replace(year=year, day=28)


def _has_profile_picture(raw: Any) -> bool:
    """Return True if raw_json carries a non-null Profile Picture URL."""
    if isinstance(raw, dict):
        if raw.get("label") == "Profile Picture":
            return bool(raw.get("value"))
        for v in raw.values():
            if _has_profile_picture(v):
                return True
    elif isinstance(raw, list):
        for item in raw:
            if _has_profile_picture(item):
                return True
    return False


@router.get("/birthdays/this-week", response_model=list[BirthdayEntry])
async def get_birthdays_this_week(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[BirthdayEntry]:
    """Return the active employees whose birthday falls in the current ISO week.

    Week boundary = Monday 00:00 .. Sunday 23:59 (date-only comparison).
    "Active" = no termination_date set, or termination_date in the future.
    Result is sorted by `occurs_on`, then last_name + first_name for stability.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    # The week can straddle a year boundary (Dec 30..Jan 5). Check both years.
    candidate_years = {monday.year, sunday.year}

    rows = (
        await db.execute(
            sa_select(
                PersonioEmployee.id,
                PersonioEmployee.first_name,
                PersonioEmployee.last_name,
                PersonioEmployee.department,
                PersonioEmployee.status,
                PersonioEmployee.termination_date,
                PersonioEmployee.raw_json,
            )
        )
    ).all()

    entries: list[BirthdayEntry] = []
    for r in rows:
        if not _is_currently_active(r.status, r.termination_date, today):
            continue
        raw_val = _find_birthday_in_raw(r.raw_json)
        if not raw_val:
            continue
        dob = _parse_birthday(raw_val)
        if dob is None:
            continue
        for year in candidate_years:
            occurs = _anniversary_in_year(dob, year)
            if monday <= occurs <= sunday:
                entries.append(
                    BirthdayEntry(
                        employee_id=r.id,
                        first_name=r.first_name,
                        last_name=r.last_name,
                        department=r.department,
                        birthday=dob,
                        weekday=occurs.weekday(),
                        occurs_on=occurs,
                        age_turning=year - dob.year,
                        has_photo=_has_profile_picture(r.raw_json),
                    )
                )
                break  # avoid the duplicate when monday.year == sunday.year

    entries.sort(
        key=lambda e: (e.occurs_on, (e.last_name or "").lower(), (e.first_name or "").lower())
    )
    return entries


@router.get("/joiners/recent", response_model=list[JoinerEntry])
async def get_joiners_recent(
    weeks: int = Query(2, ge=1, le=52),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[JoinerEntry]:
    """Active employees whose hire_date is within the last `weeks` weeks (default 2).

    Excludes status != 'active', terminated rows, future hire_dates, and
    NULL hire_dates. Sorted by hire_date desc (newest first) with last_name
    + first_name as the tiebreaker.
    """
    today = date.today()
    earliest = today - timedelta(weeks=weeks)
    rows = (
        await db.execute(
            sa_select(
                PersonioEmployee.id,
                PersonioEmployee.first_name,
                PersonioEmployee.last_name,
                PersonioEmployee.department,
                PersonioEmployee.status,
                PersonioEmployee.hire_date,
                PersonioEmployee.termination_date,
                PersonioEmployee.raw_json,
            )
        )
    ).all()

    out: list[JoinerEntry] = []
    for r in rows:
        if not _is_currently_active(r.status, r.termination_date, today):
            continue
        if r.hire_date is None:
            continue
        if r.hire_date < earliest or r.hire_date > today:
            continue
        out.append(
            JoinerEntry(
                employee_id=r.id,
                first_name=r.first_name,
                last_name=r.last_name,
                department=r.department,
                hire_date=r.hire_date,
                days_with_company=(today - r.hire_date).days,
                has_photo=_has_profile_picture(r.raw_json),
            )
        )

    out.sort(
        key=lambda e: (
            -(e.hire_date.toordinal()),
            (e.last_name or "").lower(),
            (e.first_name or "").lower(),
        )
    )
    return out


@router.get("/employees/{employee_id}/photo")
async def get_employee_photo(
    employee_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Authenticated proxy for the Personio profile picture of one employee.

    The Personio asset URL needs a Personio bearer and CORS-blocks the
    browser; this route hides both. Returns the image bytes with a 1-hour
    browser cache so repeat renders in the same session don't refetch.
    404 when the row is missing, when Personio has no picture, or when
    Personio credentials aren't configured (treated as "no photo").
    """
    emp = (
        await db.execute(sa_select(PersonioEmployee).where(PersonioEmployee.id == employee_id))
    ).scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="employee not found")

    settings_row = (
        await db.execute(sa_select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()
    if (
        settings_row is None
        or not settings_row.personio_client_id_enc
        or not settings_row.personio_client_secret_enc
    ):
        raise HTTPException(status_code=404, detail="personio credentials not configured")

    client_id = decrypt_credential(settings_row.personio_client_id_enc)
    client_secret = decrypt_credential(settings_row.personio_client_secret_enc)
    client = PersonioClient(client_id=client_id, client_secret=client_secret)
    try:
        result = await client.fetch_profile_picture(employee_id)
    except PersonioAPIError as exc:
        raise HTTPException(status_code=502, detail="personio fetch failed") from exc
    finally:
        await client.close()

    if result is None:
        raise HTTPException(status_code=404, detail="no profile picture")

    body, content_type = result
    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


class OrgChartNode(BaseModel):
    """One employee node for the HR org chart.

    ``supervisor_id`` is the Personio id of the employee's manager, extracted
    from the raw payload (attributes.supervisor.value.attributes.id.value).
    ``None`` means top of hierarchy — the frontend treats such nodes (and any
    node whose supervisor is not in the active set) as roots.
    """

    id: int
    first_name: str | None
    last_name: str | None
    position: str | None
    department: str | None
    office: str | None
    supervisor_id: int | None


def _extract_office(raw: Any) -> str | None:
    """Dig the Personio office/workplace name out of a raw employee payload.

    Path: attributes.office.value.attributes.name (Personio's standard
    ``universal_id: office`` "Workplace" field, e.g. "Hamburg").
    """
    if not isinstance(raw, dict):
        return None
    value = raw.get("attributes", {}).get("office", {}).get("value")
    if not isinstance(value, dict):
        return None
    name = value.get("attributes", {}).get("name")
    return name if isinstance(name, str) and name else None


def _extract_supervisor_id(raw: Any) -> int | None:
    """Dig the supervisor's employee id out of a raw Personio employee payload."""
    if not isinstance(raw, dict):
        return None
    value = (
        raw.get("attributes", {})
        .get("supervisor", {})
        .get("value")
    )
    if not isinstance(value, dict):
        return None
    id_field = value.get("attributes", {}).get("id", {})
    sid = id_field.get("value") if isinstance(id_field, dict) else None
    try:
        return int(sid) if sid is not None else None
    except (ValueError, TypeError):
        return None


@router.get("/org-chart", response_model=list[OrgChartNode])
async def get_org_chart(
    session: AsyncSession = Depends(get_async_db_session),
) -> list[OrgChartNode]:
    """Active employees plus their supervisor id, for the HR org chart.

    Reads already-synced Personio employees from the DB (no live API call);
    supervisor links come from the stored raw payload.
    """
    rows = (
        await session.execute(
            sa_select(PersonioEmployee).where(PersonioEmployee.status == "active")
        )
    ).scalars().all()
    return [
        OrgChartNode(
            id=emp.id,
            first_name=emp.first_name,
            last_name=emp.last_name,
            position=emp.position,
            department=emp.department,
            office=_extract_office(emp.raw_json),
            supervisor_id=_extract_supervisor_id(emp.raw_json),
        )
        for emp in rows
    ]
