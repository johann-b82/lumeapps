"""Einarbeitung — Matrix je Abteilung und personalisierter Einarbeitungsbogen.

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
from app.models import EinarbeitungInhalt, PersonioEmployee
from app.security.directus_auth import get_current_user, require_admin
from app.services.pdf_logo import lade_logo
from app.services.einarbeitung_pdf import (
    EinarbeitungZeile,
    dateiname,
    erzeuge_einarbeitung_pdf,
)

router = APIRouter(
    prefix="/api/hr/einarbeitung",
    tags=["einarbeitung"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


class InhaltRead(BaseModel):
    id: int
    abteilung: str
    ansprechpartner: str | None
    inhalt: str
    reihenfolge: int


class InhaltAnlegen(BaseModel):
    abteilung: str
    inhalt: str
    ansprechpartner: str | None = None


class InhaltAendern(BaseModel):
    abteilung: str | None = None
    inhalt: str | None = None
    ansprechpartner: str | None = None


@router.get("/matrix", response_model=list[InhaltRead])
async def matrix(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[InhaltRead]:
    """Alle Einarbeitungsinhalte, nach Abteilung und Reihenfolge sortiert."""
    rows = (
        (
            await db.execute(
                select(EinarbeitungInhalt).order_by(
                    EinarbeitungInhalt.abteilung, EinarbeitungInhalt.reihenfolge
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        InhaltRead(
            id=x.id,
            abteilung=x.abteilung,
            ansprechpartner=x.ansprechpartner,
            inhalt=x.inhalt,
            reihenfolge=x.reihenfolge,
        )
        for x in rows
    ]


@router.get("/abteilungen", response_model=list[str])
async def abteilungen(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[str]:
    """Wählbare Abteilungen: aktive Personio-Abteilungen plus bereits gepflegte."""
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
        await db.execute(select(EinarbeitungInhalt.abteilung).distinct())
    ).scalars().all()
    return sorted({a.strip() for a in [*aus_personio, *aus_matrix] if a and a.strip()})


@router.get("/ansprechpartner", response_model=list[str])
async def ansprechpartner_vorschlaege(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[str]:
    """Aktive Personio-Mitarbeiter als Auswahl für den Ansprechpartner.

    Der Ansprechpartner bleibt ein Name (Freitext erlaubt) — das Dropdown ist
    nur eine durchsuchbare Vorschlagsliste, damit Schreibweisen einheitlich
    bleiben und externe Personen trotzdem eintragbar sind.
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
    namen = [
        f"{e.first_name or ''} {e.last_name or ''}".strip() for e in aktive
    ]
    return sorted({n for n in namen if n})


@router.post("/inhalt", response_model=InhaltRead, status_code=201)
async def inhalt_anlegen(
    eingabe: InhaltAnlegen,
    db: AsyncSession = Depends(get_async_db_session),
) -> InhaltRead:
    """Eine Inhalts-Zeile für eine Abteilung ergänzen."""
    abteilung = eingabe.abteilung.strip()
    inhalt = eingabe.inhalt.strip()
    if not abteilung or not inhalt:
        raise HTTPException(status_code=400, detail="Abteilung und Inhalt sind Pflicht.")

    letzte = (
        await db.execute(
            select(EinarbeitungInhalt.reihenfolge)
            .where(EinarbeitungInhalt.abteilung == abteilung)
            .order_by(EinarbeitungInhalt.reihenfolge.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    zeile = EinarbeitungInhalt(
        abteilung=abteilung,
        inhalt=inhalt,
        ansprechpartner=(eingabe.ansprechpartner or "").strip() or None,
        reihenfolge=(letzte or 0) + 1,
    )
    db.add(zeile)
    await db.commit()
    await db.refresh(zeile)
    return InhaltRead(
        id=zeile.id,
        abteilung=zeile.abteilung,
        ansprechpartner=zeile.ansprechpartner,
        inhalt=zeile.inhalt,
        reihenfolge=zeile.reihenfolge,
    )


@router.put("/inhalt/{inhalt_id}", response_model=InhaltRead)
async def inhalt_aendern(
    inhalt_id: int,
    eingabe: InhaltAendern,
    db: AsyncSession = Depends(get_async_db_session),
) -> InhaltRead:
    """Eine Inhalts-Zeile ändern (nur gesetzte Felder)."""
    zeile = (
        await db.execute(
            select(EinarbeitungInhalt).where(EinarbeitungInhalt.id == inhalt_id)
        )
    ).scalar_one_or_none()
    if zeile is None:
        raise HTTPException(status_code=404, detail="Zeile nicht gefunden.")

    if eingabe.abteilung is not None:
        neu = eingabe.abteilung.strip()
        if not neu:
            raise HTTPException(status_code=400, detail="Abteilung darf nicht leer sein.")
        zeile.abteilung = neu
    if eingabe.inhalt is not None:
        neu = eingabe.inhalt.strip()
        if not neu:
            raise HTTPException(status_code=400, detail="Inhalt darf nicht leer sein.")
        zeile.inhalt = neu
    if eingabe.ansprechpartner is not None:
        zeile.ansprechpartner = eingabe.ansprechpartner.strip() or None

    await db.commit()
    await db.refresh(zeile)
    return InhaltRead(
        id=zeile.id,
        abteilung=zeile.abteilung,
        ansprechpartner=zeile.ansprechpartner,
        inhalt=zeile.inhalt,
        reihenfolge=zeile.reihenfolge,
    )


@router.delete("/inhalt/{inhalt_id}", status_code=204)
async def inhalt_entfernen(
    inhalt_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    zeile = (
        await db.execute(
            select(EinarbeitungInhalt).where(EinarbeitungInhalt.id == inhalt_id)
        )
    ).scalar_one_or_none()
    if zeile is None:
        raise HTTPException(status_code=404, detail="Zeile nicht gefunden.")
    await db.delete(zeile)
    await db.commit()


@router.get("/plan/{employee_id}/pdf")
async def plan_pdf(
    employee_id: int,
    abteilungen: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Einarbeitungsbogen einer Person als PDF.

    Ohne ``abteilungen``-Parameter werden die Inhalte der Personio-Abteilung der
    Person genommen. Über den Parameter lassen sich weitere Abteilungen ergänzen
    — für Rollen, die mehrere Bereiche abdecken (z. B. QS und Produktion).
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

    zeilen: list[EinarbeitungZeile] = []
    if gewaehlt:
        rows = (
            (
                await db.execute(
                    select(EinarbeitungInhalt)
                    .where(EinarbeitungInhalt.abteilung.in_(gewaehlt))
                    .order_by(
                        EinarbeitungInhalt.abteilung, EinarbeitungInhalt.reihenfolge
                    )
                )
            )
            .scalars()
            .all()
        )
        zeilen = [
            EinarbeitungZeile(
                abteilung=x.abteilung,
                inhalt=x.inhalt,
                ansprechpartner=x.ansprechpartner or "",
            )
            for x in rows
        ]

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
