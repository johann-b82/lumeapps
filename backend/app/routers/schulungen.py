"""Schulungs-Modul — Import der Schulungsübersicht und Auswertungen.

Der gesamte Router ist admin-gated (Stufe 1 des Moduls ist HR-intern). Sobald
Vorgesetzten- und Trainer-Sichten dazukommen, wird die Gate-Struktur hier
aufgeteilt und im Docstring dokumentiert.

Compute-justified: clause 1 (file parsing) — die Import-Routen lesen eine
hochgeladene .xlsx serverseitig ein; clause 3 (multi-row atomic compute) — die
Übernahme schreibt Katalog und Teilnahmen in einer Transaktion.
"""
from __future__ import annotations

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
