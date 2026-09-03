"""Weekly Report — Mehrarbeit/Überstunden + Krankheit je ISO-Woche (v1.111).

Compute-justified: aggregiert Personio-Anwesenheit gegen das Arbeitszeit-Soll je
ISO-Woche (Rechenlogik) — keine reine Directus-Collection-Lesung.

Vier Kennzahlen je Kalenderwoche, wie im Haufe-/Excel-Report:
  1. Saldo Mehrarbeit  — Σ(Ist − Soll) über die Belegschaft, Woche + Vorwoche.
  2. geleistete Überstd. — positive Mehrarbeit je Person (Top-Liste).
  3. Krankheit in Tagen — Summe Krank-Tage (days_count), Woche + Vorwoche.
  4. Krankheit/Person    — Krank-Tage je Person (Top-Liste).

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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AppSettings, PersonioAbsence, PersonioAttendance, PersonioEmployee
from app.security.directus_auth import get_current_user, require_admin

router = APIRouter(
    prefix="/api/hr/weekly-report",
    tags=["weekly-report"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

#: Fallback-Krank-Typen (Personio-``sick_leave`` in diesem Account: Krankheit +
#: Krankheit ohne Lohnfortzahlung), falls in den Einstellungen nichts gepflegt
#: ist. Regulär kommen die IDs aus ``app_settings.personio_sick_leave_type_id``.
_DEFAULT_SICK_TYPE_IDS = {568234, 3270500}


async def _sick_type_ids(db: AsyncSession) -> set[int]:
    """Krank-Abwesenheitstypen aus den Einstellungen (Fallback: Default-Set)."""
    st = (
        await db.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()
    ids = getattr(st, "personio_sick_leave_type_id", None) if st else None
    gesammelt = {int(x) for x in ids if x is not None} if ids else set()
    return gesammelt or _DEFAULT_SICK_TYPE_IDS

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


#: Wochentag-Schlüssel im Personio-``work_schedule`` (Index = date.weekday()).
_WOCHENTAGE = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _hhmm_std(v) -> float:
    """„HH:MM" → Stunden (``08:45`` → 8.75). Ungültig/leer → 0.0."""
    if not isinstance(v, str) or ":" not in v:
        return 0.0
    hh, _, mm = v.partition(":")
    try:
        return int(hh) + int(mm) / 60.0
    except ValueError:
        return 0.0


def _tagessoll_aus_schedule(ws) -> dict[int, float] | None:
    """Wochentags-Soll (weekday-Index → Stunden) aus dem Personio-Arbeitszeitmodell.
    ``None``, wenn kein verwertbares Modell vorliegt (alle Tage 0/fehlen)."""
    if not isinstance(ws, dict):
        return None
    soll = {i: _hhmm_std(ws.get(tag)) for i, tag in enumerate(_WOCHENTAGE)}
    return soll if any(h > 0 for h in soll.values()) else None


def _fallback_soll(weekly_working_hours) -> dict[int, float]:
    """Ersatz-Tagessoll, falls kein Arbeitszeitmodell hinterlegt ist (kommt bei
    aktueller Datenlage praktisch nicht vor). Verhält sich wie zuvor: flaches
    Tagessoll = Wochenstunden/5 (Fallback 8 h) an allen Tagen."""
    daily = float(weekly_working_hours) / 5.0 if weekly_working_hours else 8.0
    return {i: daily for i in range(7)}


def _woche_grenzen(year: int, week: int) -> tuple[date, date]:
    montag = date.fromisocalendar(year, week, 1)
    return montag, montag + timedelta(days=6)


class Person(BaseModel):
    name: str
    stunden: float
    #: Nur bei Krankheit gesetzt — erlaubt das Umschalten Tage/Stunden im Frontend.
    tage: float | None = None


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
    krankheit_tage: WochenKennzahl
    krankheit_std: WochenKennzahl
    ueberstunden_top: list[Person]
    krankheit_top: list[Person]
    meta: WeeklyMeta


async def _entschuldigte_stunden(
    db: AsyncSession, montag: date, sonntag: date, soll: dict[int, dict[int, float]]
) -> dict[tuple[int, date], float]:
    """Entschuldigte Soll-Stunden je (Mitarbeiter, Tag) aus **allen** Abwesenheiten
    (Urlaub, Krank, Freizeitausgleich …), die in die Woche fallen.

    Die Abwesenheits-Stunden werden über die **Soll-Tage** der Spanne verteilt
    (proportional zum Tagessoll), nicht über Kalendertage. Da Personio ``hours``
    = Summe der Tagessolls über die Abwesenheitstage liefert, entschuldigt ein
    voller Urlaub jeden betroffenen Soll-Tag vollständig (Wochenende/Folgewoche
    verwässern das nicht); halbe Tage werden anteilig entschuldigt."""
    rows = (
        await db.execute(
            select(
                PersonioAbsence.employee_id,
                PersonioAbsence.start_date,
                PersonioAbsence.end_date,
                PersonioAbsence.hours,
            ).where(
                PersonioAbsence.start_date <= sonntag,
                PersonioAbsence.end_date >= montag,
            )
        )
    ).all()
    frei: dict[tuple[int, date], float] = {}
    for a in rows:
        if a.hours is None or not a.start_date or not a.end_date:
            continue
        smap = soll.get(a.employee_id)
        if not smap:
            continue
        # Soll-Tage der GANZEN Abwesenheits-Spanne (auch außerhalb der Woche) —
        # die Stunden werden proportional zum Tagessoll darauf verteilt.
        soll_tage: list[tuple[date, float]] = []
        d = a.start_date
        while d <= a.end_date:
            s = smap.get(d.weekday(), 0.0)
            if s > 0:
                soll_tage.append((d, s))
            d += timedelta(days=1)
        summe = sum(s for _, s in soll_tage)
        if summe <= 0:
            continue
        for d, s in soll_tage:
            if montag <= d <= sonntag:
                frei[(a.employee_id, d)] = (
                    frei.get((a.employee_id, d), 0.0) + float(a.hours) * s / summe
                )
    return frei


async def _anwesenheit_woche(db: AsyncSession, montag: date, sonntag: date):
    """Ist-Stunden, Überstunden und Saldo je Mitarbeiter für eine Woche (Wochen-Netto).

    Personio liefert je Tag oft **mehrere** Zeilen (Vor-/Nachmittag). Deshalb
    erst je (Mitarbeiter, Tag) summieren.

    Gerechnet wird gegen das **volle Wochen-Soll** aus dem Personio-Arbeitszeit­
    modell (``work_schedule``, Soll je Wochentag):

        Saldo       = Ist_Woche − effektives Wochen-Soll
        Überstunden = max(0, Saldo)

    Das effektive Wochen-Soll ist die Summe der Tagessolls über die Woche,
    gekürzt um **entschuldigte** Abwesenheiten (Urlaub/Krank). Nicht gearbeitete,
    unentschuldigte Soll-Tage zählen damit als Fehlstunden — wer die Woche unter
    Soll bleibt, erscheint nicht als Überstunde. Fehlt ein Modell, greift der
    Wochenstunden/5-Fallback.

    **Laufende Woche:** Soll zählt je Person nur bis zu ihrem letzten vollständig
    gestempelten Tag; spätere offene/fehlende Tage gelten als noch nicht erfasst
    (nicht als Fehlstunde). So ist die noch nicht fertig gesyncte aktuelle Woche
    nicht künstlich negativ; fertige Wochen bleiben unverändert.
    """
    _ws = PersonioEmployee.raw_json["attributes"]["work_schedule"]["value"]["attributes"]
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
                _ws.label("work_schedule"),
            )
            .join(PersonioEmployee, PersonioAttendance.employee_id == PersonioEmployee.id)
            .where(PersonioAttendance.date >= montag, PersonioAttendance.date <= sonntag)
        )
    ).all()

    tag: dict[tuple[int, date], float] = {}
    soll: dict[int, dict[int, float]] = {}
    name: dict[int, str] = {}
    for r in rows:
        w = _worked(r.start_time, r.end_time, r.break_minutes)
        tag[(r.employee_id, r.date)] = tag.get((r.employee_id, r.date), 0.0) + w
        if r.employee_id not in soll:
            soll[r.employee_id] = (
                _tagessoll_aus_schedule(r.work_schedule)
                or _fallback_soll(r.weekly_working_hours)
            )
        name[r.employee_id] = (
            f"{r.first_name or ''} {r.last_name or ''}".strip() or f"#{r.employee_id}"
        )

    # Ist je Mitarbeiter — nur vollständig gestempelte Tage (kein Ende → verwerfen).
    # ``letzter_tag`` = letzter Tag der Woche mit vollständiger Stempelung.
    worked: dict[int, float] = {}
    letzter_tag: dict[int, date] = {}
    for (eid, d), wtag in tag.items():
        if wtag > 0:
            worked[eid] = worked.get(eid, 0.0) + wtag
            if eid not in letzter_tag or d > letzter_tag[eid]:
                letzter_tag[eid] = d

    # Nur die **laufende** (noch nicht fertig gesyncte) Woche bekommt die Kappung
    # „Soll nur bis zum letzten gestempelten Tag": spätere offene/fehlende Tage
    # gelten dort als noch nicht erfasst, nicht als Fehlstunde. Eine voll
    # zurückliegende Woche (Sonntag vor dem letzten Anwesenheitsdatum) wird
    # komplett gewertet — dort sind fehlende Tage echte Fehlstunden.
    max_att = (
        await db.execute(select(func.max(PersonioAttendance.date)))
    ).scalar_one_or_none()
    laufend = max_att is not None and sonntag >= max_att

    entschuldigt = await _entschuldigte_stunden(db, montag, sonntag, soll)
    woche = [montag + timedelta(days=i) for i in range(7)]

    ist: dict[int, float] = {}
    ueber: dict[int, float] = {}
    netto: dict[int, float] = {}
    for eid, smap in soll.items():
        grenze = letzter_tag.get(eid) if laufend else sonntag
        soll_eff = 0.0
        for d in woche:
            if grenze is None or d > grenze:
                continue
            s = smap.get(d.weekday(), 0.0)
            if s <= 0:
                continue
            soll_eff += max(0.0, s - entschuldigt.get((eid, d), 0.0))
        w = worked.get(eid, 0.0)
        ist[eid] = w
        netto[eid] = w - soll_eff
        ueber[eid] = max(0.0, w - soll_eff)
    return ist, ueber, netto, name


def _krank_tage_gesamt(absence: PersonioAbsence) -> float | None:
    """Krank-**Tage** einer Abwesenheit aus dem Personio-Payload (``days_count``,
    berücksichtigt Halbtage). Fallback über die Stunden (Tagessoll ~8 h), falls
    ``days_count`` fehlt."""
    rj = absence.raw_json if isinstance(absence.raw_json, dict) else {}
    attrs = rj.get("attributes", {}) if isinstance(rj, dict) else {}
    dc = attrs.get("days_count") if isinstance(attrs, dict) else None
    try:
        if dc is not None:
            return float(dc)
    except (TypeError, ValueError):
        pass
    # Fallback: keine days_count → aus Stunden näherungsweise (8 h/Tag).
    if absence.hours is not None:
        return float(absence.hours) / 8.0
    return None


async def _krankheit_woche(
    db: AsyncSession, montag: date, sonntag: date, sick_ids: set[int]
):
    """Krank-**Tage und -Stunden** je Mitarbeiter für eine Woche (anteilig nach
    Überlapp-Tagen). Tage aus ``days_count`` (inkl. Halbtage), Stunden aus
    ``hours`` — beides proportional zur Kalender-Spanne auf die Woche verteilt.

    Rückgabe: ``(tage_je_mitarbeiter, stunden_je_mitarbeiter, name)``."""
    rows = (
        await db.execute(
            select(PersonioAbsence, PersonioEmployee)
            .join(PersonioEmployee, PersonioAbsence.employee_id == PersonioEmployee.id)
            .where(
                PersonioAbsence.absence_type_id.in_(sick_ids),
                PersonioAbsence.start_date <= sonntag,
                PersonioAbsence.end_date >= montag,
            )
        )
    ).all()
    per_tage: dict[int, float] = {}
    per_std: dict[int, float] = {}
    name: dict[int, str] = {}
    for absence, emp in rows:
        if not absence.start_date or not absence.end_date:
            continue
        spanne = (absence.end_date - absence.start_date).days + 1
        ueberlapp = max(
            0, (min(absence.end_date, sonntag) - max(absence.start_date, montag)).days + 1
        )
        tage_gesamt = _krank_tage_gesamt(absence)
        if tage_gesamt is not None:
            pro_tag = tage_gesamt / spanne if spanne > 0 else tage_gesamt
            per_tage[emp.id] = per_tage.get(emp.id, 0.0) + pro_tag * ueberlapp
        if absence.hours is not None:
            pro_std = float(absence.hours) / spanne if spanne > 0 else float(absence.hours)
            per_std[emp.id] = per_std.get(emp.id, 0.0) + pro_std * ueberlapp
        name[emp.id] = _name(emp)
    return per_tage, per_std, name


@router.get("/meta", response_model=WeeklyMeta)
async def meta(db: AsyncSession = Depends(get_async_db_session)) -> WeeklyMeta:
    def _kw(d: date) -> str:
        iso = d.isocalendar()
        return f"{iso[0]}-{iso[1]:02d}"

    heute_kw = _kw(date.today())
    max_att = (await db.execute(select(PersonioAttendance.date).order_by(PersonioAttendance.date.desc()).limit(1))).scalar_one_or_none()
    att_dates = (await db.execute(select(PersonioAttendance.date))).scalars().all()
    kw_set = {_kw(d) for d in att_dates}
    # Abwesenheits-Wochen ergänzen: Krankheit/Urlaub liegen aktueller als die
    # (am V1-Bruch endenden) Anwesenheiten — so bleiben aktuelle Wochen wählbar.
    abs_dates = (
        await db.execute(select(PersonioAbsence.start_date, PersonioAbsence.end_date))
    ).all()
    for s, e in abs_dates:
        if s:
            kw_set.add(_kw(s))
        if e:
            kw_set.add(_kw(e))
    # Keine Zukunftswochen anbieten (geplanter Urlaub kann in der Zukunft liegen).
    kws = sorted({k for k in kw_set if k <= heute_kw}, reverse=True)
    sick_ids = await _sick_type_ids(db)
    hat_krank = (
        await db.execute(
            select(PersonioAbsence.id).where(
                PersonioAbsence.absence_type_id.in_(sick_ids)
            ).limit(1)
        )
    ).first() is not None
    return WeeklyMeta(
        hat_anwesenheit=bool(att_dates),
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

    sick_ids = await _sick_type_ids(db)
    ist, ueber, netto, name = await _anwesenheit_woche(db, montag, sonntag)
    _, _, netto_v, _ = await _anwesenheit_woche(db, p_montag, p_sonntag)
    krank_t, krank_s, kname = await _krankheit_woche(db, montag, sonntag, sick_ids)
    krank_t_v, krank_s_v, _ = await _krankheit_woche(db, p_montag, p_sonntag, sick_ids)

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
        (
            {
                "name": kname[e],
                "tage": round(krank_t.get(e, 0.0), 2),
                "stunden": round(krank_s.get(e, 0.0), 2),
            }
            for e in set(krank_t) | set(krank_s)
            if krank_t.get(e, 0.0) > 0.01 or krank_s.get(e, 0.0) > 0.01
        ),
        key=lambda x: x["tage"],
        reverse=True,
    )[:TOP_N]

    meta_obj = await meta(db)
    return WeeklyReport(
        kw_label=f"KW {week}",
        kw_prev_label=f"KW {p_montag.isocalendar()[1]}",
        saldo_mehrarbeit=WochenKennzahl(aktuell=_saldo(netto), vorwoche=_saldo(netto_v)),
        krankheit_tage=WochenKennzahl(
            aktuell=round(sum(krank_t.values()), 2) if krank_t else None,
            vorwoche=round(sum(krank_t_v.values()), 2) if krank_t_v else None,
        ),
        krankheit_std=WochenKennzahl(
            aktuell=round(sum(krank_s.values()), 2) if krank_s else None,
            vorwoche=round(sum(krank_s_v.values()), 2) if krank_s_v else None,
        ),
        ueberstunden_top=[Person(**p) for p in ueber_top],
        krankheit_top=[Person(**p) for p in krank_top],
        meta=meta_obj,
    )
