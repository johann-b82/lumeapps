"""Einarbeitung — Katalog, Abteilungs-Matrix und personalisierter Bogen.

Der Router ist komplett admin-gated (HR-intern), wie das übrige Onboarding.

Compute-justified: clause 2 (document generation) — /plan/{id}/pdf baut den
Einarbeitungsbogen serverseitig auf und konvertiert ihn über LibreOffice.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import EinarbeitungKatalog, EinarbeitungPflicht, PersonioEmployee
from app.security.directus_auth import get_current_user, require_admin
from app.services.pdf_logo import lade_logo
from app.services.einarbeitung_pdf import dateiname, erzeuge_einarbeitung_pdf
from app.services.einarbeitung_query import zeilen_fuer_abteilungen
from app.services.verantwortlicher_sync import person_fuer_name, sync_person_nach_name

router = APIRouter(
    prefix="/api/hr/einarbeitung",
    tags=["einarbeitung"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


# --------------------------------------------------------------------------
# Katalog: alle Einarbeitungen mit Ansprechpartner (abteilungsunabhängig)
# --------------------------------------------------------------------------


class KatalogRead(BaseModel):
    id: int
    inhalt: str
    ansprechpartner: str | None
    #: Bereich der Einarbeitung (v1.103) — erscheint im PDF als „Abteilung".
    bereich: str | None
    reihenfolge: int


class KatalogAnlegen(BaseModel):
    inhalt: str
    ansprechpartner: str | None = None
    bereich: str | None = None


class KatalogAendern(BaseModel):
    inhalt: str | None = None
    ansprechpartner: str | None = None
    bereich: str | None = None


def _katalog_read(k: EinarbeitungKatalog) -> KatalogRead:
    return KatalogRead(
        id=k.id,
        inhalt=k.inhalt,
        ansprechpartner=k.ansprechpartner,
        bereich=k.bereich,
        reihenfolge=k.reihenfolge,
    )


@router.get("/katalog", response_model=list[KatalogRead])
async def katalog(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[KatalogRead]:
    """Alle Einarbeitungen, nach Reihenfolge sortiert."""
    rows = (
        (
            await db.execute(
                select(EinarbeitungKatalog).order_by(
                    EinarbeitungKatalog.reihenfolge, EinarbeitungKatalog.id
                )
            )
        )
        .scalars()
        .all()
    )
    return [_katalog_read(k) for k in rows]


@router.post("/katalog", response_model=KatalogRead, status_code=201)
async def katalog_anlegen(
    eingabe: KatalogAnlegen,
    db: AsyncSession = Depends(get_async_db_session),
) -> KatalogRead:
    """Eine Einarbeitung dem Katalog hinzufügen."""
    inhalt = eingabe.inhalt.strip()
    if not inhalt:
        raise HTTPException(status_code=400, detail="Inhalt ist Pflicht.")
    letzte = (
        await db.execute(
            select(EinarbeitungKatalog.reihenfolge)
            .order_by(EinarbeitungKatalog.reihenfolge.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    person = (eingabe.ansprechpartner or "").strip() or None
    # Ohne Angabe: eine bereits zum Namen gesetzte Person übernehmen (überall gleich).
    if person is None:
        person = await person_fuer_name(db, inhalt)
    k = EinarbeitungKatalog(
        inhalt=inhalt,
        ansprechpartner=person,
        bereich=(eingabe.bereich or "").strip() or None,
        reihenfolge=(letzte or 0) + 1,
    )
    db.add(k)
    if person is not None:
        await sync_person_nach_name(db, inhalt, person)
    await db.commit()
    await db.refresh(k)
    return _katalog_read(k)


@router.put("/katalog/{katalog_id}", response_model=KatalogRead)
async def katalog_aendern(
    katalog_id: int,
    eingabe: KatalogAendern,
    db: AsyncSession = Depends(get_async_db_session),
) -> KatalogRead:
    """Inhalt und/oder Ansprechpartner einer Einarbeitung ändern (nur gesetzte Felder)."""
    k = await db.get(EinarbeitungKatalog, katalog_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Einarbeitung nicht gefunden.")
    if eingabe.inhalt is not None:
        neu = eingabe.inhalt.strip()
        if not neu:
            raise HTTPException(status_code=400, detail="Inhalt darf nicht leer sein.")
        k.inhalt = neu
    if eingabe.ansprechpartner is not None:
        k.ansprechpartner = eingabe.ansprechpartner.strip() or None
        # Person je Name teilen: gleichnamige Schulungen + Einarbeitungen mitziehen.
        await sync_person_nach_name(db, k.inhalt, k.ansprechpartner)
    if eingabe.bereich is not None:
        k.bereich = eingabe.bereich.strip() or None
    await db.commit()
    await db.refresh(k)
    return _katalog_read(k)


@router.delete("/katalog/{katalog_id}", status_code=204)
async def katalog_entfernen(
    katalog_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Einarbeitung samt ihrer Abteilungs-Zuordnungen entfernen."""
    k = await db.get(EinarbeitungKatalog, katalog_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Einarbeitung nicht gefunden.")
    await db.delete(k)
    await db.commit()


# --------------------------------------------------------------------------
# Matrix: welche Einarbeitung ist für welche Abteilung nötig
# --------------------------------------------------------------------------


class PflichtMatrixRead(BaseModel):
    #: Achse der Abteilungen (Spalten).
    abteilungen: list[str]
    #: Gesetzte Häkchen als "<einarbeitung_id>:<abteilung>".
    regeln: list[str]


class PflichtSetzen(BaseModel):
    einarbeitung_id: int
    abteilung: str
    pflicht: bool


@router.get("/pflicht", response_model=PflichtMatrixRead)
async def pflicht_matrix(
    db: AsyncSession = Depends(get_async_db_session),
) -> PflichtMatrixRead:
    """Abteilungs-Achse und gesetzte Zuordnungen der Einarbeitungs-Matrix."""
    regeln = (
        await db.execute(
            select(EinarbeitungPflicht.einarbeitung_id, EinarbeitungPflicht.abteilung)
        )
    ).all()
    return PflichtMatrixRead(
        abteilungen=await _abteilungen(db),
        regeln=[f"{eid}:{abt}" for eid, abt in regeln],
    )


@router.put("/pflicht", status_code=204)
async def pflicht_setzen(
    eingabe: PflichtSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Einarbeitung für eine Abteilung als nötig markieren oder entfernen."""
    abteilung = eingabe.abteilung.strip()
    if not abteilung:
        raise HTTPException(status_code=400, detail="Abteilung darf nicht leer sein.")
    if await db.get(EinarbeitungKatalog, eingabe.einarbeitung_id) is None:
        raise HTTPException(status_code=404, detail="Einarbeitung nicht gefunden.")

    vorhanden = (
        await db.execute(
            select(EinarbeitungPflicht).where(
                EinarbeitungPflicht.einarbeitung_id == eingabe.einarbeitung_id,
                EinarbeitungPflicht.abteilung == abteilung,
            )
        )
    ).scalar_one_or_none()
    if eingabe.pflicht and vorhanden is None:
        db.add(
            EinarbeitungPflicht(
                einarbeitung_id=eingabe.einarbeitung_id, abteilung=abteilung
            )
        )
    elif not eingabe.pflicht and vorhanden is not None:
        await db.delete(vorhanden)
    await db.commit()


# --------------------------------------------------------------------------
# Hilfslisten + Bogen
# --------------------------------------------------------------------------


async def _abteilungen(db: AsyncSession) -> list[str]:
    aus_personio = (
        await db.execute(
            select(PersonioEmployee.department)
            .where(
                PersonioEmployee.status == "active",
                PersonioEmployee.department.isnot(None),
            )
            .distinct()
        )
    ).scalars().all()
    aus_matrix = (
        await db.execute(select(EinarbeitungPflicht.abteilung).distinct())
    ).scalars().all()
    return sorted({a.strip() for a in [*aus_personio, *aus_matrix] if a and a.strip()})


@router.get("/abteilungen", response_model=list[str])
async def abteilungen(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[str]:
    """Wählbare Abteilungen: aktive Personio-Abteilungen plus bereits gepflegte."""
    return await _abteilungen(db)


@router.get("/ansprechpartner", response_model=list[str])
async def ansprechpartner_vorschlaege(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[str]:
    """Aktive Personio-Mitarbeiter als Vorschlag für den Ansprechpartner.

    Der Ansprechpartner bleibt Freitext (auch Externe) — das Dropdown ist nur eine
    durchsuchbare Vorschlagsliste für einheitliche Schreibweisen.
    """
    aktive = (
        (
            await db.execute(
                select(PersonioEmployee)
                .where(PersonioEmployee.status == "active")
                .order_by(PersonioEmployee.last_name, PersonioEmployee.first_name)
            )
        )
        .scalars()
        .all()
    )
    namen = [f"{e.first_name or ''} {e.last_name or ''}".strip() for e in aktive]
    return sorted({n for n in namen if n})


@router.get("/plan/{employee_id}/pdf")
async def plan_pdf(
    employee_id: int,
    abteilungen: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Einarbeitungsbogen einer Person als PDF.

    Ohne ``abteilungen``-Parameter werden die Inhalte der Personio-Abteilung der
    Person genommen. Über den Parameter lassen sich weitere Abteilungen ergänzen —
    für Rollen, die mehrere Bereiche abdecken (z. B. QS und Produktion).
    """
    emp = (
        await db.execute(
            select(PersonioEmployee).where(PersonioEmployee.id == employee_id)
        )
    ).scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")

    gewaehlt = [a.strip() for a in (abteilungen or []) if a and a.strip()]
    if not gewaehlt and emp.department:
        gewaehlt = [emp.department]

    zeilen = await zeilen_fuer_abteilungen(db, gewaehlt)

    name = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or f"#{emp.id}"
    pdf = await erzeuge_einarbeitung_pdf(
        name=name,
        stelle=emp.position or "",
        beginn=emp.hire_date,
        zeilen=zeilen,
        logo=await lade_logo(db),
    )
    datei = dateiname(name, date.today())
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{datei}.pdf"'},
    )
