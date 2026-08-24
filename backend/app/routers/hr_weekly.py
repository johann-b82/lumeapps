"""Weekly Report — Mehrarbeit/Überstunden + Krankheit je ISO-Woche (v1.111).

Vier Kennzahlen je Kalenderwoche, wie im Haufe-/Excel-Report:
  1. Saldo Mehrarbeit  — Σ(Ist − Soll) über die Belegschaft, Woche + Vorwoche.
  2. geleistete Überstd. — positive Mehrarbeit je Person (Top-Liste).
  3. Krankheit in Std.  — Summe Krank-Stunden, Woche + Vorwoche.
  4. Krankheit/Std.     — Krank-Stunden je Person (Top-Liste).

Admin-gated: die Kacheln zeigen personenbezogene Leistungs- und
**Gesundheitsdaten** (Krankheit).

Datenlage (Stand Bau): Anwesenheiten enden am V1-Sync-Bruch (2026-07-08) →
Mehrarbeit/Überstunden nur für Wochen mit Daten. Krankheit ist datenseitig noch
nicht freigegeben (nur „Freizeitausgleich" wird geliefert) → Krank-Kacheln
bleiben leer, bis Personio den Typ freigibt. ``meta`` meldet beides ehrlich.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import PersonioAbsence, PersonioAttendance, PersonioEmployee
from app.security.directus_auth import get_current_user, require_admin

router = APIRouter(
    prefix="/api/hr/weekly-report",
    tags=["weekly-report"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

#: Personio-Abwesenheitstypen der Kategorie ``sick_leave`` in diesem Account
#: (aus /company/time-off-types): Krankheit + Krankheit ohne Lohnfortzahlung.
#: Kinderkrank (child_care) zählt bewusst nicht als „Krankheit" des Mitarbeiters.
SICK_ABSENCE_TYPE_IDS = {568234, 3270500}

#: Länge der Top-Personen-Listen.
TOP_N = 5


def _name(e: PersonioEmployee) -> str:
    return f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}"


def _worked(start_time, end_time, break_minutes) -> float:
    if start_time is None or end_time is None:
        return 0.0
    s = start_time.hour * 60 + start_time.minute
    e = end_time.hour * 60 + end_time.minute
    w = (e - s - (break_minutes or 0)) / 60.0
    return w if w > 0 else 0.0


def _woche_grenzen(year: int, week: int) -> tuple[date, date]:
    montag = date.fromisocalendar(year, week, 1)
    return montag, montag + timedelta(days=6)


class Person(BaseModel):
    name: str
    stunden: float


class WochenKennzahl(BaseModel):
    aktuell: float | None
    vorwoche: float | None


class WeeklyMeta(BaseModel):
    hat_anwesenheit: bool
    hat_krankheitsdaten: bool
    anwesenheit_bis: date | None
    wochen_verfuegbar: list[str]
    letzte_woche: str | None


class WeeklyReport(BaseModel):
    kw_label: str
    kw_prev_label: str
    saldo_mehrarbeit: WochenKennzahl
    krankheit_std: WochenKennzahl
    ueberstunden_top: list[Person]
    krankheit_top: list[Person]
    meta: WeeklyMeta


async def _anwesenheit_woche(db: AsyncSession, montag: date, sonntag: date):
    """Ist-Stunden, Überstunden und Saldo je Mitarbeiter für eine Woche.

    Personio liefert je Tag oft **mehrere** Zeilen (Vor-/Nachmittag). Deshalb
    erst je (Mitarbeiter, Tag) summieren und dann gegen das **Tagessoll**
    rechnen — sonst würde das Soll pro Segment abgezogen (Faktor 2+).
    """
    rows = (
        await db.execute(
            select(
                PersonioAttendance.employee_id,
                PersonioAttendance.date,
                PersonioAttendance.start_time,
                PersonioAttendance.end_time,
                PersonioAttendance.break_minutes,
                PersonioEmployee.weekly_working_hours,
                PersonioEmployee.first_name,
                PersonioEmployee.last_name,
            )
            .join(PersonioEmployee, PersonioAttendance.employee_id == PersonioEmployee.id)
            .where(PersonioAttendance.date >= montag, PersonioAttendance.date <= sonntag)
        )
    ).all()

    tag: dict[tuple[int, date], float] = {}
    quota: dict[int, float] = {}
    name: dict[int, str] = {}
    for r in rows:
        w = _worked(r.start_time, r.end_time, r.break_minutes)
        tag[(r.employee_id, r.date)] = tag.get((r.employee_id, r.date), 0.0) + w
        quota[r.employee_id] = (
            float(r.weekly_working_hours) / 5.0 if r.weekly_working_hours else 8.0
        )
        name[r.employee_id] = (
            f"{r.first_name or ''} {r.last_name or ''}".strip() or f"#{r.employee_id}"
        )

    ist: dict[int, float] = {}
    ueber: dict[int, float] = {}
    netto: dict[int, float] = {}
    for (eid, _d), wtag in tag.items():
        if wtag <= 0:  # unvollständige Stempelung (kein Ende) → Tag nicht werten
            continue
        q = quota[eid]
        ist[eid] = ist.get(eid, 0.0) + wtag
        # Nur gearbeitete Tage zählen; ein Abwesenheitstag erzeugt keinen Minus-Saldo.
        netto[eid] = netto.get(eid, 0.0) + (wtag - q)
        ueber[eid] = ueber.get(eid, 0.0) + max(0.0, wtag - q)
    return ist, ueber, netto, name


async def _krankheit_woche(db: AsyncSession, montag: date, sonntag: date):
    """Krank-Stunden je Mitarbeiter für eine Woche (anteilig nach Überlapp-Tagen)."""
    rows = (
        await db.execute(
            select(PersonioAbsence, PersonioEmployee)
            .join(PersonioEmployee, PersonioAbsence.employee_id == PersonioEmployee.id)
            .where(
                PersonioAbsence.absence_type_id.in_(SICK_ABSENCE_TYPE_IDS),
                PersonioAbsence.start_date <= sonntag,
                PersonioAbsence.end_date >= montag,
            )
        )
    ).all()
    per_emp: dict[int, float] = {}
    name: dict[int, str] = {}
    for absence, emp in rows:
        if absence.hours is None or not absence.start_date or not absence.end_date:
            continue
        spanne = (absence.end_date - absence.start_date).days + 1
        pro_tag = float(absence.hours) / spanne if spanne > 0 else float(absence.hours)
        ueberlapp = (min(absence.end_date, sonntag) - max(absence.start_date, montag)).days + 1
        stunden = pro_tag * max(0, ueberlapp)
        per_emp[emp.id] = per_emp.get(emp.id, 0.0) + stunden
        name[emp.id] = _name(emp)
    return per_emp, name


@router.get("/meta", response_model=WeeklyMeta)
async def meta(db: AsyncSession = Depends(get_async_db_session)) -> WeeklyMeta:
    max_att = (await db.execute(select(PersonioAttendance.date).order_by(PersonioAttendance.date.desc()).limit(1))).scalar_one_or_none()
    wochen = (
        await db.execute(select(PersonioAttendance.date))
    ).scalars().all()
    kws = sorted({f"{d.isocalendar()[0]}-{d.isocalendar()[1]:02d}" for d in wochen}, reverse=True)
    hat_krank = (
        await db.execute(
            select(PersonioAbsence.id).where(
                PersonioAbsence.absence_type_id.in_(SICK_ABSENCE_TYPE_IDS)
            ).limit(1)
        )
    ).first() is not None
    return WeeklyMeta(
        hat_anwesenheit=bool(kws),
        hat_krankheitsdaten=hat_krank,
        anwesenheit_bis=max_att,
        wochen_verfuegbar=kws,
        letzte_woche=kws[0] if kws else None,
    )


@router.get("", response_model=WeeklyReport)
async def weekly_report(
    year: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=53),
    db: AsyncSession = Depends(get_async_db_session),
) -> WeeklyReport:
    try:
        montag, sonntag = _woche_grenzen(year, week)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Ungültige Kalenderwoche.") from exc
    p_montag = montag - timedelta(days=7)
    p_sonntag = sonntag - timedelta(days=7)

    ist, ueber, netto, name = await _anwesenheit_woche(db, montag, sonntag)
    _, _, netto_v, _ = await _anwesenheit_woche(db, p_montag, p_sonntag)
    krank, kname = await _krankheit_woche(db, montag, sonntag)
    krank_v, _ = await _krankheit_woche(db, p_montag, p_sonntag)

    def _saldo(netto_map):
        if not netto_map:
            return None
        return round(sum(netto_map.values()), 2)

    ueber_top = sorted(
        ({"name": name[e], "stunden": round(h, 2)} for e, h in ueber.items() if h > 0.01),
        key=lambda x: x["stunden"],
        reverse=True,
    )[:TOP_N]
    krank_top = sorted(
        ({"name": kname[e], "stunden": round(h, 2)} for e, h in krank.items() if h > 0.01),
        key=lambda x: x["stunden"],
        reverse=True,
    )[:TOP_N]

    meta_obj = await meta(db)
    return WeeklyReport(
        kw_label=f"KW {week}",
        kw_prev_label=f"KW {p_montag.isocalendar()[1]}",
        saldo_mehrarbeit=WochenKennzahl(aktuell=_saldo(netto), vorwoche=_saldo(netto_v)),
        krankheit_std=WochenKennzahl(
            aktuell=round(sum(krank.values()), 2) if krank else None,
            vorwoche=round(sum(krank_v.values()), 2) if krank_v else None,
        ),
        ueberstunden_top=[Person(**p) for p in ueber_top],
        krankheit_top=[Person(**p) for p in krank_top],
        meta=meta_obj,
    )
