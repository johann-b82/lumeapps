"""Personio sync orchestrator — fetches data from Personio API and upserts into PostgreSQL.

Decisions:
  D-01: Manual sync is blocking — run_sync() awaits all fetches and upserts.
  D-03: Upsert by Personio ID via INSERT ... ON CONFLICT DO UPDATE.
  D-04: Sync results persisted to personio_sync_meta singleton.
"""
from datetime import date as date_type, datetime, time as time_type, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AppSettings,
    PersonioAbsence,
    PersonioAttendance,
    PersonioEmployee,
    PersonioSyncMeta,
    SalesEmployeeAlias,
)
from app.schemas import SyncResult
from app.security.fernet import decrypt_credential
from app.services.personio_client import PersonioAPIError, PersonioClient
from app.services.sales_aliases import canonical_token


# Incremental syncs re-fetch the trailing window so late-entered / edited
# attendance records are captured. 14 days matches typical payroll
# correction windows.
_INCREMENTAL_OVERLAP_DAYS = 14


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_sync(session: AsyncSession) -> SyncResult:
    """Fetch all Personio data and upsert into PostgreSQL.

    Executes fetches sequentially (not asyncio.gather) to avoid rate-limit
    bursts and to keep FK ordering safe: employees must be upserted before
    attendances and absences.

    Raises:
        PersonioAPIError: On any Personio API failure (after updating sync meta).
        ValueError: If Personio credentials are not configured.
    """
    settings = await _get_settings(session)

    if not settings.personio_client_id_enc or not settings.personio_client_secret_enc:
        raise ValueError("Personio credentials not configured — set them in Settings first")

    client_id = decrypt_credential(settings.personio_client_id_enc)
    client_secret = decrypt_credential(settings.personio_client_secret_enc)

    client = PersonioClient(client_id=client_id, client_secret=client_secret)
    emp_count = att_count = abs_count = 0

    try:
        # Sequential fetches — employees first for FK ordering
        raw_employees = await client.fetch_employees()

        # Attendance window (D-??, Phase 60 follow-up): first run fetches from
        # earliest employee hire_date (full backfill); subsequent runs fetch
        # max(stored_date) - 14d → today for an incremental update that
        # re-captures late-entered corrections.
        today = date_type.today()
        att_start = await _compute_attendance_window_start(session, raw_employees)
        raw_attendances = await client.fetch_attendances(
            start_date=att_start.isoformat(),
            end_date=today.isoformat(),
        )
        raw_absences = await client.fetch_absences()

        # Normalize
        employees = [_normalize_employee(r) for r in raw_employees]
        attendances = [_normalize_attendance(r) for r in raw_attendances]
        absences = [_normalize_absence(r) for r in raw_absences]

        # Upsert in FK order: employees -> attendances -> absences
        emp_count = await _upsert(session, PersonioEmployee, employees)
        att_count = await _upsert(session, PersonioAttendance, attendances)
        abs_count = await _upsert(session, PersonioAbsence, absences)

        # v1.41: rebuild canonical sales-rep aliases from the configured
        # sales departments. Manual aliases (is_canonical=False) are
        # never touched here.
        await rebuild_canonical_sales_aliases(session)

        await _update_sync_meta(session, emp_count, att_count, abs_count, "ok")

    except PersonioAPIError as exc:
        await _update_sync_meta(session, emp_count, att_count, abs_count, "error", str(exc))
        raise

    finally:
        await client.close()

    return SyncResult(
        employees_synced=emp_count,
        attendance_synced=att_count,
        absences_synced=abs_count,
        status="ok",
    )


# ---------------------------------------------------------------------------
# Normalizers — map nested Personio attributes.field_name.value to flat dicts
# ---------------------------------------------------------------------------


def _parse_time(val) -> time_type | None:
    """Parse a time string like '13:28' into a time object.

    Handles '24:00' (Personio uses it for end-of-day) by clamping to 23:59.
    """
    if val is None:
        return None
    if isinstance(val, time_type):
        return val
    if isinstance(val, str):
        parts = val.split(":")
        h, m = int(parts[0]), int(parts[1])
        if h >= 24:
            h, m = 23, 59
        return time_type(h, m)
    return None


def _parse_date(val) -> date_type | None:
    """Parse a date from various Personio formats (ISO timestamp, date string, or None)."""
    if val is None:
        return None
    if isinstance(val, date_type):
        return val
    if isinstance(val, str):
        return date_type.fromisoformat(val[:10])
    return None


def _attr_val(attrs: dict, key: str):
    """Extract value from a Personio attribute field.

    Personio wraps every field as {label, value, type, universal_id}.
    Some fields are flat scalars in certain endpoint responses.
    """
    field = attrs.get(key)
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    return field


def _normalize_employee(raw: dict) -> dict:
    """Extract flat fields from nested Personio employee response.

    Real shape: {type: "Employee", attributes: {id: {value: 123}, first_name: {value: "..."}, department: {value: {type: "Department", attributes: {name: "..."}}}}}
    """
    attrs = raw.get("attributes", {})
    dept_val = _attr_val(attrs, "department")
    if isinstance(dept_val, dict):
        dept_name = dept_val.get("attributes", {}).get("name")
    elif isinstance(dept_val, str):
        dept_name = dept_val
    else:
        dept_name = None
    return {
        "id": _attr_val(attrs, "id") or raw.get("id"),
        "first_name": _attr_val(attrs, "first_name"),
        "last_name": _attr_val(attrs, "last_name"),
        "status": _attr_val(attrs, "status"),
        "department": dept_name,
        "position": _attr_val(attrs, "position"),
        "hire_date": _parse_date(_attr_val(attrs, "hire_date")),
        "termination_date": _parse_date(_attr_val(attrs, "termination_date")),
        "weekly_working_hours": _attr_val(attrs, "weekly_working_hours"),
        "synced_at": datetime.now(timezone.utc),
        "raw_json": raw,
    }


def _normalize_attendance(raw: dict) -> dict:
    """Extract flat fields from nested Personio attendance response.

    Real shape: {id: 545436417, type: "AttendancePeriod", attributes: {employee: 22933156, date: "2025-03-27", start_time: "13:28", end_time: "13:28", break: 0, is_holiday: false}}
    Attendance attributes are flat scalars (not wrapped in {value:}).
    """
    attrs = raw.get("attributes", {})
    employee_id = _attr_val(attrs, "employee")
    if isinstance(employee_id, dict):
        employee_id = employee_id.get("attributes", {}).get("id", {}).get("value") or employee_id.get("id")
    return {
        "id": raw.get("id") or _attr_val(attrs, "id"),
        "employee_id": employee_id,
        "date": _parse_date(_attr_val(attrs, "date")),
        "start_time": _parse_time(_attr_val(attrs, "start_time")),
        "end_time": _parse_time(_attr_val(attrs, "end_time")),
        "break_minutes": _attr_val(attrs, "break") or 0,
        "is_holiday": _attr_val(attrs, "is_holiday") or False,
        "synced_at": datetime.now(timezone.utc),
        "raw_json": raw,
    }


def _normalize_absence(raw: dict) -> dict:
    """Extract flat fields from nested Personio absence response.

    Real shape: {type: "AbsencePeriod", attributes: {id: "uuid", measurement_unit: "hour",
    effective_duration: 300, employee: {type: "Employee", attributes: {id: {value: 123}, ...}},
    time_off_type: {type: "TimeOffType", attributes: {id: 568239, ...}},
    start_date: "2025-01-01T...", end_date: "2025-01-02T..."}}
    """
    attrs = raw.get("attributes", {})

    # Absence ID — UUID string in attributes
    absence_id = str(attrs.get("id") or raw.get("id"))

    # Employee ID — nested employee object with deeply wrapped id
    employee_ref = attrs.get("employee")
    if isinstance(employee_ref, dict):
        emp_attrs = employee_ref.get("attributes", {})
        emp_id_field = emp_attrs.get("id")
        if isinstance(emp_id_field, dict):
            employee_id = emp_id_field.get("value")
        else:
            employee_id = emp_id_field
    elif isinstance(employee_ref, int):
        employee_id = employee_ref
    else:
        employee_id = _attr_val(attrs, "employee_id")

    # Absence type ID — from absence_type.attributes.time_off_type_id (integer)
    type_ref = attrs.get("absence_type") or attrs.get("time_off_type") or attrs.get("type")
    absence_type_id = None
    if isinstance(type_ref, dict):
        type_attrs = type_ref.get("attributes", {})
        absence_type_id = type_attrs.get("time_off_type_id") or type_attrs.get("id")
        if not isinstance(absence_type_id, int):
            absence_type_id = None

    # Dates — real API uses "start"/"end" (ISO timestamps), not "start_date"/"end_date"
    start_raw = attrs.get("start") or _attr_val(attrs, "start_date")
    end_raw = attrs.get("end") or _attr_val(attrs, "end_date")

    return {
        "id": absence_id,
        "employee_id": employee_id,
        "absence_type_id": absence_type_id,
        "start_date": _parse_date(start_raw),
        "end_date": _parse_date(end_raw),
        "time_unit": attrs.get("measurement_unit") or _attr_val(attrs, "time_unit") or "days",
        "hours": attrs.get("effective_duration") or _attr_val(attrs, "hours"),
        "synced_at": datetime.now(timezone.utc),
        "raw_json": raw,
    }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def _upsert(session: AsyncSession, model, rows: list[dict]) -> int:
    """Generic INSERT ... ON CONFLICT DO UPDATE upsert for Personio models.

    Batches in chunks of 500 to stay under asyncpg's 32767 parameter limit.
    Returns the number of rows affected (inserted + updated).
    """
    if not rows:
        return 0
    total = 0
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        stmt = pg_insert(model).values(batch)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in model.__table__.columns
            if col.name != "id"
        }
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_=update_cols,
        )
        result = await session.execute(upsert_stmt)
        total += result.rowcount
    await session.commit()
    return total


async def _update_sync_meta(
    session: AsyncSession,
    emp_count: int,
    att_count: int,
    abs_count: int,
    status: str,
    error: str | None = None,
) -> None:
    """Update the personio_sync_meta singleton row (id=1)."""
    stmt = (
        update(PersonioSyncMeta)
        .where(PersonioSyncMeta.id == 1)
        .values(
            last_synced_at=datetime.now(timezone.utc),
            last_sync_status=status,
            last_sync_error=error,
            employees_synced=emp_count,
            attendance_synced=att_count,
            absences_synced=abs_count,
        )
    )
    await session.execute(stmt)
    await session.commit()


async def _compute_attendance_window_start(
    session: AsyncSession,
    raw_employees: list[dict],
) -> date_type:
    """Determine attendance fetch start date.

    If PersonioAttendance has any rows → incremental mode: start at
    max(date) - _INCREMENTAL_OVERLAP_DAYS (capture late edits).

    Otherwise → full-backfill mode: start at the earliest employee hire_date
    (no attendance can exist before anyone was hired). Falls back to
    today-395d if no hire dates are parseable (preserves prior behaviour for
    misconfigured tenants).
    """
    max_stored = await session.scalar(
        select(func.max(PersonioAttendance.date))
    )
    if max_stored is not None:
        return max_stored - timedelta(days=_INCREMENTAL_OVERLAP_DAYS)

    hire_dates: list[date_type] = []
    for raw in raw_employees:
        attrs = raw.get("attributes", {})
        hd = _parse_date(_attr_val(attrs, "hire_date"))
        if hd is not None:
            hire_dates.append(hd)
    if hire_dates:
        return min(hire_dates)

    today = date_type.today()
    return today.replace(day=1) - timedelta(days=395)


async def _get_settings(session: AsyncSession) -> AppSettings:
    """Fetch the AppSettings singleton row (id=1)."""
    result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
    return result.scalar_one()


async def rebuild_canonical_sales_aliases(session: AsyncSession) -> None:
    """Per Personio sync: drop and rebuild canonical sales alias rows.

    Manual rows (``is_canonical = False``) are NEVER touched. Canonical
    rows are derived from Personio employees whose ``department`` is in
    ``AppSettings.personio_sales_dept``. If a canonical token collides
    with an existing manual alias, the manual row wins (the canonical
    row is simply skipped).
    """
    settings_row = (
        await session.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()
    sales_depts: list[str] = (
        settings_row.personio_sales_dept or [] if settings_row else []
    )

    # Always drop existing canonical rows; rebuild below if config still has
    # any sales departments selected.
    await session.execute(
        delete(SalesEmployeeAlias).where(SalesEmployeeAlias.is_canonical.is_(True))
    )

    if not sales_depts:
        await session.commit()
        return

    employees = (
        await session.execute(
            select(PersonioEmployee).where(
                PersonioEmployee.department.in_(sales_depts)
            )
        )
    ).scalars().all()

    # Existing manual tokens — canonical rows that would collide are skipped.
    manual_tokens = {
        row[0]
        for row in (
            await session.execute(
                select(SalesEmployeeAlias.employee_token).where(
                    SalesEmployeeAlias.is_canonical.is_(False)
                )
            )
        ).all()
    }

    for emp in employees:
        token = canonical_token(emp.last_name)
        if not token or token in manual_tokens:
            continue
        session.add(
            SalesEmployeeAlias(
                personio_employee_id=emp.id,
                employee_token=token,
                is_canonical=True,
            )
        )
    await session.commit()
