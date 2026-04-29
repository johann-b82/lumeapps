"""Phase 60 Plan 04 Task 1 — pytest coverage for HR date-range endpoints.

Covers the 11 required behaviours (see 60-04-PLAN.md Task 1 <behavior>):

  1.  /api/hr/kpis custom range — whole-range overtime aggregation (D-01).
  2.  /api/hr/kpis custom range — previous_period is prior same-length window (D-02).
  3.  /api/hr/kpis — fluctuation denominator is avg active headcount across range
      with an explicit 104/45 numeric expectation (D-03).
  4.  /api/hr/kpis omitted params — current-month fallback (legacy parity).
  5.  /api/hr/kpis/history 15-day range — 15 daily buckets (D-06).
  6.  /api/hr/kpis/history 60-day range — weekly buckets labelled YYYY-Www (D-06).
  7.  /api/hr/kpis/history no params — 12 monthly buckets (D-07 thisYear parity).
  8.  /api/hr/kpis/history 1000-day range — quarterly buckets labelled YYYY-Qn.
  9.  (Removed in Phase 67 — overtime compute moved to its own endpoint;
       coverage lives in tests/test_hr_overtime_endpoint.py.)
  10. Invalid ranges (half-provided, inverted) return HTTP 400 on the two HR KPI endpoints.
  11. /api/hr/kpis — sick_leave_ratio is a whole-range ratio, NOT an average of
      per-month ratios (D-05 mirror of overtime).

Tests seed into far-future 2099+ windows where possible so the shared dev
database's real 2026 data cannot contaminate bounded assertions. Employee
fluctuation/sick-leave tests that need day-weighted denominators use the
specific dates from the plan (2026-03-01..2026-04-14) and assert against
the service functions directly rather than absolute counts — this keeps
assertions valid regardless of baseline rows in the shared db.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models import (
    AppSettings,
    PersonioAbsence,
    PersonioAttendance,
    PersonioEmployee,
    SalesRecord,
    UploadBatch,
)
from app.services.hr_kpi_aggregation import (
    _overtime_ratio,
    _sick_leave_ratio,
    compute_hr_kpis,
    prior_window_same_length,
)
from tests.test_directus_auth import _mint, ADMIN_UUID

pytestmark = pytest.mark.asyncio


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_mint(ADMIN_UUID)}"}


# ---------------------------------------------------------------------------
# Seed + cleanup helpers
# ---------------------------------------------------------------------------


def _emp_id(prefix: str, idx: int) -> int:
    """Derive a deterministic integer id for a test employee.

    Uses a large offset (9_500_000 + prefix hash) to avoid colliding with
    real Personio ids in the shared dev DB.
    """
    # Stable-ish seed; the prefix is already scoped per-test.
    base = 9_500_000 + (abs(hash(prefix)) % 100_000) * 10
    return base + idx


async def _cleanup_employees(session, employee_ids: list[int]) -> None:
    if not employee_ids:
        return
    await session.execute(
        delete(PersonioAttendance).where(PersonioAttendance.employee_id.in_(employee_ids))
    )
    await session.execute(
        delete(PersonioAbsence).where(PersonioAbsence.employee_id.in_(employee_ids))
    )
    await session.execute(
        delete(PersonioEmployee).where(PersonioEmployee.id.in_(employee_ids))
    )
    await session.commit()


# ---------------------------------------------------------------------------
# 1. Custom range — overtime_ratio is whole-range aggregation (D-01)
# ---------------------------------------------------------------------------


async def test_hr_kpis_custom_range_single_window(client):
    """D-01: /api/hr/kpis?date_from=2026-03-01&date_to=2026-04-14 returns
    overtime_ratio.value equal to _overtime_ratio(db, first, last) — i.e. the
    single-window whole-range aggregation, not an average of monthly ratios.
    """
    first = date(2026, 3, 1)
    last = date(2026, 4, 14)
    prefix = "hr-range-otcurr"
    emp_a = _emp_id(prefix, 0)
    emp_b = _emp_id(prefix, 1)

    async with AsyncSessionLocal() as session:
        session.add(PersonioEmployee(
            id=emp_a,
            first_name="OT", last_name="Alpha",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        session.add(PersonioEmployee(
            id=emp_b,
            first_name="OT", last_name="Beta",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        # 2 attendance rows: one in March, one in April — both with 10h worked
        # (2h overtime each on a 40h week = 8h daily quota)
        att_id_base = 9_800_000 + (abs(hash(prefix)) % 10_000) * 10
        session.add(PersonioAttendance(
            id=att_id_base,
            employee_id=emp_a,
            date=date(2026, 3, 10),
            start_time=time(8, 0), end_time=time(18, 0),
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        session.add(PersonioAttendance(
            id=att_id_base + 1,
            employee_id=emp_b,
            date=date(2026, 4, 5),
            start_time=time(8, 0), end_time=time(18, 0),
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            direct = await _overtime_ratio(session, first, last)

            res = await client.get(
                "/api/hr/kpis",
                params={"date_from": first.isoformat(), "date_to": last.isoformat()},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["overtime_ratio"]["value"] == pytest.approx(direct, rel=1e-6)
        finally:
            await _cleanup_employees(session, [emp_a, emp_b])


# ---------------------------------------------------------------------------
# 2. previous_period is prior same-length window (D-02)
# ---------------------------------------------------------------------------


async def test_hr_kpis_prior_window_same_length(client):
    """D-02: previous_period equals _overtime_ratio over the prior 45-day window
    ending the day before date_from. For a 45-day request
    2026-03-01..2026-04-14, prior window is 2026-01-15..2026-02-28.
    """
    first = date(2026, 3, 1)
    last = date(2026, 4, 14)
    prev_first, prev_last = prior_window_same_length(first, last)
    assert (prev_first, prev_last) == (date(2026, 1, 15), date(2026, 2, 28))

    prefix = "hr-range-otprev"
    emp = _emp_id(prefix, 0)
    async with AsyncSessionLocal() as session:
        session.add(PersonioEmployee(
            id=emp,
            first_name="OT", last_name="Prev",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        # Row inside prior window (Feb) with 9h worked — 1h overtime
        att_base = 9_810_000 + (abs(hash(prefix)) % 10_000) * 10
        session.add(PersonioAttendance(
            id=att_base,
            employee_id=emp,
            date=date(2026, 2, 10),
            start_time=time(8, 0), end_time=time(17, 0),
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        # Row inside current window — different ratio so we can distinguish
        session.add(PersonioAttendance(
            id=att_base + 1,
            employee_id=emp,
            date=date(2026, 3, 10),
            start_time=time(8, 0), end_time=time(20, 0),
            break_minutes=0,
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            direct_prev = await _overtime_ratio(session, prev_first, prev_last)

            res = await client.get(
                "/api/hr/kpis",
                params={"date_from": first.isoformat(), "date_to": last.isoformat()},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["overtime_ratio"]["previous_period"] == pytest.approx(
                direct_prev, rel=1e-6
            )
        finally:
            await _cleanup_employees(session, [emp])


# ---------------------------------------------------------------------------
# 3. Fluctuation denominator = avg active headcount across range (D-03)
# ---------------------------------------------------------------------------


async def test_hr_kpis_fluctuation_avg_headcount_denominator(client):
    """D-03: exactly 3 employees; 1 leaves mid-range; avg-active-headcount math:

        A: hire 2025-01-01, term None             -> active all 45 days
        B: hire 2025-06-01, term None             -> active all 45 days
        C: hire 2025-03-01, term 2026-03-15       -> active days 2026-03-01..2026-03-14
           (14 days) — termination_date > d rule: active when termination_date > d.

        avg_active_headcount = (3 * 14 + 2 * 31) / 45 = 104 / 45
        leavers_in_range = 1 (C)
        fluctuation = 1 / (104 / 45) = 45/104

    This assertion would fail if the denominator reverted to end-of-month snapshot
    (which would be 2 at 2026-04-14).

    Uses test-scoped employees; wipes other employees that would otherwise be
    counted in the denominator by isolating with a far-future range first to
    confirm the test's shape is valid, then scoping to the plan dates.
    """
    first = date(2026, 3, 1)
    last = date(2026, 4, 14)  # 45 days inclusive
    prefix = "hr-fluct-d03"
    emp_a = _emp_id(prefix, 0)
    emp_b = _emp_id(prefix, 1)
    emp_c = _emp_id(prefix, 2)

    # Temporarily quarantine all OTHER employees out of the window by saving +
    # restoring their hire/termination dates. This guarantees our 3 rows are
    # the only contributors to avg_active_headcount across [first, last].
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, update

        other_ids_rows = (
            await session.execute(
                select(PersonioEmployee.id).where(
                    ~PersonioEmployee.id.in_([emp_a, emp_b, emp_c])
                )
            )
        ).all()
        other_ids = [r.id for r in other_ids_rows]

        # Snapshot their current hire/termination so we can restore in finally.
        snapshots: list[tuple[int, date | None, date | None]] = []
        if other_ids:
            snap_rows = (
                await session.execute(
                    select(
                        PersonioEmployee.id,
                        PersonioEmployee.hire_date,
                        PersonioEmployee.termination_date,
                    ).where(PersonioEmployee.id.in_(other_ids))
                )
            ).all()
            snapshots = [(r.id, r.hire_date, r.termination_date) for r in snap_rows]
            # Push them out of the window: hire_date after last.
            await session.execute(
                update(PersonioEmployee)
                .where(PersonioEmployee.id.in_(other_ids))
                .values(hire_date=date(2099, 1, 1), termination_date=None)
            )
            await session.commit()

        try:
            session.add(PersonioEmployee(
                id=emp_a,
                first_name="Fluct", last_name="A",
                status="active",
                hire_date=date(2025, 1, 1),
                termination_date=None,
                weekly_working_hours=Decimal("40.00"),
                synced_at=datetime.now(timezone.utc),
            ))
            session.add(PersonioEmployee(
                id=emp_b,
                first_name="Fluct", last_name="B",
                status="active",
                hire_date=date(2025, 6, 1),
                termination_date=None,
                weekly_working_hours=Decimal("40.00"),
                synced_at=datetime.now(timezone.utc),
            ))
            session.add(PersonioEmployee(
                id=emp_c,
                first_name="Fluct", last_name="C",
                status="inactive",
                hire_date=date(2025, 3, 1),
                termination_date=date(2026, 3, 15),
                weekly_working_hours=Decimal("40.00"),
                synced_at=datetime.now(timezone.utc),
            ))
            await session.commit()

            res = await client.get(
                "/api/hr/kpis",
                params={"date_from": first.isoformat(), "date_to": last.isoformat()},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            body = res.json()

            # Explicit numeric expectation (D-03)
            expected = 45 / 104  # 1 leaver / (104/45 avg-active) = 45/104
            assert body["fluctuation"]["value"] == pytest.approx(expected, rel=1e-6)
        finally:
            await _cleanup_employees(session, [emp_a, emp_b, emp_c])
            # Restore everyone else
            if snapshots:
                for other_id, hire, term in snapshots:
                    await session.execute(
                        update(PersonioEmployee)
                        .where(PersonioEmployee.id == other_id)
                        .values(hire_date=hire, termination_date=term)
                    )
                await session.commit()


# ---------------------------------------------------------------------------
# 4. Omitted params falls back to current-month (legacy)
# ---------------------------------------------------------------------------


async def test_hr_kpis_omitted_params_fallback_is_current_month(client, monkeypatch):
    """No date_from/date_to => endpoint uses _month_bounds(today.year, today.month).

    We monkeypatch `date.today` inside the router module to a fixed day so the
    assertion is deterministic. Response equals compute_hr_kpis(db, first, last)
    for that month.
    """
    import app.routers.hr_kpis as hr_kpis_mod

    class _FrozenDate(date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return date(2026, 4, 15)

    monkeypatch.setattr(hr_kpis_mod, "date", _FrozenDate)

    res = await client.get("/api/hr/kpis", headers=_auth_headers())
    assert res.status_code == 200, res.text
    body = res.json()

    async with AsyncSessionLocal() as session:
        expected = await compute_hr_kpis(session, date(2026, 4, 1), date(2026, 4, 30))

    # overtime_ratio is structurally always present; compare value fields only.
    assert body["overtime_ratio"]["value"] == (
        pytest.approx(expected.overtime_ratio.value, rel=1e-6)
        if expected.overtime_ratio.value is not None
        else None
    )
    assert body["fluctuation"]["value"] == (
        pytest.approx(expected.fluctuation.value, rel=1e-6)
        if expected.fluctuation.value is not None
        else None
    )


# ---------------------------------------------------------------------------
# 5. /kpis/history 15-day range -> 15 daily buckets
# ---------------------------------------------------------------------------


async def test_hr_kpis_history_daily_buckets(client):
    res = await client.get(
        "/api/hr/kpis/history",
        params={"date_from": "2026-04-01", "date_to": "2026-04-15"},
        headers=_auth_headers(),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) == 15
    for point in body:
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", point["month"]), point["month"]


# ---------------------------------------------------------------------------
# 6. /kpis/history 60-day range -> weekly buckets
# ---------------------------------------------------------------------------


async def test_hr_kpis_history_weekly_buckets(client):
    res = await client.get(
        "/api/hr/kpis/history",
        params={"date_from": "2026-03-01", "date_to": "2026-04-29"},
        headers=_auth_headers(),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert 9 <= len(body) <= 10, len(body)
    for point in body:
        assert re.match(r"^\d{4}-W\d{2}$", point["month"]), point["month"]


# ---------------------------------------------------------------------------
# 7. /kpis/history no params -> 12 monthly buckets (thisYear parity, D-07)
# ---------------------------------------------------------------------------


async def test_hr_kpis_history_monthly_buckets_default(client):
    res = await client.get("/api/hr/kpis/history", headers=_auth_headers())
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) == 12
    for point in body:
        assert re.match(r"^\d{4}-\d{2}$", point["month"]), point["month"]


# ---------------------------------------------------------------------------
# 8. /kpis/history 1000-day range -> quarterly buckets
# ---------------------------------------------------------------------------


async def test_hr_kpis_history_quarterly_buckets(client):
    # 1000 days from 2024-01-01 -> ~2026-09-26
    res = await client.get(
        "/api/hr/kpis/history",
        params={"date_from": "2024-01-01", "date_to": "2026-09-26"},
        headers=_auth_headers(),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    for point in body:
        assert re.match(r"^\d{4}-Q[1-4]$", point["month"]), point["month"]


# ---------------------------------------------------------------------------
# 9. Invalid ranges return 400 on the two HR KPI endpoints
# (Phase 67: legacy employees endpoint deleted; overtime endpoint 422 cases
# live in tests/test_hr_overtime_endpoint.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/api/hr/kpis",
        "/api/hr/kpis/history",
    ],
)
async def test_invalid_range_returns_400(client, url):
    """Half-provided and inverted ranges both return HTTP 400."""
    # Half-provided
    r1 = await client.get(url, params={"date_from": "2026-04-01"}, headers=_auth_headers())
    assert r1.status_code == 400, (url, r1.text)
    r2 = await client.get(url, params={"date_to": "2026-04-30"}, headers=_auth_headers())
    assert r2.status_code == 400, (url, r2.text)
    # Inverted
    r3 = await client.get(
        url,
        params={"date_from": "2026-04-30", "date_to": "2026-04-01"},
        headers=_auth_headers(),
    )
    assert r3.status_code == 400, (url, r3.text)


# ---------------------------------------------------------------------------
# 11. D-05 sick-leave whole-range ratio (mirror of D-01 overtime)
# ---------------------------------------------------------------------------


async def test_hr_kpis_sick_leave_whole_range(client):
    """D-05: sick_leave_ratio equals _sick_leave_ratio(db, first, last, ids)
    across the whole 45-day window — NOT the unweighted average of per-month
    ratios.

    Seed a case where the per-month average would differ from the day-weighted
    whole-range ratio: 1 sick-leave day in a short month stretch vs. many
    working days in April. If the backend averaged monthly ratios, the value
    would be larger than the whole-range ratio.
    """
    first = date(2026, 3, 1)
    last = date(2026, 4, 14)
    prefix = "hr-sickleave-d05"
    emp = _emp_id(prefix, 0)

    # Configure a sick_leave_type_id in settings
    sick_type_id = 98765
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, update

        # Save + override app settings
        row = (await session.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
        original_sick = row.personio_sick_leave_type_id
        await session.execute(
            update(AppSettings)
            .where(AppSettings.id == 1)
            .values(personio_sick_leave_type_id=[sick_type_id])
        )
        await session.commit()

        session.add(PersonioEmployee(
            id=emp,
            first_name="Sick", last_name="Leave",
            status="active",
            hire_date=date(2025, 1, 1),
            termination_date=None,
            weekly_working_hours=Decimal("40.00"),
            synced_at=datetime.now(timezone.utc),
        ))
        # 1 sick-leave absence spanning March 10 (single day)
        abs_id = f"abs-{prefix}-1"
        session.add(PersonioAbsence(
            id=abs_id,
            employee_id=emp,
            absence_type_id=sick_type_id,
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 10),
            time_unit="days",
            hours=None,
            synced_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        try:
            direct = await _sick_leave_ratio(session, first, last, [sick_type_id])

            res = await client.get(
                "/api/hr/kpis",
                params={"date_from": first.isoformat(), "date_to": last.isoformat()},
                headers=_auth_headers(),
            )
            assert res.status_code == 200, res.text
            body = res.json()
            value = body["sick_leave_ratio"]["value"]
            if direct is None:
                assert value is None
            else:
                assert value == pytest.approx(direct, rel=1e-6)

            # Show that averaging per-month would differ: March and April
            # have different working-day counts, so avg(march_ratio, april_ratio)
            # != whole-range ratio.
            r_march = await _sick_leave_ratio(session, date(2026, 3, 1), date(2026, 3, 31), [sick_type_id])
            r_april = await _sick_leave_ratio(session, date(2026, 4, 1), date(2026, 4, 14), [sick_type_id])
            if r_march is not None and r_april is not None and direct is not None:
                unweighted_avg = (r_march + r_april) / 2
                # The backend must match the whole-range value, not the avg.
                # (If this ever coincides numerically, the test still passes
                # because the direct whole-range ratio is what's asserted.)
                assert value == pytest.approx(direct, rel=1e-6)
                # Sanity: avg_ratio diverges from direct in this seed
                assert unweighted_avg != pytest.approx(direct, rel=1e-6)
        finally:
            await session.execute(
                delete(PersonioAbsence).where(PersonioAbsence.id == abs_id)
            )
            await session.execute(
                delete(PersonioEmployee).where(PersonioEmployee.id == emp)
            )
            await session.execute(
                update(AppSettings)
                .where(AppSettings.id == 1)
                .values(personio_sick_leave_type_id=original_sick)
            )
            await session.commit()
