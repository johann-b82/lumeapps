"""Belegschafts-KPIs für das HR-Dashboard (v1.113).

Vier Kennzahlen aus den Personio-Stammdaten der **aktiven** Belegschaft:
Geschlecht, Beschäftigungsart (Vollzeit/Teilzeit/Geringfügig/Extern), neue vs.
bestehende Mitarbeiter (Eintritt im laufenden Quartal) und Kopfzahl je Abteilung.

Viewer-lesbar (Dashboard-KPIs, keine Namen — nur Aggregate).
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
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


@router.get("/belegschaft-kpi", response_model=BelegschaftKpi)
async def belegschaft_kpi(
    db: AsyncSession = Depends(get_async_db_session),
) -> BelegschaftKpi:
    aktive = (
        (await db.execute(select(PersonioEmployee).where(PersonioEmployee.status == "active")))
        .scalars()
        .all()
    )
    q_start = _quartal_start(date.today())

    g: dict[str, int] = {}
    b: dict[str, int] = {}
    neu = bestand = 0
    abt: dict[str, int] = {}
    for e in aktive:
        g[_geschlecht(e)] = g.get(_geschlecht(e), 0) + 1
        b[_beschaeftigung(e)] = b.get(_beschaeftigung(e), 0) + 1
        if e.hire_date and e.hire_date >= q_start:
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
    )
