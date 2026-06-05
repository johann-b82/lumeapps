"""Public birthday + profile-picture endpoints for the digital-signage embed.

Mirror of the routes in hr_kpis.py BUT WITHOUT the directus_auth dep — these
are intended to be iframed from kiosks that don't carry a Directus session
cookie. Risk acknowledged in PR description: the data (employee names,
departments, photos) is exposed to anyone who can reach the dashboard host
on the corporate LAN. Acceptable for an internal office-display use case;
swap to a long-lived signed embed token if the dashboard ever leaves the
LAN. The auth'd duplicates in hr_kpis.py keep their role gates intact —
admin-only HR navigation still goes through those.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AppSettings, PersonioEmployee
from app.security.fernet import decrypt_credential
from app.services.personio_client import PersonioAPIError, PersonioClient
from app.routers.hr_kpis import (
    BirthdayEntry,
    _anniversary_in_year,
    _find_birthday_in_raw,
    _has_profile_picture,
    _parse_birthday,
)


router = APIRouter(prefix="/api/hr/embed", tags=["hr-embed"])


@router.get("/birthdays/this-week", response_model=list[BirthdayEntry])
async def embed_birthdays_this_week(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[BirthdayEntry]:
    """Same shape as /api/hr/birthdays/this-week — no auth, no Directus token.

    Duplicates the logic deliberately so the auth'd endpoint stays the
    canonical reference; if the resolver shape ever changes, both functions
    need to move together. Kept small enough that the duplication is cheap.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    candidate_years = {monday.year, sunday.year}

    rows = (
        await db.execute(
            sa_select(
                PersonioEmployee.id,
                PersonioEmployee.first_name,
                PersonioEmployee.last_name,
                PersonioEmployee.department,
                PersonioEmployee.termination_date,
                PersonioEmployee.raw_json,
            )
        )
    ).all()

    entries: list[BirthdayEntry] = []
    for r in rows:
        if r.termination_date is not None and r.termination_date <= today:
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
                break

    entries.sort(
        key=lambda e: (e.occurs_on, (e.last_name or "").lower(), (e.first_name or "").lower())
    )
    return entries


@router.get("/employees/{employee_id}/photo")
async def embed_employee_photo(
    employee_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Unauthenticated mirror of the photo proxy.

    Returns 404 when the row is missing, when Personio has no picture, or
    when credentials aren't configured — so a misconfigured stack just
    renders initials rather than failing the whole tile.
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
        headers={"Cache-Control": "public, max-age=3600"},
    )
