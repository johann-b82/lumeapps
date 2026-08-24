"""Personio sync orchestrator — fetches data from Personio API and upserts into PostgreSQL.

Decisions:
  D-01: Manual sync is blocking — run_sync() awaits all fetches and upserts.
  D-03: Upsert by Personio ID via INSERT ... ON CONFLICT DO UPDATE.
  D-04: Sync results persisted to personio_sync_meta singleton.
"""
import logging
from datetime import date as date_type, datetime, time as time_type, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AppSettings,
    PersonioAbsence,
    PersonioAttendance,
    PersonioEmployee,
    PersonioSyncMeta,
)
from app.schemas import SyncResult
from app.security.fernet import decrypt_credential
from app.services.personio_client import PersonioAPIError, PersonioClient

log = logging.getLogger(__name__)


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
    # Nicht-fataler Teilausfall (z. B. Personio-V1-Attendances-Deprecation): der
    # Mitarbeiter-Abgleich gilt trotzdem als geglückt, damit Stamm-/Org-Daten
    # (Abteilungen, Vorgesetzte, Ein-/Austritte) aktuell werden.
    teil_fehler: str | None = None

    try:
        # 1) Mitarbeiter — Pflichtteil. Sofort upserten (und committen), damit
        # Org-/Stammdaten selbst dann aktuell werden, wenn Anwesenheiten scheitern.
        raw_employees = await client.fetch_employees()
        employees = [_normalize_employee(r) for r in raw_employees]
        emp_count = await _upsert(session, PersonioEmployee, employees)

        # 2) Anwesenheiten — optional, über **Personio API V2**
        # (/v2/attendance-periods, v1.111). V1 (/company/attendances) war für
        # mehrtägige Perioden abgekündigt und lieferte 422 → der Sync blieb seit
        # 2026-07-08 stehen. V2 nutzt denselben Token, liefert die volle Historie
        # und je Segment einen Datensatz (WORK/BREAK); nur WORK zählt als
        # Arbeitszeit (Pausen sind eigene Segmente).
        try:
            # Fenster begrenzen (weniger Requests/Rate-Limit); deckt alle
            # report-relevanten Wochen ab. Volle Historie ist über V2 möglich,
            # aber unnötig teuer.
            att_since = date_type.today() - timedelta(days=400)
            raw_attendances = await client.fetch_attendance_periods_v2(since=att_since)
            attendances = [
                _normalize_attendance_v2(r)
                for r in raw_attendances
                if r.get("type") == "WORK"
            ]
            att_count = await _upsert(session, PersonioAttendance, attendances)
        except PersonioAPIError as exc:
            teil_fehler = f"Anwesenheiten: {exc}"
            log.warning("Anwesenheits-Sync fehlgeschlagen (nicht fatal): %s", exc)

        # 3) Abwesenheiten — optional. Zwei Quellen mit disjunkten Typen:
        #    /company/absence-periods liefert für unsere Zugangsdaten nur
        #    „Freizeitausgleich" (stundenbasiert); /company/time-offs liefert
        #    Urlaub, Krankheit, Kinderkrank … (tagesbasiert). Zusammengeführt.
        daily_hours = {
            e["id"]: (float(e["weekly_working_hours"]) / 5.0 if e.get("weekly_working_hours") else 8.0)
            for e in employees
            if e.get("id")
        }
        absences: list[dict] = []
        beide_ok = True
        try:
            absences += [_normalize_absence(r) for r in await client.fetch_absences()]
        except PersonioAPIError as exc:
            beide_ok = False
            teil_fehler = teil_fehler or f"Abwesenheiten (absence-periods): {exc}"
            log.warning("absence-periods-Sync fehlgeschlagen (nicht fatal): %s", exc)
        try:
            absences += [
                _normalize_timeoff(r, daily_hours) for r in await client.fetch_time_offs()
            ]
        except PersonioAPIError as exc:
            beide_ok = False
            teil_fehler = teil_fehler or f"Abwesenheiten (time-offs): {exc}"
            log.warning("time-offs-Sync fehlgeschlagen (nicht fatal): %s", exc)
        if absences:
            abs_count = await _upsert(session, PersonioAbsence, absences)
        # Verwaiste (in Personio gelöschte) Abwesenheiten entfernen — nur wenn
        # beide Endpoints erfolgreich waren (sonst volle ID-Menge unbekannt).
        if beide_ok:
            entfernt = await _prune_absences(session, {a["id"] for a in absences})
            if entfernt:
                log.info("Verwaiste Abwesenheiten entfernt: %s", entfernt)

        await _update_sync_meta(
            session,
            emp_count,
            att_count,
            abs_count,
            "ok" if teil_fehler is None else "partial",
            teil_fehler,
        )

        # Nach dem Abgleich: für neue Eintritte die Schulungsübersicht anlegen
        # bzw. auffrischen. Bewusst NACH _update_sync_meta und in eigenem
        # try/except — der Personio-Abgleich selbst gilt als geglückt, auch
        # wenn LibreOffice oder Directus gerade nicht mitspielen.
        try:
            from app.services.onboarding_dokumente import uebersichten_erzeugen

            lauf = await uebersichten_erzeugen(session)
            if lauf.erzeugt or lauf.aktualisiert:
                log.info(
                    "Schulungsübersichten: %s erzeugt, %s aktualisiert",
                    lauf.erzeugt,
                    lauf.aktualisiert,
                )
        except Exception as exc:  # noqa: BLE001 - darf den Sync nicht kippen
            log.warning("Schulungsübersichten fehlgeschlagen: %s", exc)

    except PersonioAPIError as exc:
        await _update_sync_meta(session, emp_count, att_count, abs_count, "error", str(exc))
        raise

    finally:
        await client.close()

    return SyncResult(
        employees_synced=emp_count,
        attendance_synced=att_count,
        absences_synced=abs_count,
        status="ok" if teil_fehler is None else "partial",
        error_message=teil_fehler,
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


def _v2_zeit(dt: str | None):
    """Zeitanteil aus einem V2-Zeitstempel (``2026-01-26T08:50:00``)."""
    if not dt or "T" not in dt:
        return _parse_time(dt)
    return _parse_time(dt.split("T", 1)[1])


def _normalize_attendance_v2(raw: dict) -> dict:
    """Flache Felder aus einem V2-``/v2/attendance-periods``-Segment.

    Struktur: ``{id: <uuid>, person: {id}, type: "WORK", start: {date_time},
    end: {date_time}, attribution_date}``. Pausen sind eigene ``BREAK``-Segmente
    (vom Aufrufer herausgefiltert) → ``break_minutes`` bleibt 0.
    """
    person = (raw.get("person") or {}).get("id")
    return {
        "id": str(raw.get("id")),
        "employee_id": int(person) if person else None,
        "date": _parse_date(raw.get("attribution_date")),
        "start_time": _v2_zeit((raw.get("start") or {}).get("date_time")),
        "end_time": _v2_zeit((raw.get("end") or {}).get("date_time")),
        "break_minutes": 0,
        "is_holiday": False,
        "synced_at": datetime.now(timezone.utc),
        "raw_json": raw,
    }


def _absence_stunden(attrs: dict) -> float | None:
    """Dauer einer Abwesenheit in **Stunden**.

    Personio liefert ``effective_duration`` bei stundenbasierten Abwesenheiten
    in **Minuten** (300 = 5 h), nicht in Stunden — daher ``/ 60``. Ohne diese
    Umrechnung landeten Minuten als Stunden in der DB (Faktor 60 zu groß).

    Tagesbasierte Abwesenheiten (``measurement_unit == "day"``) behalten vorerst
    ihren Rohwert; ihre saubere Umrechnung in Stunden braucht die Tages-
    arbeitszeit der Person und folgt, sobald tagesbasierte Daten (z. B.
    Krankheit) überhaupt synchronisiert werden.
    """
    dur = attrs.get("effective_duration")
    if dur is None:
        dur = _attr_val(attrs, "hours")
    if dur is None:
        return None
    unit = (attrs.get("measurement_unit") or _attr_val(attrs, "time_unit") or "").lower()
    if unit == "hour":
        return round(dur / 60.0, 2)
    return dur


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
        "hours": _absence_stunden(attrs),
        "synced_at": datetime.now(timezone.utc),
        "raw_json": raw,
    }


def _normalize_timeoff(raw: dict, daily_hours: dict[int, float]) -> dict:
    """Flache Felder aus einem ``/company/time-offs``-Eintrag (tagesbasiert).

    Struktur weicht von ``/absence-periods`` ab: ``id`` ist ein Integer, die
    Dauer steht als ``days_count`` (Personio zählt bereits Arbeitstage, inkl.
    halber Tage als 0.5). Für die Std.-Auswertung: ``days_count × Tagesarbeitszeit``
    der Person (``daily_hours``). Employee-/Typ-ID stecken verschachtelt.
    """
    attrs = raw.get("attributes", raw)
    to_id = str(attrs.get("id") or raw.get("id"))

    emp = attrs.get("employee") or {}
    emp_attrs = emp.get("attributes", {}) if isinstance(emp, dict) else {}
    emp_id_field = emp_attrs.get("id")
    employee_id = emp_id_field.get("value") if isinstance(emp_id_field, dict) else emp_id_field

    tt = attrs.get("time_off_type") or {}
    tt_attrs = tt.get("attributes", {}) if isinstance(tt, dict) else {}
    type_id = tt_attrs.get("id")
    if not isinstance(type_id, int):
        type_id = None

    tage = float(attrs.get("days_count") or 0)
    stunden = round(tage * daily_hours.get(employee_id, 8.0), 2)
    return {
        "id": to_id,
        "employee_id": employee_id,
        "absence_type_id": type_id,
        "start_date": _parse_date(attrs.get("start_date")),
        # Offene (laufende) Abwesenheiten haben kein end_date → auf start_date
        # setzen (Spalte ist NOT NULL; days_count/Stunden bleiben Personios Wert).
        "end_date": _parse_date(attrs.get("end_date")) or _parse_date(attrs.get("start_date")),
        "time_unit": "day",
        "hours": stunden,
        "synced_at": datetime.now(timezone.utc),
        "raw_json": raw,
    }


async def _prune_absences(session: AsyncSession, keep_ids: set[str]) -> int:
    """Abwesenheiten löschen, die Personio nicht mehr liefert (in P. gelöscht).

    Nur aufrufen, wenn ALLE Abwesenheits-Endpoints erfolgreich waren — sonst
    würde ein Teilausfall gültige Zeilen des anderen Endpoints entfernen.
    """
    from sqlalchemy import delete, select

    vorhanden = (await session.execute(select(PersonioAbsence.id))).scalars().all()
    weg = [i for i in vorhanden if i not in keep_ids]
    if weg:
        await session.execute(delete(PersonioAbsence).where(PersonioAbsence.id.in_(weg)))
        await session.commit()
    return len(weg)


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


async def _get_settings(session: AsyncSession) -> AppSettings:
    """Fetch the AppSettings singleton row (id=1)."""
    result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
    return result.scalar_one()


# v1.41 introduced rebuild_canonical_sales_aliases as a post-sync hook.
# v1.42 removed the alias table entirely — sales reps are identified by
# the Wer token from the Kontakte file directly — so the hook has been
# deleted along with its call site in run_sync().
