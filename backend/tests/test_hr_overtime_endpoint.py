"""Phase 67 MIG-DATA-03: tests for GET /api/data/employees/overtime.

Ports the overtime compute assertions that previously lived on the
deleted /api/data/employees endpoint. Response shape is the flat
array [{employee_id, total_hours, overtime_hours, overtime_ratio}, ...]
— NOT the row-data shape. Assertions use row["employee_id"] (not row["id"]).

Status-code contract (CONTEXT D-06/D-07): 422, not 400, on missing or
inverted dates — mirrors FastAPI Query(...) native validation.
"""
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

from app.database import AsyncSessionLocal
from app.models import PersonioAttendance, PersonioEmployee
from tests.test_hr_kpi_range import _auth_headers, _emp_id, _cleanup_employees

pytestmark = pytest.mark.asyncio


OVERTIME_URL = "/api/data/employees/overtime"


async def test_overtime_range_scopes_attendance(client):
    """Seed 1 employee with an 8h attendance on 2026-04-10 and another on
    2026-05-10. Request April window — only April attendance contributes.
    """
    prefix = "ot-range-scope"
    emp = _emp_id(prefix, 0)
    async with AsyncSessionLocal() as session:
        session.add(PersonioEmployee(
            id=emp,
            first_name="Scope", last_name="Test",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        att_base = 9_820_000 + (abs(hash(prefix)) % 10_000) * 10
        session.add(PersonioAttendance(
            id=att_base,
            employee_id=emp,
            date=date(2026, 4, 10),
            start_time=time(8, 0), end_time=time(16, 0),  # 8h, no OT at 40h/week
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        session.add(PersonioAttendance(
            id=att_base + 1,
            employee_id=emp,
            date=date(2026, 5, 10),
            start_time=time(8, 0), end_time=time(16, 0),
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            res = await client.get(
                OVERTIME_URL,
                params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            rows = res.json()
            match = [r for r in rows if r["employee_id"] == emp]
            assert len(match) == 1, match
            row = match[0]
            assert row["total_hours"] == 8.0, row
            assert row["overtime_hours"] == 0.0, row
            # D-08: ot == 0 → overtime_ratio is None
            assert row["overtime_ratio"] is None
        finally:
            await _cleanup_employees(session, [emp])


async def test_overtime_null_times_skipped(client):
    """Attendance rows with start_time=None OR end_time=None contribute
    nothing. Employee with only null-time rows does not appear in the
    response (D-04: only employees with attendance in the window appear)."""
    prefix = "ot-null-times"
    emp = _emp_id(prefix, 0)
    async with AsyncSessionLocal() as session:
        session.add(PersonioEmployee(
            id=emp,
            first_name="Null", last_name="Times",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        att_base = 9_830_000 + (abs(hash(prefix)) % 10_000) * 10
        session.add(PersonioAttendance(
            id=att_base,
            employee_id=emp,
            date=date(2026, 4, 10),
            start_time=None, end_time=time(16, 0),
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        session.add(PersonioAttendance(
            id=att_base + 1,
            employee_id=emp,
            date=date(2026, 4, 11),
            start_time=time(8, 0), end_time=None,
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            res = await client.get(
                OVERTIME_URL,
                params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            rows = res.json()
            assert not [r for r in rows if r["employee_id"] == emp], rows
        finally:
            await _cleanup_employees(session, [emp])


async def test_overtime_break_subtraction(client):
    """9h shift (08:00–17:00) minus 60min break = 8h worked. At 40h/week,
    daily quota is 8h → overtime_hours == 0."""
    prefix = "ot-break"
    emp = _emp_id(prefix, 0)
    async with AsyncSessionLocal() as session:
        session.add(PersonioEmployee(
            id=emp,
            first_name="Break", last_name="Sub",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        att_base = 9_840_000 + (abs(hash(prefix)) % 10_000) * 10
        session.add(PersonioAttendance(
            id=att_base,
            employee_id=emp,
            date=date(2026, 4, 10),
            start_time=time(8, 0), end_time=time(17, 0),  # 9h span
            break_minutes=60,                               # -1h
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            res = await client.get(
                OVERTIME_URL,
                params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            rows = res.json()
            match = [r for r in rows if r["employee_id"] == emp]
            assert len(match) == 1
            assert match[0]["total_hours"] == 8.0
            assert match[0]["overtime_hours"] == 0.0
            assert match[0]["overtime_ratio"] is None
        finally:
            await _cleanup_employees(session, [emp])


async def test_overtime_weekly_hours_fallback_to_8h(client):
    """Employee with weekly_working_hours=None → daily quota falls back
    to 8h. A 10h shift produces 2h overtime."""
    prefix = "ot-fallback"
    emp = _emp_id(prefix, 0)
    async with AsyncSessionLocal() as session:
        session.add(PersonioEmployee(
            id=emp,
            first_name="Weekly", last_name="Null",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=None,
            synced_at=datetime.now(timezone.utc),
        ))
        att_base = 9_850_000 + (abs(hash(prefix)) % 10_000) * 10
        session.add(PersonioAttendance(
            id=att_base,
            employee_id=emp,
            date=date(2026, 4, 10),
            start_time=time(8, 0), end_time=time(18, 0),  # 10h
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            res = await client.get(
                OVERTIME_URL,
                params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            rows = res.json()
            match = [r for r in rows if r["employee_id"] == emp]
            assert len(match) == 1
            assert match[0]["total_hours"] == 10.0
            assert match[0]["overtime_hours"] == 2.0
            # D-08: overtime_ratio = round(2 / 10, 4) = 0.2
            assert match[0]["overtime_ratio"] == 0.2
        finally:
            await _cleanup_employees(session, [emp])


async def test_overtime_zero_worked_hours_skipped(client):
    """When break_minutes swallows all worked time (worked <= 0), row is
    skipped. Employee disappears from response if that is their only row."""
    prefix = "ot-zero"
    emp = _emp_id(prefix, 0)
    async with AsyncSessionLocal() as session:
        session.add(PersonioEmployee(
            id=emp,
            first_name="Zero", last_name="Worked",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        att_base = 9_860_000 + (abs(hash(prefix)) % 10_000) * 10
        session.add(PersonioAttendance(
            id=att_base,
            employee_id=emp,
            date=date(2026, 4, 10),
            start_time=time(8, 0), end_time=time(9, 0),  # 1h
            break_minutes=60,                              # -1h → worked=0 (skipped)
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            res = await client.get(
                OVERTIME_URL,
                params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            rows = res.json()
            assert not [r for r in rows if r["employee_id"] == emp], rows
        finally:
            await _cleanup_employees(session, [emp])


# -------------------------------------------------------------------------
# 422 cases: missing dates (FastAPI Query(...) native) + inverted range
# -------------------------------------------------------------------------


async def test_overtime_missing_date_from_returns_422(client):
    res = await client.get(
        OVERTIME_URL,
        params={"date_to": "2026-04-30"},
        headers=_auth_headers(),
    )
    assert res.status_code == 422, res.text


async def test_overtime_missing_date_to_returns_422(client):
    res = await client.get(
        OVERTIME_URL,
        params={"date_from": "2026-04-01"},
        headers=_auth_headers(),
    )
    assert res.status_code == 422, res.text


async def test_overtime_inverted_range_returns_422(client):
    res = await client.get(
        OVERTIME_URL,
        params={"date_from": "2026-04-30", "date_to": "2026-04-01"},
        headers=_auth_headers(),
    )
    assert res.status_code == 422, res.text
    body = res.json()
    assert body.get("detail") == "date_from must be <= date_to", body
