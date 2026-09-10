"""Public birthday + profile-picture endpoints for the digital-signage embed.

Mirror of the routes in hr_kpis.py BUT WITHOUT the directus_auth dep — these
are intended to be iframed from kiosks that don't carry a Directus session
cookie. The auth'd duplicates in hr_kpis.py keep their role gates intact —
admin-only HR navigation still goes through those.

Because the routes are session-less, they only ever carry what the kiosk
board actually paints (Befund 4 der Sicherheitsanalyse):

  * the payload is the *embed* shape, not the admin shape — no date of
    birth, no age. The board shows a name, a department and the day of the
    week; the birth year is neither drawn nor sent.
  * the photo proxy answers only for employees the board is currently
    showing (birthday this ISO week, or joined within the last 52 weeks),
    so the integer id can no longer be walked to page through the staff
    directory.
  * photo bytes are cached for an hour and rate-limited per IP, so the
    proxy can't be used to hammer Personio with our credentials.

The real fix — a signed embed token per playlist item — lives in the new
platform; changing the URL shape here would mean re-pasting every signage
playlist item on site.

Compute-justified: clause 1 (side effect outside Postgres) — proxies Personio
profile-picture bytes, computes ISO-week birthday/joiner windows, and serves
session-less kiosk embeds; none of which a Directus collection read can express.
"""

from datetime import date, timedelta
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AppSettings, PersonioEmployee
from app.security.fernet import decrypt_credential
from app.security.rate_limit import rate_limit_embed_photo
from app.services.personio_client import PersonioAPIError, PersonioClient
from app.routers.hr_kpis import (
    _anniversary_in_year,
    _find_birthday_in_raw,
    _has_profile_picture,
    _is_currently_active,
    _parse_birthday,
)
from fastapi import Query


router = APIRouter(prefix="/api/hr/embed", tags=["hr-embed"])

# Widest joiner window the route below accepts. Also bounds which employees
# the photo proxy will serve, so both stay in step.
_JOINER_MAX_WOCHEN = 52
_FOTO_TTL_S = 3600.0
_FOTO_CACHE_MAX = 200


class EmbedBirthdayEntry(BaseModel):
    """Birthday tile as the kiosk paints it — deliberately without the DOB."""

    employee_id: int
    first_name: str | None
    last_name: str | None
    department: str | None
    weekday: int            # 0 = Monday … 6 = Sunday — week-relative
    occurs_on: date         # this year's anniversary date (handles Feb 29)
    has_photo: bool


class EmbedJoinerEntry(BaseModel):
    """New-joiner tile as the kiosk paints it."""

    employee_id: int
    first_name: str | None
    last_name: str | None
    department: str | None
    hire_date: date
    days_with_company: int
    has_photo: bool


def _wochenfenster(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def _geburtstag_in_woche(raw_json, monday: date, sunday: date) -> date | None:
    """The anniversary date inside [monday, sunday], or None."""
    raw_val = _find_birthday_in_raw(raw_json)
    if not raw_val:
        return None
    dob = _parse_birthday(raw_val)
    if dob is None:
        return None
    for year in {monday.year, sunday.year}:
        occurs = _anniversary_in_year(dob, year)
        if monday <= occurs <= sunday:
            return occurs
    return None


@router.get("/birthdays/this-week", response_model=list[EmbedBirthdayEntry])
async def embed_birthdays_this_week(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[EmbedBirthdayEntry]:
    """Kiosk mirror of /api/hr/birthdays/this-week — no auth, no DOB, no age."""
    today = date.today()
    monday, sunday = _wochenfenster(today)

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

    entries: list[EmbedBirthdayEntry] = []
    for r in rows:
        if not _is_currently_active(r.status, r.termination_date, today):
            continue
        occurs = _geburtstag_in_woche(r.raw_json, monday, sunday)
        if occurs is None:
            continue
        entries.append(
            EmbedBirthdayEntry(
                employee_id=r.id,
                first_name=r.first_name,
                last_name=r.last_name,
                department=r.department,
                weekday=occurs.weekday(),
                occurs_on=occurs,
                has_photo=_has_profile_picture(r.raw_json),
            )
        )

    entries.sort(
        key=lambda e: (e.occurs_on, (e.last_name or "").lower(), (e.first_name or "").lower())
    )
    return entries


@router.get("/joiners/recent", response_model=list[EmbedJoinerEntry])
async def embed_joiners_recent(
    weeks: int = Query(2, ge=1, le=_JOINER_MAX_WOCHEN),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[EmbedJoinerEntry]:
    """Unauthenticated mirror of /api/hr/joiners/recent — same shape, no auth."""
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

    out: list[EmbedJoinerEntry] = []
    for r in rows:
        if not _is_currently_active(r.status, r.termination_date, today):
            continue
        if r.hire_date is None:
            continue
        if r.hire_date < earliest or r.hire_date > today:
            continue
        out.append(
            EmbedJoinerEntry(
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


async def _wird_gerade_gezeigt(db: AsyncSession, employee_id: int, today: date) -> bool:
    """True when this employee appears on one of the two boards right now.

    Everyone else is invisible to the session-less proxy — that is what stops
    the integer id from being a directory index.
    """
    row = (
        await db.execute(
            sa_select(
                PersonioEmployee.status,
                PersonioEmployee.hire_date,
                PersonioEmployee.termination_date,
                PersonioEmployee.raw_json,
            ).where(PersonioEmployee.id == employee_id)
        )
    ).first()
    if row is None:
        return False
    if not _is_currently_active(row.status, row.termination_date, today):
        return False
    monday, sunday = _wochenfenster(today)
    if _geburtstag_in_woche(row.raw_json, monday, sunday) is not None:
        return True
    if row.hire_date is None:
        return False
    return today - timedelta(weeks=_JOINER_MAX_WOCHEN) <= row.hire_date <= today


# employee_id -> (abgelegt_am monotonic, bytes, content-type)
_foto_cache: dict[int, tuple[float, bytes, str]] = {}


def _cache_lesen(employee_id: int) -> tuple[bytes, str] | None:
    eintrag = _foto_cache.get(employee_id)
    if eintrag is None:
        return None
    abgelegt, body, content_type = eintrag
    if time.monotonic() - abgelegt > _FOTO_TTL_S:
        _foto_cache.pop(employee_id, None)
        return None
    return body, content_type


def _cache_schreiben(employee_id: int, body: bytes, content_type: str) -> None:
    if len(_foto_cache) >= _FOTO_CACHE_MAX:
        aeltester = min(_foto_cache, key=lambda k: _foto_cache[k][0])
        _foto_cache.pop(aeltester, None)
    _foto_cache[employee_id] = (time.monotonic(), body, content_type)


def _reset_foto_cache_for_tests() -> None:
    _foto_cache.clear()


@router.get("/employees/{employee_id}/photo", dependencies=[Depends(rate_limit_embed_photo)])
async def embed_employee_photo(
    employee_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Unauthenticated mirror of the photo proxy, for shown employees only.

    Returns 404 when the employee isn't on a board right now, when Personio
    has no picture, or when credentials aren't configured — so a misconfigured
    stack just renders initials rather than failing the whole tile. The 404 is
    identical in all three cases on purpose: a distinguishable answer would
    turn the route back into a staff-directory probe.
    """
    today = date.today()
    if not await _wird_gerade_gezeigt(db, employee_id, today):
        raise HTTPException(status_code=404, detail="no profile picture")

    zwischengespeichert = _cache_lesen(employee_id)
    if zwischengespeichert is not None:
        body, content_type = zwischengespeichert
        return Response(
            content=body,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    settings_row = (
        await db.execute(sa_select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()
    if (
        settings_row is None
        or not settings_row.personio_client_id_enc
        or not settings_row.personio_client_secret_enc
    ):
        raise HTTPException(status_code=404, detail="no profile picture")

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
    _cache_schreiben(employee_id, body, content_type)
    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )
