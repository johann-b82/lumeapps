"""Belegschafts-KPIs für das HR-Dashboard (v1.113).

Compute-justified: aggregiert Personio-Stammdaten der aktiven Belegschaft zu
Kennzahlen — keine reine Directus-Collection-Lesung.

Vier Kennzahlen aus den Personio-Stammdaten der **aktiven** Belegschaft:
Geschlecht, Beschäftigungsart (Vollzeit/Teilzeit/Geringfügig/Extern), neue vs.
bestehende Mitarbeiter (Eintritt im laufenden Quartal) und Kopfzahl je Abteilung.

Viewer-lesbar (Dashboard-KPIs, keine Namen — nur Aggregate).
"""
from __future__ import annotations

import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import PersonioEmployee
from app.security.directus_auth import get_current_user, require_dashboard_read

router = APIRouter(
    prefix="/api/hr",
    tags=["hr-belegschaft"],
    dependencies=[Depends(get_current_user), Depends(require_dashboard_read)],
)


class LabelWert(BaseModel):
    key: str
    wert: int


class AbteilungWert(BaseModel):
    name: str
    wert: int


class BelegschaftKpi(BaseModel):
    gesamt: int
    geschlecht: list[LabelWert]
    beschaeftigung: list[LabelWert]
    eintritt: list[LabelWert]
    abteilungen: list[AbteilungWert]
    #: Stichtag der Auswertung — None bei der aktuellen (statusbasierten) Ansicht,
    #: sonst das Periodenende (bzw. heute, wenn die Periode noch läuft).
    stichtag: date | None = None


class BelegschaftMeta(BaseModel):
    #: Frühestes und aktuelles Jahr für die Zeitraum-Auswahl im Dashboard.
    min_jahr: int
    aktuelles_jahr: int


def _attrs(emp: PersonioEmployee) -> dict:
    return (emp.raw_json or {}).get("attributes", {}) or {}


def _geschlecht(emp: PersonioEmployee) -> str:
    v = (_attrs(emp).get("gender") or {})
    val = (v.get("value") if isinstance(v, dict) else None) or ""
    return {"male": "maennlich", "female": "weiblich", "diverse": "divers"}.get(
        str(val).lower(), "unbekannt"
    )


def _beschaeftigung(emp: PersonioEmployee) -> str:
    attrs = _attrs(emp)
    et = attrs.get("employment_type") or {}
    if isinstance(et, dict) and str(et.get("value")).lower() == "external":
        return "extern"
    # „Art der Beschäftigung" ist ein dynamisches Feld (dynamic_NNNN) — über das
    # Label finden, nicht über den Schlüssel.
    art = ""
    for feld in attrs.values():
        if isinstance(feld, dict) and feld.get("label") == "Art der Beschäftigung":
            art = str(feld.get("value") or "")
            break
    s = art.lower()
    if "geringf" in s:
        return "geringfuegig"
    if "teilzeit" in s:
        return "teilzeit"
    if "vollzeit" in s:
        return "vollzeit"
    # Fallback für Minijobs ohne gepflegte „Art der Beschäftigung": der
    # Personengruppenschlüssel 109 kennzeichnet geringfügig Beschäftigte.
    for feld in attrs.values():
        if isinstance(feld, dict) and "geringfügig" in str(feld.get("value") or "").lower():
            return "geringfuegig"
    # Interne ohne Angabe (in der Praxis Management/Geschäftsführung) → Vollzeit.
    return "vollzeit"


def _quartal_start(heute: date) -> date:
    return date(heute.year, ((heute.month - 1) // 3) * 3 + 1, 1)


def _perioden_grenzen(jahr: int, quartal: int | None) -> tuple[date, date]:
    """Start/Ende eines Jahres oder Quartals (quartal=None → Gesamtjahr)."""
    if quartal is None:
        return date(jahr, 1, 1), date(jahr, 12, 31)
    if quartal not in (1, 2, 3, 4):
        raise ValueError("Quartal muss 1–4 sein.")
    start_monat = (quartal - 1) * 3 + 1
    end_monat = start_monat + 2
    letzter = calendar.monthrange(jahr, end_monat)[1]
    return date(jahr, start_monat, 1), date(jahr, end_monat, letzter)


async def aggregiere_belegschaft(
    db: AsyncSession, *, jahr: int | None = None, quartal: int | None = None
) -> BelegschaftKpi:
    """Belegschafts-KPIs berechnen — von der Route UND vom Newsletter-Snapshot genutzt.

    Ohne ``jahr``: aktuelle Belegschaft (statusbasiert ``active``), „neu" = Eintritt
    im laufenden Quartal — unverändertes Verhalten (Newsletter-Snapshot).

    Mit ``jahr`` (optional ``quartal``): **Stichtag am Periodenende** — Kopfzahl =
    wer am Stichtag beschäftigt war (Eintritt ≤ Stichtag, noch nicht ausgetreten).
    „neu" = Eintritt innerhalb der Periode. Läuft die Periode noch, ist der
    Stichtag heute. Verteilungen nutzen die heutigen Stammdaten der damals
    Beschäftigten (Personio liefert nur den aktuellen Stand).
    """
    stichtag: date | None = None
    if jahr is None:
        # Aktuell / statusbasiert (unverändert).
        aktive = (
            (await db.execute(select(PersonioEmployee).where(PersonioEmployee.status == "active")))
            .scalars()
            .all()
        )
        period_start = _quartal_start(date.today())
        period_ende = date.today()
    else:
        period_start, period_ende = _perioden_grenzen(jahr, quartal)
        stichtag = min(period_ende, date.today())
        # Kopfzahl zum Stichtag über Eintritts-/Austrittsdatum.
        aktive = (
            (
                await db.execute(
                    select(PersonioEmployee).where(
                        PersonioEmployee.hire_date.is_not(None),
                        PersonioEmployee.hire_date <= stichtag,
                        or_(
                            PersonioEmployee.termination_date.is_(None),
                            PersonioEmployee.termination_date > stichtag,
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        period_ende = stichtag  # „neu" nur bis zum Stichtag zählen

    g: dict[str, int] = {}
    b: dict[str, int] = {}
    neu = bestand = 0
    abt: dict[str, int] = {}
    for e in aktive:
        g[_geschlecht(e)] = g.get(_geschlecht(e), 0) + 1
        b[_beschaeftigung(e)] = b.get(_beschaeftigung(e), 0) + 1
        ist_neu = (
            e.hire_date is not None
            and period_start <= e.hire_date <= period_ende
        )
        if ist_neu:
            neu += 1
        else:
            bestand += 1
        name = (e.department or "").strip() or "Sonstige"
        abt[name] = abt.get(name, 0) + 1

    def _sortiert(d: dict[str, int], reihenfolge: list[str]) -> list[LabelWert]:
        # feste Reihenfolge zuerst, unbekannt nur wenn > 0
        out = [LabelWert(key=k, wert=d[k]) for k in reihenfolge if d.get(k)]
        for k, v in d.items():
            if k not in reihenfolge and v:
                out.append(LabelWert(key=k, wert=v))
        return out

    return BelegschaftKpi(
        gesamt=len(aktive),
        geschlecht=_sortiert(g, ["maennlich", "weiblich", "divers"]),
        beschaeftigung=_sortiert(b, ["vollzeit", "teilzeit", "geringfuegig", "extern"]),
        eintritt=[LabelWert(key="neu", wert=neu), LabelWert(key="bestand", wert=bestand)],
        abteilungen=[
            AbteilungWert(name=n, wert=w)
            for n, w in sorted(abt.items(), key=lambda x: x[1], reverse=True)
        ],
        stichtag=stichtag,
    )


@router.get("/belegschaft-kpi/meta", response_model=BelegschaftMeta)
async def belegschaft_meta(
    db: AsyncSession = Depends(get_async_db_session),
) -> BelegschaftMeta:
    """Jahresspanne für die Zeitraum-Auswahl (frühestes Eintrittsjahr … heute)."""
    min_hire = (
        await db.execute(select(func.min(PersonioEmployee.hire_date)))
    ).scalar_one_or_none()
    aktuell = date.today().year
    return BelegschaftMeta(
        min_jahr=min_hire.year if min_hire else aktuell,
        aktuelles_jahr=aktuell,
    )


@router.get("/belegschaft-kpi", response_model=BelegschaftKpi)
async def belegschaft_kpi(
    jahr: int | None = Query(None, ge=2000, le=2100),
    quartal: int | None = Query(None, ge=1, le=4),
    db: AsyncSession = Depends(get_async_db_session),
) -> BelegschaftKpi:
    try:
        return await aggregiere_belegschaft(db, jahr=jahr, quartal=quartal)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
