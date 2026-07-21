"""Schulungs-Modul — Import der Schulungsübersicht und Auswertungen.

Der gesamte Router ist admin-gated (Stufe 1 des Moduls ist HR-intern). Sobald
Vorgesetzten- und Trainer-Sichten dazukommen, wird die Gate-Struktur hier
aufgeteilt und im Docstring dokumentiert.

Compute-justified: clause 1 (file parsing) — die Import-Routen lesen eine
hochgeladene .xlsx serverseitig ein; clause 3 (multi-row atomic compute) — die
Übernahme schreibt Katalog und Teilnahmen in einer Transaktion.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import PersonioEmployee, SchulungKatalog, SchulungTeilnahme
from app.parsing.schulung_parser import parse_schulungsuebersicht
# Bewusst wiederverwendet statt dupliziert: der JSON-Pfad zum Vorgesetzten in
# den Personio-Rohdaten soll nur an einer Stelle gepflegt werden.
from app.routers.hr_kpis import _extract_supervisor_id
from app.security.directus_auth import get_current_user, require_admin
from app.services.schulung_import import ImportVorschau, baue_vorschau, uebernehmen

router = APIRouter(
    prefix="/api/hr/schulungen",
    tags=["schulungen"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


class NichtZugeordnetRead(BaseModel):
    personalnummer: str
    mitarbeiter_name: str | None
    anzahl_teilnahmen: int


class ImportVorschauRead(BaseModel):
    """Ergebnis von Vorschau und Übernahme — bewusst identische Form."""

    dateiname: str
    schulungen_gesamt: int
    schulungen_neu: int
    teilnahmen_gesamt: int
    teilnahmen_zugeordnet: int
    bereiche: dict[str, int]
    nicht_zugeordnet: list[NichtZugeordnetRead]
    warnungen: list[str]


class SchulungRead(BaseModel):
    id: int
    bereich: str
    name: str
    turnus: str | None
    turnus_monate: int | None
    aktiv: bool
    teilnahmen: int


class AbteilungRead(BaseModel):
    """Abteilung mit ihrem Hauptverantwortlichen.

    ``vorgesetzter`` ist die Person, die innerhalb der Abteilung die meisten
    Mitarbeiter führt. ``weitere_vorgesetzte`` zählt zusätzliche Führungskräfte
    derselben Abteilung — mehrere sind der Normalfall (z. B. Production), und
    eine davon willkürlich als "die" Leitung auszugeben wäre falsch.
    """

    abteilung: str
    mitarbeiter: int
    vorgesetzter: str | None
    unterstellte: int
    weitere_vorgesetzte: int


def _als_read(v: ImportVorschau) -> ImportVorschauRead:
    return ImportVorschauRead(
        dateiname=v.dateiname,
        schulungen_gesamt=v.schulungen_gesamt,
        schulungen_neu=v.schulungen_neu,
        teilnahmen_gesamt=v.teilnahmen_gesamt,
        teilnahmen_zugeordnet=v.teilnahmen_zugeordnet,
        bereiche=v.bereiche,
        nicht_zugeordnet=[
            NichtZugeordnetRead(
                personalnummer=n.personalnummer,
                mitarbeiter_name=n.mitarbeiter_name,
                anzahl_teilnahmen=n.anzahl_teilnahmen,
            )
            for n in v.nicht_zugeordnet
        ],
        warnungen=v.warnungen,
    )


async def _parse_upload(file: UploadFile):
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Bitte eine .xlsx-Datei hochladen.")
    inhalt = await file.read()
    try:
        return parse_schulungsuebersicht(inhalt)
    except Exception as exc:  # openpyxl wirft je nach Defekt sehr unterschiedlich
        raise HTTPException(
            status_code=400, detail=f"Datei konnte nicht gelesen werden: {exc}"
        ) from exc


@router.post("/import/preview", response_model=ImportVorschauRead)
async def import_preview(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> ImportVorschauRead:
    """Datei analysieren, ohne etwas zu schreiben."""
    parsed = await _parse_upload(file)
    return _als_read(await baue_vorschau(db, parsed, file.filename or "unbenannt.xlsx"))


@router.post("/import/commit", response_model=ImportVorschauRead)
async def import_commit(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> ImportVorschauRead:
    """Datei übernehmen (idempotent: erneuter Import aktualisiert)."""
    parsed = await _parse_upload(file)
    return _als_read(await uebernehmen(db, parsed, file.filename or "unbenannt.xlsx"))


class MitarbeiterSchulungRead(BaseModel):
    """Eine Schulung im Blick eines Mitarbeiters."""

    schulung_id: int
    bereich: str
    name: str
    turnus: str | None
    initial_datum: date | None
    aktuell_datum: date | None
    naechste_faellig: str | None
    naechste_faellig_am: date | None
    #: "ueberfaellig" | "bald" | "ok" | "ohne_frist"
    status: str


class MitarbeiterRead(BaseModel):
    """Zeile der Mitarbeiterübersicht."""

    employee_id: int | None
    personalnummer: str
    name: str
    abteilung: str | None
    schulungen: int
    ueberfaellig: int
    bald_faellig: int
    naechste_faelligkeit: date | None


#: Fenster, ab dem eine Fälligkeit als "bald" gilt.
BALD_FAELLIG_TAGE = 90


def _status(faellig_am: date | None, heute: date) -> str:
    if faellig_am is None:
        return "ohne_frist"
    if faellig_am < heute:
        return "ueberfaellig"
    if (faellig_am - heute).days <= BALD_FAELLIG_TAGE:
        return "bald"
    return "ok"


@router.get("/mitarbeiter", response_model=list[MitarbeiterRead])
async def liste_mitarbeiter(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[MitarbeiterRead]:
    """Übersicht: je Mitarbeiter Anzahl Schulungen und Fälligkeiten.

    Gruppiert über die Personalnummer, weil sie auch dort trägt, wo keine
    Personio-Zuordnung existiert.
    """
    heute = date.today()
    zeilen = (
        (
            await db.execute(
                select(SchulungTeilnahme, SchulungKatalog).join(
                    SchulungKatalog, SchulungKatalog.id == SchulungTeilnahme.schulung_id
                )
            )
        )
        .all()
    )

    # Abteilung aus Personio, wo zugeordnet.
    abteilungen: dict[int, str | None] = {
        e.id: e.department
        for e in (await db.execute(select(PersonioEmployee))).scalars().all()
    }

    gruppen: dict[str, MitarbeiterRead] = {}
    for teilnahme, _katalog in zeilen:
        eintrag = gruppen.get(teilnahme.personalnummer)
        if eintrag is None:
            eintrag = MitarbeiterRead(
                employee_id=teilnahme.employee_id,
                personalnummer=teilnahme.personalnummer,
                name=teilnahme.mitarbeiter_name or f"#{teilnahme.personalnummer}",
                abteilung=abteilungen.get(teilnahme.employee_id or -1),
                schulungen=0,
                ueberfaellig=0,
                bald_faellig=0,
                naechste_faelligkeit=None,
            )
            gruppen[teilnahme.personalnummer] = eintrag

        eintrag.schulungen += 1
        status = _status(teilnahme.naechste_faellig_am, heute)
        if status == "ueberfaellig":
            eintrag.ueberfaellig += 1
        elif status == "bald":
            eintrag.bald_faellig += 1
        if teilnahme.naechste_faellig_am is not None and (
            eintrag.naechste_faelligkeit is None
            or teilnahme.naechste_faellig_am < eintrag.naechste_faelligkeit
        ):
            eintrag.naechste_faelligkeit = teilnahme.naechste_faellig_am

    return sorted(
        gruppen.values(),
        key=lambda m: (-m.ueberfaellig, -m.bald_faellig, m.name.lower()),
    )


@router.get(
    "/mitarbeiter/{personalnummer}", response_model=list[MitarbeiterSchulungRead]
)
async def mitarbeiter_schulungen(
    personalnummer: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[MitarbeiterSchulungRead]:
    """Alle Schulungen eines Mitarbeiters (Einzelübersicht)."""
    heute = date.today()
    zeilen = (
        await db.execute(
            select(SchulungTeilnahme, SchulungKatalog)
            .join(SchulungKatalog, SchulungKatalog.id == SchulungTeilnahme.schulung_id)
            .where(SchulungTeilnahme.personalnummer == personalnummer)
        )
    ).all()
    if not zeilen:
        raise HTTPException(status_code=404, detail="Keine Schulungen zu dieser Personalnummer.")

    ergebnis = [
        MitarbeiterSchulungRead(
            schulung_id=k.id,
            bereich=k.bereich,
            name=k.name,
            turnus=k.turnus,
            initial_datum=t.initial_datum,
            aktuell_datum=t.aktuell_datum,
            naechste_faellig=t.naechste_faellig,
            naechste_faellig_am=t.naechste_faellig_am,
            status=_status(t.naechste_faellig_am, heute),
        )
        for t, k in zeilen
    ]
    rang = {"ueberfaellig": 0, "bald": 1, "ok": 2, "ohne_frist": 3}
    return sorted(ergebnis, key=lambda s: (rang[s.status], s.bereich, s.name))


@router.get("/abteilungen", response_model=list[AbteilungRead])
async def liste_abteilungen(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AbteilungRead]:
    """Abteilungen der aktiven Belegschaft samt Hauptverantwortlichem.

    Der Vorgesetzte wird aus den Personio-Daten abgeleitet: wer innerhalb einer
    Abteilung von den meisten Mitarbeitern als Vorgesetzter geführt wird.
    """
    aktive = (
        (
            await db.execute(
                select(PersonioEmployee).where(PersonioEmployee.status == "active")
            )
        )
        .scalars()
        .all()
    )
    namen = {
        e.id: " ".join(x for x in (e.first_name, e.last_name) if x).strip() or f"#{e.id}"
        for e in aktive
    }

    # Je Abteilung: Kopfzahl und wie oft wer als Vorgesetzter auftaucht.
    kopfzahl: dict[str, int] = {}
    fuehrung: dict[str, dict[int, int]] = {}
    for emp in aktive:
        abteilung = (emp.department or "").strip()
        if not abteilung:
            continue  # Ohne Abteilung lässt sich nichts zuordnen.
        kopfzahl[abteilung] = kopfzahl.get(abteilung, 0) + 1
        sup_id = _extract_supervisor_id(emp.raw_json)
        # Nur Vorgesetzte zählen, die selbst aktiv sind.
        if sup_id is not None and sup_id in namen:
            fuehrung.setdefault(abteilung, {})[sup_id] = (
                fuehrung.setdefault(abteilung, {}).get(sup_id, 0) + 1
            )

    ergebnis: list[AbteilungRead] = []
    for abteilung, anzahl in kopfzahl.items():
        kandidaten = sorted(
            fuehrung.get(abteilung, {}).items(), key=lambda kv: kv[1], reverse=True
        )
        top = kandidaten[0] if kandidaten else None
        ergebnis.append(
            AbteilungRead(
                abteilung=abteilung,
                mitarbeiter=anzahl,
                vorgesetzter=namen.get(top[0]) if top else None,
                unterstellte=top[1] if top else 0,
                weitere_vorgesetzte=max(0, len(kandidaten) - 1),
            )
        )
    return sorted(ergebnis, key=lambda a: (-a.mitarbeiter, a.abteilung))


@router.get("", response_model=list[SchulungRead])
async def liste_schulungen(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[SchulungRead]:
    """Schulungskatalog mit Anzahl der Teilnahmen je Schulung."""
    katalog = (
        (await db.execute(select(SchulungKatalog).order_by(SchulungKatalog.bereich, SchulungKatalog.sort_order)))
        .scalars()
        .all()
    )
    zaehler: dict[int, int] = {}
    for (sid,) in (await db.execute(select(SchulungTeilnahme.schulung_id))).all():
        zaehler[sid] = zaehler.get(sid, 0) + 1
    return [
        SchulungRead(
            id=k.id,
            bereich=k.bereich,
            name=k.name,
            turnus=k.turnus,
            turnus_monate=k.turnus_monate,
            aktiv=k.aktiv,
            teilnahmen=zaehler.get(k.id, 0),
        )
        for k in katalog
    ]
