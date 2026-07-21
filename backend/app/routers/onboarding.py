"""Onboarding — neue Eintritte und ihr abgeleiteter Schulungsplan.

Schritte 4/5 des Prozesskonzepts. Der Router ist komplett admin-gated (HR).

Compute-justified: clause 3 (multi-row atomic compute) — das Anlegen eines
Plans schreibt mehrere Teilnahme-Zeilen in einer Transaktion; die Ableitung
selbst verknüpft Anforderungsmatrix, Rollen-Zuordnung und Bestand.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import PersonioEmployee, SchulungRolle
from app.security.directus_auth import get_current_user, require_admin
from app.services.onboarding import (
    normalisiere_position,
    plan_anlegen,
    schulungsplan,
)

router = APIRouter(
    prefix="/api/hr/onboarding",
    tags=["onboarding"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

#: Fenster, in dem ein Eintritt als "neu" gilt (rückwirkend).
NEU_TAGE = 90


class SollSchulungRead(BaseModel):
    schulung_id: int
    bereich: str
    name: str
    turnus: str | None
    quelle: str
    abteilung: str
    vorhanden: bool


class SchulungsplanRead(BaseModel):
    employee_id: int
    personalnummer: str | None
    name: str
    position: str | None
    abteilung: str | None
    abteilung_kuerzel: str | None
    #: Position hat keine Zuordnung zu einem Kürzel -> feine Matrix-Ebene greift nicht.
    kuerzel_fehlt: bool
    soll: list[SollSchulungRead]
    fehlend: int


class EintrittRead(BaseModel):
    employee_id: int
    personalnummer: str | None
    name: str
    position: str | None
    abteilung: str | None
    hire_date: date | None
    #: Negativ = liegt n Tage zurück, positiv = beginnt in n Tagen.
    tage_bis_eintritt: int | None
    soll_gesamt: int
    fehlend: int
    kuerzel_fehlt: bool


class RolleRead(BaseModel):
    id: int
    position: str
    abteilung_kuerzel: str


class RolleSetzen(BaseModel):
    position: str
    abteilung_kuerzel: str


async def _employee(db: AsyncSession, employee_id: int) -> PersonioEmployee:
    emp = (
        await db.execute(
            select(PersonioEmployee).where(PersonioEmployee.id == employee_id)
        )
    ).scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")
    return emp


@router.get("/eintritte", response_model=list[EintrittRead])
async def neue_eintritte(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[EintrittRead]:
    """Neue und bevorstehende Eintritte samt Umfang ihres Schulungsplans.

    "Neu" heißt: Eintrittsdatum liegt höchstens 90 Tage zurück oder in der
    Zukunft. Ohne Eintrittsdatum taucht niemand auf.
    """
    grenze = date.today() - timedelta(days=NEU_TAGE)
    aktive = (
        (
            await db.execute(
                select(PersonioEmployee).where(
                    PersonioEmployee.status == "active",
                    PersonioEmployee.hire_date.isnot(None),
                    PersonioEmployee.hire_date >= grenze,
                )
            )
        )
        .scalars()
        .all()
    )

    heute = date.today()
    ergebnis: list[EintrittRead] = []
    for emp in aktive:
        plan = await schulungsplan(db, emp)
        ergebnis.append(
            EintrittRead(
                employee_id=emp.id,
                personalnummer=plan.personalnummer,
                name=plan.name,
                position=emp.position,
                abteilung=emp.department,
                hire_date=emp.hire_date,
                tage_bis_eintritt=(emp.hire_date - heute).days if emp.hire_date else None,
                soll_gesamt=len(plan.soll),
                fehlend=len(plan.fehlend),
                kuerzel_fehlt=plan.kuerzel_fehlt,
            )
        )
    return sorted(ergebnis, key=lambda e: (e.hire_date or date.max), reverse=True)


@router.get("/plan/{employee_id}", response_model=SchulungsplanRead)
async def plan_ansehen(
    employee_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> SchulungsplanRead:
    """Soll/Ist einer Person — schreibt nichts."""
    emp = await _employee(db, employee_id)
    plan = await schulungsplan(db, emp)
    return SchulungsplanRead(
        employee_id=emp.id,
        personalnummer=plan.personalnummer,
        name=plan.name,
        position=plan.position,
        abteilung=plan.abteilung,
        abteilung_kuerzel=plan.abteilung_kuerzel,
        kuerzel_fehlt=plan.kuerzel_fehlt,
        soll=[SollSchulungRead(**vars(s)) for s in plan.soll],
        fehlend=len(plan.fehlend),
    )


@router.post("/plan/{employee_id}", response_model=SchulungsplanRead)
async def plan_erzeugen(
    employee_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> SchulungsplanRead:
    """Fehlende Pflichtschulungen als offene Zeilen anlegen (idempotent)."""
    emp = await _employee(db, employee_id)
    plan = await plan_anlegen(db, emp)
    return SchulungsplanRead(
        employee_id=emp.id,
        personalnummer=plan.personalnummer,
        name=plan.name,
        position=plan.position,
        abteilung=plan.abteilung,
        abteilung_kuerzel=plan.abteilung_kuerzel,
        kuerzel_fehlt=plan.kuerzel_fehlt,
        soll=[SollSchulungRead(**vars(s)) for s in plan.soll],
        fehlend=len(plan.fehlend),
    )


@router.get("/rollen", response_model=list[RolleRead])
async def rollen_liste(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[RolleRead]:
    """Zuordnungen Position → Abteilungskürzel."""
    rows = (
        (await db.execute(select(SchulungRolle).order_by(SchulungRolle.position)))
        .scalars()
        .all()
    )
    return [
        RolleRead(id=r.id, position=r.position, abteilung_kuerzel=r.abteilung_kuerzel)
        for r in rows
    ]


@router.put("/rollen", response_model=RolleRead)
async def rolle_setzen(
    eingabe: RolleSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> RolleRead:
    """Zuordnung anlegen oder ändern (Schlüssel ist die normalisierte Position)."""
    norm = normalisiere_position(eingabe.position)
    if not norm:
        raise HTTPException(status_code=400, detail="Position darf nicht leer sein.")

    vorhanden = (
        await db.execute(select(SchulungRolle).where(SchulungRolle.position_norm == norm))
    ).scalar_one_or_none()

    if vorhanden is None:
        vorhanden = SchulungRolle(
            position=eingabe.position.strip(),
            position_norm=norm,
            abteilung_kuerzel=eingabe.abteilung_kuerzel.strip(),
        )
        db.add(vorhanden)
    else:
        vorhanden.abteilung_kuerzel = eingabe.abteilung_kuerzel.strip()
    await db.commit()
    await db.refresh(vorhanden)
    return RolleRead(
        id=vorhanden.id,
        position=vorhanden.position,
        abteilung_kuerzel=vorhanden.abteilung_kuerzel,
    )
