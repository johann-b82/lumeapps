"""Phase 67 MIG-DATA-03: per-employee overtime compute endpoint.

Lifted verbatim from the now-deleted data.py `list_employees` overtime
block (lines 89-125). Row-data for employees is served by Directus
`readItems('personio_employees')` — this endpoint only computes the
total-hours / overtime-hours / overtime-ratio roll-up per employee
over a required [date_from, date_to] window.

Response: flat array — only employees WITH attendance in the window
appear (D-04). Frontend zero-fills missing entries (D-05).

Compute-justified: clause 3 (overtime compute across overlapping intervals).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import get_current_user
from app.models import PersonioAttendance, PersonioEmployee

router = APIRouter(
    prefix="/api/data",
    tags=["data"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/employees/overtime")
async def get_employees_overtime(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[dict]:
    # Per CONTEXT D-07: inverted range → 422 (not 400 as data.py did).
    if date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be <= date_to",
        )

    att_stmt = (
        select(
            PersonioAttendance.employee_id,
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
            PersonioAttendance.date >= date_from,
            PersonioAttendance.date <= date_to,
        )
    )
    att_rows = (await db.execute(att_stmt)).all()

    overtime_map: dict[int, float] = {}
    total_map: dict[int, float] = {}
    for row in att_rows:
        if row.start_time is None or row.end_time is None:
            continue
        start_min = row.start_time.hour * 60 + row.start_time.minute
        end_min = row.end_time.hour * 60 + row.end_time.minute
        worked = (end_min - start_min - (row.break_minutes or 0)) / 60.0
        if worked <= 0:
            continue
        total_map[row.employee_id] = (
            total_map.get(row.employee_id, 0.0) + worked
        )
        daily_quota = (
            float(row.weekly_working_hours) / 5.0
            if row.weekly_working_hours
            else 8.0
        )
        ot = max(0.0, worked - daily_quota)
        overtime_map[row.employee_id] = (
            overtime_map.get(row.employee_id, 0.0) + ot
        )

    result: list[dict] = []
    for emp_id in total_map:
        total = total_map[emp_id]
        ot = overtime_map.get(emp_id, 0.0)
        result.append({
            "employee_id": emp_id,
            "total_hours": round(total, 1),
            "overtime_hours": round(ot, 1),
            "overtime_ratio": (
                round(ot / total, 4)
                if total > 0 and ot > 0
                else None
            ),
        })
    return result
