"""Onboarding — neue Eintritte und ihr abgeleiteter Schulungsplan.

Schritte 4/5 des Prozesskonzepts. Der Router ist komplett admin-gated (HR).

Compute-justified: clause 3 (multi-row atomic compute) — das Anlegen eines
Plans schreibt mehrere Teilnahme-Zeilen in einer Transaktion; die Ableitung
selbst verknüpft Anforderungsmatrix, Rollen-Zuordnung und Bestand. Clause 2
(document generation) — /plan/{id}/pdf baut Formblatt 71 serverseitig auf und
konvertiert es über LibreOffice.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import (
    EinarbeitungInhalt,
    OnboardingAbteilung,
    OnboardingDokument,
    PersonioEmployee,
    SchulungPflicht,
    SchulungRolle,
    SchulungTeilnahme,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.maintenance_files import fetch_directus_asset
from app.services.onboarding import (
    normalisiere_position,
    plan_anlegen,
    schulungsplan,
)
from app.services.onboarding_dokumente import plan_signatur, uebersichten_erzeugen
from app.services.einarbeitung_pdf import EinarbeitungZeile
from app.services.einarbeitung_pdf import dateiname as einarb_dateiname
from app.services.onboarding_paket_pdf import erzeuge_onboarding_paket_pdf
from app.services.pdf_logo import lade_logo
from app.services.schulungsuebersicht_pdf import (
    UebersichtZeile,
    dateiname,
    erzeuge_schulungsuebersicht_pdf,
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
    #: Aktuell zugeordnetes Kürzel (über die Position), None wenn nicht gepflegt.
    abteilung_kuerzel: str | None
    hire_date: date | None
    #: Negativ = liegt n Tage zurück, positiv = beginnt in n Tagen.
    tage_bis_eintritt: int | None
    #: Neuer/bevorstehender Eintritt (Eintritt höchstens NEU_TAGE zurück oder in
    #: der Zukunft). Steuert die Markierung in der Tabelle.
    ist_neu: bool
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
    """Alle aktiven Mitarbeiter samt Umfang ihres Schulungsplans.

    Neue/bevorstehende Eintritte (Eintrittsdatum höchstens 90 Tage zurück oder in
    der Zukunft) werden über ``ist_neu`` markiert und stehen oben.
    """
    grenze = date.today() - timedelta(days=NEU_TAGE)
    aktive = (
        (
            await db.execute(
                select(PersonioEmployee).where(PersonioEmployee.status == "active")
            )
        )
        .scalars()
        .all()
    )

    heute = date.today()
    ergebnis: list[EintrittRead] = []
    for emp in aktive:
        plan = await schulungsplan(db, emp)
        ist_neu = emp.hire_date is not None and emp.hire_date >= grenze
        ergebnis.append(
            EintrittRead(
                employee_id=emp.id,
                personalnummer=plan.personalnummer,
                name=plan.name,
                position=emp.position,
                abteilung=plan.abteilung,
                abteilung_kuerzel=plan.abteilung_kuerzel,
                hire_date=emp.hire_date,
                tage_bis_eintritt=(emp.hire_date - heute).days if emp.hire_date else None,
                ist_neu=ist_neu,
                soll_gesamt=len(plan.soll),
                fehlend=len(plan.fehlend),
                kuerzel_fehlt=plan.kuerzel_fehlt,
            )
        )

    # Neue/bevorstehende zuerst (nach Eintritt absteigend), dann die übrigen nach Name.
    def sortier(e: EintrittRead):
        if e.ist_neu and e.hire_date:
            return (0, -e.hire_date.toordinal(), "")
        return (1, 0, e.name.lower())

    return sorted(ergebnis, key=sortier)


class AbteilungSetzen(BaseModel):
    employee_id: int
    #: Abteilungsname; leer = Override entfernen (Personio-Wert gilt wieder).
    abteilung: str


@router.get("/abteilungen", response_model=list[str])
async def verfuegbare_abteilungen(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[str]:
    """Wählbare Abteilungen fürs Dropdown.

    Vereinigt die Personio-Abteilungen, bereits gesetzte App-Overrides und die
    Abteilungen mit Anforderungsregeln (Ebene "personio") — dedupliziert, sortiert.
    """
    aus_personio = (
        await db.execute(
            select(PersonioEmployee.department)
            .where(PersonioEmployee.department.isnot(None))
            .distinct()
        )
    ).scalars().all()
    aus_override = (
        await db.execute(select(OnboardingAbteilung.abteilung).distinct())
    ).scalars().all()
    aus_matrix = (
        await db.execute(
            select(SchulungPflicht.abteilung)
            .where(SchulungPflicht.ebene == "personio")
            .distinct()
        )
    ).scalars().all()
    alle = {a.strip() for a in [*aus_personio, *aus_override, *aus_matrix] if a and a.strip()}
    return sorted(alle)


@router.put("/abteilung", status_code=204)
async def abteilung_setzen(
    eingabe: AbteilungSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """App-seitigen Abteilungs-Override setzen oder entfernen.

    Leerer ``abteilung``-Wert entfernt den Override — dann gilt wieder die
    Personio-Abteilung. Der Override ersetzt den Personio-Wert bei der
    Plan-Berechnung und übersteht den nächsten Sync.
    """
    await _employee(db, eingabe.employee_id)
    vorhanden = (
        await db.execute(
            select(OnboardingAbteilung).where(
                OnboardingAbteilung.employee_id == eingabe.employee_id
            )
        )
    ).scalar_one_or_none()

    wert = eingabe.abteilung.strip()
    if not wert:
        if vorhanden is not None:
            await db.delete(vorhanden)
            await db.commit()
        return

    if vorhanden is None:
        db.add(OnboardingAbteilung(employee_id=eingabe.employee_id, abteilung=wert))
    else:
        vorhanden.abteilung = wert
    await db.commit()


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


@router.get("/kuerzel", response_model=list[str])
async def verfuegbare_kuerzel(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[str]:
    """Wählbare Abteilungskürzel für die Zuordnung.

    Führend ist die Anforderungsmatrix: nur Kürzel, für die es dort Regeln gibt,
    lösen überhaupt Pflichtschulungen aus. Ergänzt um die aus dem Import
    bekannten und die bereits zugeordneten Kürzel, damit auch eine Zuordnung
    möglich bleibt, bevor die Matrix dafür gepflegt ist.
    """
    aus_matrix = (
        await db.execute(
            select(SchulungPflicht.abteilung)
            .where(SchulungPflicht.ebene == "kuerzel")
            .distinct()
        )
    ).scalars().all()
    aus_teilnahmen = (
        await db.execute(
            select(SchulungTeilnahme.abteilung_kuerzel)
            .where(SchulungTeilnahme.abteilung_kuerzel.isnot(None))
            .distinct()
        )
    ).scalars().all()
    aus_rollen = (
        await db.execute(select(SchulungRolle.abteilung_kuerzel).distinct())
    ).scalars().all()
    alle = [*aus_matrix, *aus_teilnahmen, *aus_rollen]
    return sorted({k.strip() for k in alle if k and k.strip()})


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


@router.delete("/rollen", status_code=204)
async def rolle_entfernen(
    position: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Zuordnung einer Position entfernen — das Kürzel wird wieder „nicht gewählt".

    Idempotent: gibt es keine Zuordnung, ist das kein Fehler.
    """
    norm = normalisiere_position(position)
    if not norm:
        raise HTTPException(status_code=400, detail="Position darf nicht leer sein.")
    vorhanden = (
        await db.execute(select(SchulungRolle).where(SchulungRolle.position_norm == norm))
    ).scalar_one_or_none()
    if vorhanden is not None:
        await db.delete(vorhanden)
        await db.commit()


@router.get("/plan/{employee_id}/pdf")
async def plan_als_pdf(
    employee_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Schulungsübersicht der Person als PDF (Formblatt 71).

    Listet die Soll-Schulungen aus der Anforderungsmatrix — das Blatt ist der
    Plan, den der neue Mitarbeiter abarbeitet. Zeitraum und Nachweis bleiben
    leer, bis die Schulung stattgefunden hat; ein Datum vorzugeben, das noch
    niemand terminiert hat, wäre erfunden.

    Compute-justified: clause 2 (document generation) — openpyxl-Aufbau plus
    LibreOffice-Konvertierung laufen serverseitig.
    """
    emp = await _employee(db, employee_id)
    plan = await schulungsplan(db, emp)

    zeilen = [
        UebersichtZeile(bezeichnung=f"{s.bereich}: {s.name}" if s.bereich else s.name)
        for s in plan.soll
    ]
    pdf = await erzeuge_schulungsuebersicht_pdf(
        name=plan.name,
        funktion=plan.position or "",
        zeilen=zeilen,
        logo=await lade_logo(db),
    )
    name = dateiname(plan.name, date.today())
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


@router.get("/plan/{employee_id}/paket/pdf")
async def onboarding_paket_pdf(
    employee_id: int,
    abteilungen: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Onboarding-Paket: Einarbeitungsplan UND Schulungsübersicht als ein PDF.

    Zwei Blätter einer Arbeitsmappe, in einem Rutsch zu einem mehrseitigen PDF
    konvertiert — ein Dokument zur Übergabe an den Vorgesetzten. Reihenfolge:
    erst Einarbeitungsplan, dann Schulungsübersicht.

    Der Einarbeitungsteil nimmt ohne ``abteilungen``-Parameter die Personio-
    Abteilung der Person; weitere lassen sich ergänzen (z. B. QS + Produktion).

    Compute-justified: clause 2 (document generation) — openpyxl-Aufbau plus
    LibreOffice-Konvertierung laufen serverseitig.
    """
    emp = await _employee(db, employee_id)
    plan = await schulungsplan(db, emp)

    # Einarbeitungsinhalte für die gewählten Abteilungen (Standard: Personio-Abt.).
    gewaehlt = [a.strip() for a in (abteilungen or []) if a and a.strip()]
    if not gewaehlt and emp.department:
        gewaehlt = [emp.department]
    einarb_zeilen: list[EinarbeitungZeile] = []
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
        einarb_zeilen = [
            EinarbeitungZeile(
                abteilung=x.abteilung,
                inhalt=x.inhalt,
                ansprechpartner=x.ansprechpartner or "",
            )
            for x in rows
        ]

    schul_zeilen = [
        UebersichtZeile(bezeichnung=f"{s.bereich}: {s.name}" if s.bereich else s.name)
        for s in plan.soll
    ]

    pdf = await erzeuge_onboarding_paket_pdf(
        name=plan.name,
        stelle=plan.position or "",
        beginn=emp.hire_date,
        einarbeitung=einarb_zeilen,
        schulungen=schul_zeilen,
        logo=await lade_logo(db),
    )
    name = f"{einarb_dateiname(plan.name, date.today())}".replace(
        "Einarbeitungsplan", "Onboarding-Paket"
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


class DokumentRead(BaseModel):
    """Die automatisch erzeugte Schulungsübersicht einer Person."""

    employee_id: int
    dateiname: str
    schulungen: int
    erzeugt_am: datetime
    #: True, wenn der Soll-Plan inzwischen von der abgelegten Fassung abweicht.
    veraltet: bool


@router.get("/dokumente", response_model=list[DokumentRead])
async def dokumente_liste(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[DokumentRead]:
    """Alle abgelegten Schulungsübersichten.

    ``veraltet`` vergleicht die gespeicherte Signatur mit dem heutigen Soll —
    so ist sichtbar, dass der nächste Abgleich das Dokument erneuern wird.
    """
    dokumente = (
        (await db.execute(select(OnboardingDokument))).scalars().all()
    )
    if not dokumente:
        return []

    mitarbeiter = {
        e.id: e
        for e in (
            await db.execute(
                select(PersonioEmployee).where(
                    PersonioEmployee.id.in_([d.employee_id for d in dokumente])
                )
            )
        )
        .scalars()
        .all()
    }

    ergebnis: list[DokumentRead] = []
    for d in dokumente:
        emp = mitarbeiter.get(d.employee_id)
        veraltet = False
        if emp is not None:
            plan = await schulungsplan(db, emp)
            veraltet = plan_signatur([s.schulung_id for s in plan.soll]) != d.plan_signatur
        ergebnis.append(
            DokumentRead(
                employee_id=d.employee_id,
                dateiname=d.dateiname,
                schulungen=d.schulungen,
                erzeugt_am=d.erzeugt_am,
                veraltet=veraltet,
            )
        )
    return sorted(ergebnis, key=lambda x: x.erzeugt_am, reverse=True)


@router.get("/dokumente/{employee_id}")
async def dokument_laden(
    employee_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Die abgelegte Schulungsübersicht ausliefern."""
    dok = (
        await db.execute(
            select(OnboardingDokument).where(
                OnboardingDokument.employee_id == employee_id
            )
        )
    ).scalar_one_or_none()
    if dok is None:
        raise HTTPException(
            status_code=404, detail="Für diese Person liegt keine Übersicht vor."
        )
    inhalt, _ = await fetch_directus_asset(dok.directus_file_uuid)
    return Response(
        content=inhalt,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{dok.dateiname}"'},
    )


@router.post("/dokumente/erzeugen", response_model=dict)
async def dokumente_erzeugen(
    db: AsyncSession = Depends(get_async_db_session),
) -> dict:
    """Den Lauf von Hand anstoßen, statt auf den nächsten Abgleich zu warten.

    Nützlich direkt nach dem Pflegen der Anforderungsmatrix.
    """
    lauf = await uebersichten_erzeugen(db)
    return {
        "geprueft": lauf.geprueft,
        "erzeugt": lauf.erzeugt,
        "aktualisiert": lauf.aktualisiert,
        "uebersprungen_leer": lauf.uebersprungen_leer,
        "fehler": lauf.fehler,
    }
