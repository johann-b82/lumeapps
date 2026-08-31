"""Schulungs-Modul — Import der Schulungsübersicht und Auswertungen.

Der gesamte Router ist admin-gated (Stufe 1 des Moduls ist HR-intern). Sobald
Vorgesetzten- und Trainer-Sichten dazukommen, wird die Gate-Struktur hier
aufgeteilt und im Docstring dokumentiert.

Compute-justified: clause 1 (file parsing) — die Import-Routen lesen eine
hochgeladene .xlsx serverseitig ein; clause 3 (multi-row atomic compute) — die
Übernahme schreibt Katalog und Teilnahmen in einer Transaktion.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import (
    OnboardingExtern,
    PersonioEmployee,
    SchulungDokument,
    SchulungKatalog,
    SchulungPflicht,
    SchulungTeilnahme,
    SchulungUnterlage,
    SchulungZertifikat,
)
from app.services import schulung_dokument as schulung_vorgang
from app.services.directus_files import datei_laden, datei_speichern
from app.services.onboarding import schulungsplan
from app.models.schulung import PFLICHT_EBENEN
from app.parsing.schulung_parser import parse_schulungsuebersicht
# Bewusst wiederverwendet statt dupliziert: der JSON-Pfad zum Vorgesetzten in
# den Personio-Rohdaten soll nur an einer Stelle gepflegt werden.
from app.routers.hr_kpis import _extract_office, _extract_supervisor_id
from app.services import personio_writeback
from app.security.directus_auth import get_current_user, require_admin
from app.services.verantwortlicher_sync import (
    sync_beschreibung_nach_name,
    sync_frist_nach_name,
    sync_person_nach_name,
    sync_turnus_nach_name,
)
from app.services.maintenance_files import (
    fetch_directus_asset,
    upload_maintenance_file_to_directus,
)
from app.services.pdf_logo import lade_logo
from app.services.schulungsprotokoll_pdf import (
    dateiname as protokoll_dateiname,
    erzeuge_schulungsprotokoll_pdf,
)
from app.services.schulung_import import (
    ImportVorschau,
    _faellig_am,
    _personalnummer,
    baue_vorschau,
    uebernehmen,
)
from app.services import schulungsbericht_import as bericht_import
from app.parsing.schulungsbericht_parser import SchulungsberichtError

router = APIRouter(
    prefix="/api/hr/schulungen",
    tags=["schulungen"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


def _name_norm(name: str) -> str:
    """Normalisierter Schulungs-Name — Schlüssel für geteilte Unterlagen."""
    return (name or "").strip().lower()


#: Erlaubte Unterlagen-Dateitypen (Endung → MIME).
_UNTERLAGE_TYPEN = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
}


def _unterlage_ext(dateiname: str) -> str:
    punkt = dateiname.rfind(".")
    return dateiname[punkt:].lower() if punkt >= 0 else ""


def _sicherer_dateiname(name: str) -> str:
    return name.replace('"', "").replace("\\", "").replace("/", "").strip() or "datei"


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
    #: Frist in Tagen nach Eintritt/Zuweisung (v1.93); None = nicht definiert.
    frist_tage: int | None
    #: Verantwortlicher/Trainer (v1.94); None = nicht gesetzt.
    verantwortlicher: str | None
    #: Schulungsbeschreibung (v1.100); None = leer.
    beschreibung: str | None
    #: Anzahl hinterlegter Unterlagen (v1.100).
    anzahl_unterlagen: int
    aktiv: bool
    teilnahmen: int


class AbteilungRead(BaseModel):
    """Abteilung mit ihren Vorgesetzten.

    ``vorgesetzte`` listet alle Personen, die mindestens einen Mitarbeiter dieser
    Abteilung führen — absteigend nach Anzahl Unterstellter. Mehrere sind der
    Normalfall (z. B. Production).
    """

    abteilung: str
    mitarbeiter: int
    vorgesetzte: list[str]


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


# --- Schulungsbericht-Upload (PDF) → Stand fortschreiben -----------------------


class BerichtZeileRead(BaseModel):
    mitarbeiter_name: str
    schulung_name: str
    datum: date | None
    #: "ok" | "nicht_gefunden" | "mehrdeutig"
    mitarbeiter_status: str
    #: aufgelöste Personio-ID (None, wenn nicht/mehrdeutig) — Vorauswahl im Dropdown.
    employee_id: int | None
    matched_mitarbeiter: str | None
    schulung_im_katalog: bool
    uebernehmbar: bool


class BerichtVorschauRead(BaseModel):
    format: str
    format_label: str
    gesamt: int
    uebernehmbar: int
    ohne_mitarbeiter: int
    ohne_datum: int
    neue_schulungen: int
    zeilen: list[BerichtZeileRead]


def _bericht_read(erg: bericht_import.BerichtErgebnis) -> BerichtVorschauRead:
    return BerichtVorschauRead(
        format=erg.format,
        format_label=erg.format_label,
        gesamt=erg.gesamt,
        uebernehmbar=erg.uebernehmbar,
        ohne_mitarbeiter=erg.ohne_mitarbeiter,
        ohne_datum=erg.ohne_datum,
        neue_schulungen=erg.neue_schulungen,
        zeilen=[BerichtZeileRead(**vars(z)) for z in erg.zeilen],
    )


@router.post("/bericht/preview", response_model=BerichtVorschauRead)
async def bericht_preview(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> BerichtVorschauRead:
    """Schulungsbericht-PDF (Fbl. 68/71) auswerten und zuordnen — nichts schreiben."""
    try:
        erg = await bericht_import.vorschau(db, await file.read())
    except SchulungsberichtError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _bericht_read(erg)


class BerichtCommitZeile(BaseModel):
    employee_id: int
    schulung_name: str
    datum: date


class BerichtCommitEingabe(BaseModel):
    zeilen: list[BerichtCommitZeile]


class BerichtCommitErgebnis(BaseModel):
    eingetragen: int
    angelegte_schulungen: int


@router.post("/bericht/commit", response_model=BerichtCommitErgebnis)
async def bericht_commit(
    eingabe: BerichtCommitEingabe,
    db: AsyncSession = Depends(get_async_db_session),
) -> BerichtCommitErgebnis:
    """Bearbeitete Berichtszeilen übernehmen: Durchführung setzen, fehlende Schulungen anlegen."""
    res = await bericht_import.uebernehmen_zeilen(
        db,
        [
            bericht_import.CommitZeile(
                employee_id=z.employee_id, schulung_name=z.schulung_name, datum=z.datum
            )
            for z in eingabe.zeilen
        ],
    )
    # Personio-Rückschreiben (inert bis Freischaltung) — je betroffenem Mitarbeiter.
    for eid in dict.fromkeys(z.employee_id for z in eingabe.zeilen):
        asyncio.create_task(personio_writeback.nach_schulung_update(eid))
    return BerichtCommitErgebnis(**res)


class PflichtMatrixRead(BaseModel):
    """Anforderungsmatrix: Achsen plus gesetzte Regeln.

    ``regeln`` enthält nur die gesetzten Häkchen als "<schulung_id>:<abteilung>",
    damit die Oberfläche nicht 87 × 25 leere Zellen übertragen muss.
    """

    ebene: str
    abteilungen: list[str]
    regeln: list[str]


class PflichtSetzen(BaseModel):
    schulung_id: int
    ebene: str
    abteilung: str
    pflicht: bool


@router.get("/pflicht/{ebene}", response_model=PflichtMatrixRead)
async def pflicht_matrix(
    ebene: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> PflichtMatrixRead:
    """Achse und gesetzte Pflicht-Regeln einer Ebene.

    ``kuerzel``  — Abteilungskürzel aus der Schulungs-Excel (fein).
    ``personio`` — Abteilungen aktiver Personio-Mitarbeiter (grob).
    """
    if ebene not in PFLICHT_EBENEN:
        raise HTTPException(status_code=400, detail="Unbekannte Ebene.")

    if ebene == "kuerzel":
        werte = (
            await db.execute(
                select(SchulungTeilnahme.abteilung_kuerzel)
                .where(SchulungTeilnahme.abteilung_kuerzel.isnot(None))
                .distinct()
            )
        ).scalars().all()
    else:
        werte = (
            await db.execute(
                select(PersonioEmployee.department)
                .where(
                    PersonioEmployee.status == "active",
                    PersonioEmployee.department.isnot(None),
                )
                .distinct()
            )
        ).scalars().all()

    regeln = (
        await db.execute(
            select(SchulungPflicht.schulung_id, SchulungPflicht.abteilung).where(
                SchulungPflicht.ebene == ebene
            )
        )
    ).all()

    return PflichtMatrixRead(
        ebene=ebene,
        abteilungen=sorted({w.strip() for w in werte if w and w.strip()}),
        regeln=[f"{sid}:{abt}" for sid, abt in regeln],
    )


@router.put("/pflicht", status_code=204)
async def pflicht_setzen(
    eingabe: PflichtSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Ein Häkchen setzen oder entfernen (idempotent)."""
    if eingabe.ebene not in PFLICHT_EBENEN:
        raise HTTPException(status_code=400, detail="Unbekannte Ebene.")

    vorhanden = (
        await db.execute(
            select(SchulungPflicht).where(
                SchulungPflicht.schulung_id == eingabe.schulung_id,
                SchulungPflicht.ebene == eingabe.ebene,
                SchulungPflicht.abteilung == eingabe.abteilung,
            )
        )
    ).scalar_one_or_none()

    if eingabe.pflicht and vorhanden is None:
        db.add(
            SchulungPflicht(
                schulung_id=eingabe.schulung_id,
                ebene=eingabe.ebene,
                abteilung=eingabe.abteilung,
            )
        )
    elif not eingabe.pflicht and vorhanden is not None:
        await db.delete(vorhanden)
    await db.commit()


class MitarbeiterSchulungRead(BaseModel):
    """Eine Schulung im Blick eines Mitarbeiters."""

    #: Zeilen-ID, damit eine Einzelzuweisung wieder entfernt werden kann.
    teilnahme_id: int
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

    #: Stabiler Schlüssel für die Detailsicht: "p:<personalnummer>" oder
    #: "e:<employee_id>". Seit v1_89 gibt es Zeilen ohne Personalnummer; nach
    #: ihr allein zu gruppieren würde alle diese Personen zu einer verschmelzen.
    schluessel: str
    employee_id: int | None
    personalnummer: str | None
    name: str
    abteilung: str | None
    #: Personio-Standort (Workplace, z. B. "Hamburg"); None bei Externen.
    office: str | None
    schulungen: int
    ueberfaellig: int
    bald_faellig: int
    naechste_faelligkeit: date | None


#: Fenster, ab dem eine Fälligkeit als "bald" gilt.
BALD_FAELLIG_TAGE = 90


def _schluessel(teilnahme: SchulungTeilnahme) -> str | None:
    """Adressierbarer Schlüssel einer Teilnahme-Zeile.

    Die Personalnummer hat Vorrang, weil sie die Excel-Historie zusammenhält;
    Zeilen ohne sie (seit v1_89 möglich) laufen über die Personio-ID.
    """
    if teilnahme.personalnummer:
        return f"p:{teilnahme.personalnummer}"
    if teilnahme.employee_id is not None:
        return f"e:{teilnahme.employee_id}"
    if teilnahme.extern_id is not None:
        return f"x:{teilnahme.extern_id}"
    return None


def _schluessel_filter(schluessel: str):
    """Übersetzt einen Schlüssel in die passende WHERE-Bedingung."""
    art, _, wert = schluessel.partition(":")
    if art == "p" and wert:
        return SchulungTeilnahme.personalnummer == wert
    if art == "e" and wert.isdigit():
        return SchulungTeilnahme.employee_id == int(wert)
    if art == "x" and wert.isdigit():
        return SchulungTeilnahme.extern_id == int(wert)
    raise HTTPException(status_code=400, detail="Unbekannter Mitarbeiter-Schlüssel.")


def _status(faellig_am: date | None, heute: date) -> str:
    if faellig_am is None:
        return "ohne_frist"
    if faellig_am < heute:
        return "ueberfaellig"
    if (faellig_am - heute).days <= BALD_FAELLIG_TAGE:
        return "bald"
    return "ok"


def _effektive_faelligkeit(
    teilnahme: SchulungTeilnahme, frist_tage: int | None, hire_date: date | None
) -> date | None:
    """Fälligkeitsdatum einer Teilnahme.

    * Absolviert (``aktuell_datum`` gesetzt): ``naechste_faellig_am`` aus dem
      Wiederholungs-Turnus.
    * Noch offen (kein ``aktuell_datum``): Eintrittsdatum + Frist-Tage der
      Schulung, sofern beide bekannt — so wird eine neu zugewiesene Pflicht­
      schulung fristgerecht fällig statt "ohne Frist" zu bleiben.
    * Sonst None (keine berechenbare Frist).
    """
    if teilnahme.naechste_faellig_am is not None:
        return teilnahme.naechste_faellig_am
    if teilnahme.aktuell_datum is None and frist_tage is not None and hire_date is not None:
        return hire_date + timedelta(days=frist_tage)
    return None


class ZuweisbarerMitarbeiterRead(BaseModel):
    """Auswahl für die Einzelzuweisung — alle aktiven Personio-Mitarbeiter."""

    employee_id: int
    personalnummer: str | None
    name: str
    abteilung: str | None
    #: Personio-Standort (Workplace, z. B. "Hamburg"); None bei Externen.
    office: str | None


class ZuweisungRead(BaseModel):
    teilnahme_id: int
    employee_id: int
    schulung_id: int
    name: str
    schulung: str


class ZuweisungSetzen(BaseModel):
    employee_id: int
    schulung_id: int


@router.get("/zuweisbar", response_model=list[ZuweisbarerMitarbeiterRead])
async def zuweisbare_mitarbeiter(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[ZuweisbarerMitarbeiterRead]:
    """Aktive und neu eintretende Mitarbeiter für Zuweisung/Durchführung.

    Quelle ist Personio, nicht der Teilnahme-Bestand: zuweisen/eintragen muss auch
    für jemanden möglich sein, der noch gar keine Schulung hat. Neben ``active``
    zählen auch ``onboarding`` (frisch Eingestellte) — genau die, denen man erste
    Schulungen einträgt. Ausgetretene (``inactive``) bleiben außen vor.
    """
    aktive = (
        (
            await db.execute(
                select(PersonioEmployee)
                .where(PersonioEmployee.status.in_(("active", "onboarding")))
                .order_by(PersonioEmployee.last_name, PersonioEmployee.first_name)
            )
        )
        .scalars()
        .all()
    )
    ergebnis = [
        ZuweisbarerMitarbeiterRead(
            employee_id=e.id,
            personalnummer=_personalnummer(e.raw_json),
            name=f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}",
            abteilung=e.department,
            office=_extract_office(e.raw_json),
        )
        for e in aktive
    ]
    # Manuell gepflegte (Nicht-Personio-)Einträge — negative ID (= -onboarding_extern.id).
    # Externe haben keinen Personio-Standort (office=None).
    externe = (await db.execute(select(OnboardingExtern))).scalars().all()
    ergebnis.extend(
        ZuweisbarerMitarbeiterRead(
            employee_id=-x.id,
            personalnummer=None,
            name=x.name,
            abteilung=x.abteilung,
            office=None,
        )
        for x in externe
    )
    return ergebnis


async def _teilnahme_ident(db: AsyncSession, employee_id: int):
    """(Name, Teilnahme-Felder, Such-Bedingungen) für eine (evtl. negative) ID.

    Positiv = Personio-Mitarbeiter, negativ = externer Eintrag (= -onboarding_extern.id).
    Gibt None zurück, wenn die Person nicht existiert.
    """
    if employee_id < 0:
        ext = await db.get(OnboardingExtern, -employee_id)
        if ext is None:
            return None
        return ext.name, {"extern_id": ext.id}, [SchulungTeilnahme.extern_id == ext.id]
    emp = (
        await db.execute(
            select(PersonioEmployee).where(PersonioEmployee.id == employee_id)
        )
    ).scalar_one_or_none()
    if emp is None:
        return None
    persnr = _personalnummer(emp.raw_json)
    name = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or f"#{emp.id}"
    conds = [SchulungTeilnahme.employee_id == emp.id]
    if persnr:
        conds.append(SchulungTeilnahme.personalnummer == persnr)
    return name, {"employee_id": emp.id, "personalnummer": persnr}, conds


@router.post("/zuweisen", response_model=ZuweisungRead, status_code=201)
async def schulung_zuweisen(
    eingabe: ZuweisungSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> ZuweisungRead:
    """Eine einzelne Schulung einer einzelnen Person zuweisen.

    Ergänzt die Anforderungsmatrix, die nur abteilungsweit wirkt. Die Zeile
    entsteht ohne Datumsangaben ("offen"). Externe (negative ID) sind erlaubt.
    """
    ident = await _teilnahme_ident(db, eingabe.employee_id)
    if ident is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")
    name, felder, bedingungen = ident

    katalog = (
        await db.execute(
            select(SchulungKatalog).where(SchulungKatalog.id == eingabe.schulung_id)
        )
    ).scalar_one_or_none()
    if katalog is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")

    vorhanden = (
        await db.execute(
            select(SchulungTeilnahme).where(
                SchulungTeilnahme.schulung_id == katalog.id, or_(*bedingungen)
            )
        )
    ).scalars().first()
    if vorhanden is not None:
        raise HTTPException(
            status_code=409, detail="Diese Schulung ist der Person bereits zugewiesen."
        )

    zeile = SchulungTeilnahme(
        schulung_id=katalog.id, mitarbeiter_name=name, **felder
    )
    db.add(zeile)
    await db.commit()
    await db.refresh(zeile)
    return ZuweisungRead(
        teilnahme_id=zeile.id,
        employee_id=eingabe.employee_id,
        schulung_id=katalog.id,
        name=name,
        schulung=katalog.name,
    )


@router.delete("/zuweisung/{teilnahme_id}", status_code=204)
async def zuweisung_entfernen(
    teilnahme_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Zuweisung zurücknehmen.

    Nur solange nichts nachgewiesen ist: sobald Daten eingetragen sind, ist die
    Zeile ein Nachweis und wird nicht stillschweigend gelöscht.
    """
    zeile = (
        await db.execute(
            select(SchulungTeilnahme).where(SchulungTeilnahme.id == teilnahme_id)
        )
    ).scalar_one_or_none()
    if zeile is None:
        raise HTTPException(status_code=404, detail="Zuweisung nicht gefunden.")
    if zeile.initial_datum is not None or zeile.aktuell_datum is not None:
        raise HTTPException(
            status_code=409,
            detail="Zeile enthält Schulungsnachweise und wird nicht gelöscht.",
        )
    await db.delete(zeile)
    await db.commit()


def _teilnahme_durchgefuehrt(
    zeile: SchulungTeilnahme, monate: int | None, datum: date | None
) -> None:
    """Durchführungsdatum einer Teilnahme setzen/löschen und Fälligkeit nachziehen."""
    if datum is None:
        zeile.aktuell_datum = None
        zeile.naechste_faellig_am = None
        return
    zeile.aktuell_datum = datum
    if zeile.initial_datum is None:
        zeile.initial_datum = datum
    zeile.naechste_faellig_am = _faellig_am(datum, monate)


class DurchgefuehrtSetzen(BaseModel):
    #: Durchführungsdatum; None setzt die Zeile auf "offen" zurück.
    datum: date | None = None


@router.put("/teilnahme/{teilnahme_id}/durchgefuehrt", status_code=204)
async def teilnahme_durchgefuehrt(
    teilnahme_id: int,
    eingabe: DurchgefuehrtSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine einzelne Teilnahme als durchgeführt eintragen (setzt das Datum)."""
    zeile = (
        await db.execute(
            select(SchulungTeilnahme).where(SchulungTeilnahme.id == teilnahme_id)
        )
    ).scalar_one_or_none()
    if zeile is None:
        raise HTTPException(status_code=404, detail="Teilnahme nicht gefunden.")
    katalog = (
        await db.execute(
            select(SchulungKatalog).where(SchulungKatalog.id == zeile.schulung_id)
        )
    ).scalar_one_or_none()
    _teilnahme_durchgefuehrt(
        zeile, katalog.turnus_monate if katalog else None, eingabe.datum
    )
    await db.commit()
    # Personio-Rückschreiben (inert bis Freischaltung) — fire-and-forget.
    asyncio.create_task(personio_writeback.nach_schulung_update(zeile.employee_id))


@router.delete("/teilnahme/{teilnahme_id}", status_code=204)
async def teilnahme_entfernen(
    teilnahme_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Teilnahme entfernen — Korrektur aus der Gesamtübersicht.

    Anders als ``/zuweisung`` (das Nachweise schützt): löscht bewusst auch
    absolvierte Zeilen, damit eine beim FALSCHEN Mitarbeiter bestätigte Schulung
    korrigiert werden kann. Die Oberfläche fragt vorher nach.
    """
    zeile = (
        await db.execute(
            select(SchulungTeilnahme).where(SchulungTeilnahme.id == teilnahme_id)
        )
    ).scalar_one_or_none()
    if zeile is None:
        raise HTTPException(status_code=404, detail="Teilnahme nicht gefunden.")
    await db.delete(zeile)
    await db.commit()


class SammelDurchgefuehrt(BaseModel):
    schulung_id: int
    datum: date
    #: Personio-IDs der Teilnehmer.
    employee_ids: list[int]


@router.post("/durchgefuehrt", status_code=200)
async def sammel_durchgefuehrt(
    eingabe: SammelDurchgefuehrt,
    db: AsyncSession = Depends(get_async_db_session),
) -> dict:
    """Eine Schulung für mehrere Mitarbeiter zum selben Datum als durchgeführt eintragen.

    Legt fehlende Teilnahmen an und setzt das Durchführungsdatum; passt zum
    Formblatt-68-Ablauf (ein Termin, mehrere Teilnehmer).
    """
    katalog = (
        await db.execute(
            select(SchulungKatalog).where(SchulungKatalog.id == eingabe.schulung_id)
        )
    ).scalar_one_or_none()
    if katalog is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")

    eingetragen = 0
    for eid in dict.fromkeys(eingabe.employee_ids):  # Duplikate ignorieren
        ident = await _teilnahme_ident(db, eid)
        if ident is None:
            continue
        name, felder, bedingungen = ident
        zeile = (
            await db.execute(
                select(SchulungTeilnahme).where(
                    SchulungTeilnahme.schulung_id == katalog.id, or_(*bedingungen)
                )
            )
        ).scalars().first()
        if zeile is None:
            zeile = SchulungTeilnahme(
                schulung_id=katalog.id, mitarbeiter_name=name, **felder
            )
            db.add(zeile)
        _teilnahme_durchgefuehrt(zeile, katalog.turnus_monate, eingabe.datum)
        eingetragen += 1

    await db.commit()
    # Personio-Rückschreiben (inert bis Freischaltung) — je Personio-Mitarbeiter.
    for eid in dict.fromkeys(eingabe.employee_ids):
        asyncio.create_task(personio_writeback.nach_schulung_update(eid))
    return {"eingetragen": eingetragen}


class OffeneSchulungRead(BaseModel):
    """Eine offene Fälligkeit — überfällig oder in den nächsten 3 Monaten."""

    #: Stabiler Schlüssel je Mitarbeiter ("p:<persnr>" / "e:<id>") für Frontend-Keys.
    schluessel: str
    #: NULL, wenn die Person nur über Personio (ohne DATEV-Nr.) geführt wird.
    personalnummer: str | None
    mitarbeiter_name: str
    abteilung: str | None
    abteilung_kuerzel: str | None
    bereich: str
    schulung: str
    turnus: str | None
    aktuell_datum: date | None
    faellig_am: date
    #: Negativ = überfällig seit n Tagen, positiv = fällig in n Tagen.
    tage: int
    status: str


@router.get("/offen", response_model=list[OffeneSchulungRead])
async def offene_schulungen(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[OffeneSchulungRead]:
    """Alle Schulungen, die überfällig sind oder in den nächsten 3 Monaten fällig werden.

    Ohne berechenbare Frist ("bei Bedarf", Turnus-Spannen) taucht nichts auf —
    dort gibt es kein Datum, an dem etwas fällig wäre.
    """
    heute = date.today()
    grenze = heute + timedelta(days=BALD_FAELLIG_TAGE)

    # Kein SQL-Filter auf naechste_faellig_am mehr: die Fälligkeit einer noch
    # offenen Schulung ergibt sich erst aus Eintritt + Frist (in Python).
    zeilen = (
        await db.execute(
            select(SchulungTeilnahme, SchulungKatalog).join(
                SchulungKatalog, SchulungKatalog.id == SchulungTeilnahme.schulung_id
            )
        )
    ).all()

    mitarbeiter = {
        e.id: e for e in (await db.execute(select(PersonioEmployee))).scalars().all()
    }
    externe = {
        x.id: x for x in (await db.execute(select(OnboardingExtern))).scalars().all()
    }

    ergebnis: list[OffeneSchulungRead] = []
    for t, k in zeilen:
        emp = mitarbeiter.get(t.employee_id or -1)
        ext = externe.get(t.extern_id) if t.extern_id else None
        # Roster-Regel wie Stand/Zuweisen: nur aktive/eintretende Personio-
        # Mitarbeiter oder Externe. Ausgetretene (``inactive``) und nicht mehr
        # auffindbare Personen erscheinen nicht in der offenen Liste.
        if ext is None and (emp is None or emp.status not in ("active", "onboarding")):
            continue
        abteilung = emp.department if emp else (ext.abteilung if ext else None)
        hire_date = emp.hire_date if emp else (ext.hire_date if ext else None)
        faellig = _effektive_faelligkeit(t, k.frist_tage, hire_date)
        # Nur was eine berechenbare Frist hat und im Fenster (überfällig / ≤ 3 Mon.) liegt.
        if faellig is None or faellig > grenze:
            continue
        ergebnis.append(
            OffeneSchulungRead(
                schluessel=_schluessel(t) or f"t:{t.id}",
                personalnummer=t.personalnummer,
                mitarbeiter_name=t.mitarbeiter_name
                or f"#{t.personalnummer or t.employee_id}",
                abteilung=abteilung,
                abteilung_kuerzel=t.abteilung_kuerzel,
                bereich=k.bereich,
                schulung=k.name,
                turnus=k.turnus,
                aktuell_datum=t.aktuell_datum,
                faellig_am=faellig,
                tage=(faellig - heute).days,
                status=_status(faellig, heute),
            )
        )
    # Dringendstes zuerst.
    return sorted(ergebnis, key=lambda o: (o.faellig_am, o.mitarbeiter_name.lower()))


@router.get("/mitarbeiter", response_model=list[MitarbeiterRead])
async def liste_mitarbeiter(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[MitarbeiterRead]:
    """Stand je Mitarbeiter: Anzahl Schulungen und Fälligkeiten.

    Die Belegschaft kommt aus **einer** Quelle — Personio (``active`` +
    ``onboarding``) plus manuell gepflegte Externe, identisch zur Zuweis-Auswahl
    (:func:`zuweisbare_mitarbeiter`). So erscheinen *alle* aktuellen Mitarbeiter,
    nicht nur die mit bereits zugewiesener Schulung; Ausgetretene fallen weg. Die
    Fälligkeiten werden danach aus dem Teilnahme-Bestand angeheftet (0 Schulungen,
    solange nichts zugewiesen ist).
    """
    heute = date.today()

    # Teilnahme-Bestand einmal laden und nach den drei Schlüsselarten indizieren;
    # die Schlüsselwahl unten spiegelt _schluessel/_schluessel_filter, damit Liste
    # und Detail (/mitarbeiter/{schluessel}) exakt denselben Bestand zählen.
    zeilen = (
        await db.execute(
            select(SchulungTeilnahme, SchulungKatalog).join(
                SchulungKatalog, SchulungKatalog.id == SchulungTeilnahme.schulung_id
            )
        )
    ).all()
    nach_emp: dict[int, list] = {}
    nach_persnr: dict[str, list] = {}
    nach_extern: dict[int, list] = {}
    for t, k in zeilen:
        if t.employee_id is not None:
            nach_emp.setdefault(t.employee_id, []).append((t, k))
        if t.personalnummer:
            nach_persnr.setdefault(t.personalnummer, []).append((t, k))
        if t.extern_id is not None:
            nach_extern.setdefault(t.extern_id, []).append((t, k))

    def _eintrag(schluessel, employee_id, personalnummer, name, abteilung, office, hire_date, treffer):
        eintrag = MitarbeiterRead(
            schluessel=schluessel,
            employee_id=employee_id,
            personalnummer=personalnummer,
            name=name,
            abteilung=abteilung,
            office=office,
            schulungen=len(treffer),
            ueberfaellig=0,
            bald_faellig=0,
            naechste_faelligkeit=None,
        )
        for t, k in treffer:
            faellig = _effektive_faelligkeit(t, k.frist_tage, hire_date)
            status = _status(faellig, heute)
            if status == "ueberfaellig":
                eintrag.ueberfaellig += 1
            elif status == "bald":
                eintrag.bald_faellig += 1
            if faellig is not None and (
                eintrag.naechste_faelligkeit is None
                or faellig < eintrag.naechste_faelligkeit
            ):
                eintrag.naechste_faelligkeit = faellig
        return eintrag

    ergebnis: list[MitarbeiterRead] = []

    # Personio-Belegschaft (aktive + neu eintretende) — die eine Quelle.
    personen = (
        (
            await db.execute(
                select(PersonioEmployee)
                .where(PersonioEmployee.status.in_(("active", "onboarding")))
                .order_by(PersonioEmployee.last_name, PersonioEmployee.first_name)
            )
        )
        .scalars()
        .all()
    )
    for e in personen:
        persnr = _personalnummer(e.raw_json)
        if persnr:
            schluessel, treffer = f"p:{persnr}", nach_persnr.get(persnr, [])
        else:
            schluessel, treffer = f"e:{e.id}", nach_emp.get(e.id, [])
        name = f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}"
        ergebnis.append(
            _eintrag(schluessel, e.id, persnr, name, e.department,
                     _extract_office(e.raw_json), e.hire_date, treffer)
        )

    # Manuell gepflegte Externe (Schlüssel x:<id>) — kein Personio-Standort.
    externe = (await db.execute(select(OnboardingExtern))).scalars().all()
    for x in externe:
        ergebnis.append(
            _eintrag(f"x:{x.id}", None, None, x.name, x.abteilung, None, x.hire_date,
                     nach_extern.get(x.id, []))
        )

    return sorted(
        ergebnis,
        key=lambda m: (-m.ueberfaellig, -m.bald_faellig, m.name.lower()),
    )


class MatrixSchulung(BaseModel):
    id: int
    name: str
    bereich: str


class MatrixZelle(BaseModel):
    schulung_id: int
    #: Teilnahme-ID für Korrekturen (Datum ändern / entfernen).
    teilnahme_id: int
    #: Durchführungsdatum; None = zugewiesen, noch offen.
    datum: date | None
    #: "ueberfaellig" | "bald" | "ok" | "ohne_frist" (Fälligkeits-Status)
    status: str
    #: True = zugewiesen, noch nicht absolviert.
    offen: bool


class MatrixZeile(BaseModel):
    schluessel: str
    name: str
    abteilung: str | None
    office: str | None
    zellen: list[MatrixZelle]


class MatrixRead(BaseModel):
    """Schulungsmatrix: absolvierte Schulungen (Spalten) je Mitarbeiter (Zeilen)."""

    schulungen: list[MatrixSchulung]
    zeilen: list[MatrixZeile]


@router.get("/matrix", response_model=MatrixRead)
async def schulungs_matrix(
    db: AsyncSession = Depends(get_async_db_session),
) -> MatrixRead:
    """Gesamtübersicht: wer soll welche Schulung — und was ist erledigt.

    Verbindet Zuweisung und Absolvierung: Spalten sind alle zugewiesenen ODER
    absolvierten Schulungen, Zeilen die Mitarbeiter (aktive/onboarding + Externe,
    keine Ausgetretenen). Die Zelle trägt Datum (falls absolviert), den
    Fälligkeits-Status und ob sie noch offen ist.
    """
    heute = date.today()

    # Alle Teilnahmen (offen + absolviert) nach den drei Schlüsselarten indizieren
    # (wie liste_mitarbeiter), damit die Matrix DIESELBE Belegschaft trägt.
    zeilen = (
        await db.execute(
            select(SchulungTeilnahme, SchulungKatalog).join(
                SchulungKatalog, SchulungKatalog.id == SchulungTeilnahme.schulung_id
            )
        )
    ).all()
    nach_emp: dict[int, list] = {}
    nach_persnr: dict[str, list] = {}
    nach_extern: dict[int, list] = {}
    for t, k in zeilen:
        if t.employee_id is not None:
            nach_emp.setdefault(t.employee_id, []).append((t, k))
        if t.personalnummer:
            nach_persnr.setdefault(t.personalnummer, []).append((t, k))
        if t.extern_id is not None:
            nach_extern.setdefault(t.extern_id, []).append((t, k))

    schulungen: dict[int, MatrixSchulung] = {}

    def _zeile(schluessel, name, abteilung, office, hire_date, treffer):
        # Alle Mitarbeiter erscheinen — auch ohne Absolvierung (leere Zeile).
        zellen: list[MatrixZelle] = []
        for t, k in treffer:
            schulungen.setdefault(
                k.id, MatrixSchulung(id=k.id, name=k.name, bereich=k.bereich)
            )
            faellig = _effektive_faelligkeit(t, k.frist_tage, hire_date)
            zellen.append(
                MatrixZelle(
                    schulung_id=k.id,
                    teilnahme_id=t.id,
                    datum=t.aktuell_datum,
                    status=_status(faellig, heute),
                    offen=t.aktuell_datum is None,
                )
            )
        return MatrixZeile(
            schluessel=schluessel, name=name, abteilung=abteilung, office=office, zellen=zellen
        )

    ergebnis: list[MatrixZeile] = []

    personen = (
        (
            await db.execute(
                select(PersonioEmployee)
                .where(PersonioEmployee.status.in_(("active", "onboarding")))
                .order_by(PersonioEmployee.last_name, PersonioEmployee.first_name)
            )
        )
        .scalars()
        .all()
    )
    for e in personen:
        persnr = _personalnummer(e.raw_json)
        if persnr:
            schluessel, treffer = f"p:{persnr}", nach_persnr.get(persnr, [])
        else:
            schluessel, treffer = f"e:{e.id}", nach_emp.get(e.id, [])
        name = f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}"
        ergebnis.append(
            _zeile(
                schluessel, name, e.department, _extract_office(e.raw_json), e.hire_date, treffer
            )
        )

    externe = (await db.execute(select(OnboardingExtern))).scalars().all()
    for x in externe:
        ergebnis.append(
            _zeile(f"x:{x.id}", x.name, x.abteilung, None, x.hire_date, nach_extern.get(x.id, []))
        )

    return MatrixRead(
        schulungen=sorted(
            schulungen.values(), key=lambda s: (s.bereich.lower(), s.name.lower())
        ),
        zeilen=sorted(ergebnis, key=lambda z: z.name.lower()),
    )


@router.get("/mitarbeiter/{schluessel}", response_model=list[MitarbeiterSchulungRead])
async def mitarbeiter_schulungen(
    schluessel: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[MitarbeiterSchulungRead]:
    """Alle Schulungen eines Mitarbeiters (Einzelübersicht).

    ``schluessel`` ist "p:<personalnummer>" oder "e:<employee_id>" — siehe
    :func:`_schluessel`.
    """
    heute = date.today()
    zeilen = (
        await db.execute(
            select(SchulungTeilnahme, SchulungKatalog)
            .join(SchulungKatalog, SchulungKatalog.id == SchulungTeilnahme.schulung_id)
            .where(_schluessel_filter(schluessel))
        )
    ).all()
    if not zeilen:
        raise HTTPException(status_code=404, detail="Keine Schulungen zu diesem Mitarbeiter.")

    # Eintrittsdatum der Person (für die Frist-basierte Fälligkeit offener Schulungen).
    erste = zeilen[0][0]
    hire_date = None
    if erste.employee_id is not None:
        emp = (
            await db.execute(
                select(PersonioEmployee).where(PersonioEmployee.id == erste.employee_id)
            )
        ).scalar_one_or_none()
        hire_date = emp.hire_date if emp else None
    elif erste.extern_id is not None:
        ext = await db.get(OnboardingExtern, erste.extern_id)
        hire_date = ext.hire_date if ext else None

    ergebnis = []
    for t, k in zeilen:
        faellig = _effektive_faelligkeit(t, k.frist_tage, hire_date)
        ergebnis.append(
            MitarbeiterSchulungRead(
                teilnahme_id=t.id,
                schulung_id=k.id,
                bereich=k.bereich,
                name=k.name,
                turnus=k.turnus,
                initial_datum=t.initial_datum,
                aktuell_datum=t.aktuell_datum,
                naechste_faellig=t.naechste_faellig,
                naechste_faellig_am=faellig,
                status=_status(faellig, heute),
            )
        )
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
        ergebnis.append(
            AbteilungRead(
                abteilung=abteilung,
                mitarbeiter=anzahl,
                vorgesetzte=[namen.get(sid, f"#{sid}") for sid, _ in kandidaten],
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
    # Unterlagen je normalisiertem Namen (über Bereiche geteilt).
    unterlagen: dict[str, int] = {}
    for (nm,) in (await db.execute(select(SchulungUnterlage.name_norm))).all():
        unterlagen[nm] = unterlagen.get(nm, 0) + 1
    return [
        SchulungRead(
            id=k.id,
            bereich=k.bereich,
            name=k.name,
            turnus=k.turnus,
            turnus_monate=k.turnus_monate,
            frist_tage=k.frist_tage,
            verantwortlicher=k.verantwortlicher,
            beschreibung=k.beschreibung,
            anzahl_unterlagen=unterlagen.get(_name_norm(k.name), 0),
            aktiv=k.aktiv,
            teilnahmen=zaehler.get(k.id, 0),
        )
        for k in katalog
    ]


class SchulungAnlegen(BaseModel):
    name: str
    bereich: str


@router.post("", response_model=SchulungRead, status_code=201)
async def schulung_anlegen(
    eingabe: SchulungAnlegen,
    db: AsyncSession = Depends(get_async_db_session),
) -> SchulungRead:
    """Eine neue Schulung im Katalog anlegen (Name + Bereich; Rest später pflegbar)."""
    name = eingabe.name.strip()
    bereich = eingabe.bereich.strip()
    if not name or not bereich:
        raise HTTPException(status_code=422, detail="Name und Bereich sind erforderlich.")
    # Dubletten (gleicher Name, egal welcher Bereich) verhindern — passt zur
    # deduplizierten Katalogansicht.
    vorhanden = (
        await db.execute(
            select(SchulungKatalog).where(func.lower(SchulungKatalog.name) == name.lower())
        )
    ).scalars().first()
    if vorhanden is not None:
        raise HTTPException(
            status_code=409, detail="Eine Schulung mit diesem Namen existiert bereits."
        )
    k = SchulungKatalog(bereich=bereich, name=name, sort_order=0)
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return SchulungRead(
        id=k.id,
        bereich=k.bereich,
        name=k.name,
        turnus=None,
        turnus_monate=None,
        frist_tage=None,
        verantwortlicher=None,
        beschreibung=None,
        anzahl_unterlagen=0,
        aktiv=k.aktiv,
        teilnahmen=0,
    )


@router.delete("/{schulung_id}", status_code=204)
async def schulung_entfernen(
    schulung_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Schulung entfernen — inkl. aller gleichnamigen Katalogzeilen.

    Entspricht der deduplizierten Ansicht (eine Schulung = ein Name). Teilnahmen
    (auch Nachweise) und Anforderungsregeln kaskadieren (FK ON DELETE CASCADE) —
    die Oberfläche warnt vorher, wenn Teilnahmen betroffen sind.
    """
    k = (
        await db.execute(select(SchulungKatalog).where(SchulungKatalog.id == schulung_id))
    ).scalar_one_or_none()
    if k is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")
    gleichnamig = (
        await db.execute(
            select(SchulungKatalog).where(func.lower(SchulungKatalog.name) == k.name.lower())
        )
    ).scalars().all()
    for eintrag in gleichnamig:
        await db.delete(eintrag)
    await db.commit()


class FristSetzen(BaseModel):
    #: Tage nach Eintritt/Zuweisung; None löscht die Frist.
    frist_tage: int | None = None


@router.put("/{schulung_id}/frist", status_code=204)
async def frist_setzen(
    schulung_id: int,
    eingabe: FristSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Frist (Tage nach Eintritt/Zuweisung) einer Schulung setzen oder löschen.

    Wird je Schulungs-Name geteilt: gilt auf allen gleichnamigen Schulungen.
    """
    if eingabe.frist_tage is not None and not 0 <= eingabe.frist_tage <= 3650:
        raise HTTPException(status_code=400, detail="Frist muss 0-3650 Tage sein.")
    k = (
        await db.execute(select(SchulungKatalog).where(SchulungKatalog.id == schulung_id))
    ).scalar_one_or_none()
    if k is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")
    await sync_frist_nach_name(db, k.name, eingabe.frist_tage)
    await db.commit()


class VerantwortlicherSetzen(BaseModel):
    #: Name; None/leer löscht die Zuordnung.
    verantwortlicher: str | None = None


@router.put("/{schulung_id}/verantwortlicher", status_code=204)
async def verantwortlicher_setzen(
    schulung_id: int,
    eingabe: VerantwortlicherSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Verantwortlichen/Trainer einer Schulung setzen oder löschen.

    Wird je Schulungs-Name geteilt: derselbe Verantwortliche erscheint auf allen
    gleichnamigen Schulungen (alle Bereiche) und der gleichnamigen Einarbeitung.
    """
    k = (
        await db.execute(select(SchulungKatalog).where(SchulungKatalog.id == schulung_id))
    ).scalar_one_or_none()
    if k is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")
    person = (eingabe.verantwortlicher or "").strip() or None
    await sync_person_nach_name(db, k.name, person)
    await db.commit()


class TurnusSetzen(BaseModel):
    #: Wiederholungs-Turnus in Monaten; None = bei Bedarf / kein fester Turnus.
    turnus_monate: int | None = None


def _turnus_label(monate: int | None) -> str | None:
    """Anzeigetext zu einem Monats-Turnus (treibt zusätzlich die Suche/Anzeige)."""
    if monate is None:
        return "bei Bedarf"
    fest = {
        3: "vierteljährlich",
        6: "halbjährlich",
        12: "jährlich",
        24: "alle 2 Jahre",
        36: "alle 3 Jahre",
        60: "alle 5 Jahre",
    }
    if monate in fest:
        return fest[monate]
    if monate % 12 == 0:
        return f"alle {monate // 12} Jahre"
    return f"alle {monate} Monate"


@router.put("/{schulung_id}/turnus", status_code=204)
async def turnus_setzen(
    schulung_id: int,
    eingabe: TurnusSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Wiederholungs-Turnus einer Schulung setzen (Monate) — treibt die Fälligkeit.

    Der Anzeigetext ``turnus`` wird passend abgeleitet; ``None`` = bei Bedarf. Wird
    je Schulungs-Name geteilt: gilt auf allen gleichnamigen Schulungen.
    """
    if eingabe.turnus_monate is not None and not 1 <= eingabe.turnus_monate <= 600:
        raise HTTPException(status_code=400, detail="Turnus muss 1-600 Monate sein.")
    k = (
        await db.execute(select(SchulungKatalog).where(SchulungKatalog.id == schulung_id))
    ).scalar_one_or_none()
    if k is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")
    await sync_turnus_nach_name(
        db, k.name, _turnus_label(eingabe.turnus_monate), eingabe.turnus_monate
    )
    await db.commit()


class BeschreibungSetzen(BaseModel):
    #: Freitext; None/leer löscht die Beschreibung.
    beschreibung: str | None = None


@router.put("/{schulung_id}/beschreibung", status_code=204)
async def beschreibung_setzen(
    schulung_id: int,
    eingabe: BeschreibungSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Beschreibung einer Schulung setzen — je Name geteilt (alle Bereiche)."""
    k = (
        await db.execute(select(SchulungKatalog).where(SchulungKatalog.id == schulung_id))
    ).scalar_one_or_none()
    if k is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")
    text = (eingabe.beschreibung or "").strip() or None
    await sync_beschreibung_nach_name(db, k.name, text)
    await db.commit()


class UnterlageRead(BaseModel):
    id: int
    dateiname: str
    mime: str | None


async def _schulung_name(db: AsyncSession, schulung_id: int) -> str:
    name = (
        await db.execute(select(SchulungKatalog.name).where(SchulungKatalog.id == schulung_id))
    ).scalar_one_or_none()
    if name is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")
    return name


@router.get("/{schulung_id}/unterlagen", response_model=list[UnterlageRead])
async def unterlagen_liste(
    schulung_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[UnterlageRead]:
    """Unterlagen einer Schulung (über alle gleichnamigen geteilt)."""
    name = await _schulung_name(db, schulung_id)
    rows = (
        (
            await db.execute(
                select(SchulungUnterlage)
                .where(SchulungUnterlage.name_norm == _name_norm(name))
                .order_by(SchulungUnterlage.hochgeladen_am)
            )
        )
        .scalars()
        .all()
    )
    return [UnterlageRead(id=u.id, dateiname=u.dateiname, mime=u.mime) for u in rows]


@router.post("/{schulung_id}/unterlagen", response_model=UnterlageRead, status_code=201)
async def unterlage_hochladen(
    schulung_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> UnterlageRead:
    """Eine Unterlage zu einer Schulung hochladen (Directus); je Name geteilt."""
    name = await _schulung_name(db, schulung_id)
    dateiname = file.filename or ""
    ext = _unterlage_ext(dateiname)
    if ext not in _UNTERLAGE_TYPEN:
        raise HTTPException(
            status_code=422,
            detail="Dateityp nicht erlaubt (PDF, Bild, Office oder Text).",
        )
    mime = _UNTERLAGE_TYPEN[ext]

    async def _iter():
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    directus_uuid, _ = await upload_maintenance_file_to_directus(
        filename=dateiname or f"unterlage{ext}", content_type=mime, body_stream=_iter()
    )
    u = SchulungUnterlage(
        name_norm=_name_norm(name),
        directus_file_uuid=directus_uuid,
        dateiname=dateiname or f"unterlage{ext}",
        mime=mime,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return UnterlageRead(id=u.id, dateiname=u.dateiname, mime=u.mime)


@router.get("/unterlage/{unterlage_id}/download")
async def unterlage_download(
    unterlage_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Die gespeicherten Bytes aus Directus an den Client durchreichen."""
    u = await db.get(SchulungUnterlage, unterlage_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Unterlage nicht gefunden.")
    content, content_type = await fetch_directus_asset(u.directus_file_uuid)
    return Response(
        content=content,
        media_type=u.mime or content_type,
        headers={
            "Content-Disposition": f'inline; filename="{_sicherer_dateiname(u.dateiname)}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete("/unterlage/{unterlage_id}", status_code=204)
async def unterlage_entfernen(
    unterlage_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    u = await db.get(SchulungUnterlage, unterlage_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Unterlage nicht gefunden.")
    await db.delete(u)
    await db.commit()


@router.get("/{schulung_id}/protokoll/pdf")
async def schulungsprotokoll_pdf(
    schulung_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    """Schulungsnachweis (Formblatt 68) für eine Schulung als PDF.

    Titel kommt aus dem Katalog; Datum, Trainer, Teilnehmer bleiben leer und
    werden bei der Schulung von Hand ausgefüllt (Unterschriften).

    Compute-justified: clause 2 (document generation) — openpyxl-Aufbau plus
    LibreOffice-Konvertierung laufen serverseitig.
    """
    k = (
        await db.execute(select(SchulungKatalog).where(SchulungKatalog.id == schulung_id))
    ).scalar_one_or_none()
    if k is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")

    titel = f"{k.bereich}: {k.name}" if k.bereich else k.name
    pdf = await erzeuge_schulungsprotokoll_pdf(
        titel=titel, trainer=k.verantwortlicher or "", logo=await lade_logo(db)
    )
    name = protokoll_dateiname(k.name, date.today())
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


# --------------------------------------------------------------------------
# Schulungsvorgang: persistiertes Formblatt 71 mit QR, Lebenszyklus, Scan-
# Prüfung + je Schulungszeile zugeordneten Zertifikaten (v1.121). Prüfung und
# Datei-Ablage teilen sich die Services mit dem Einarbeitungsvorgang.
# --------------------------------------------------------------------------


class SchulungZertifikatRead(BaseModel):
    id: int
    schulung_bezeichnung: str | None
    dateiname: str
    hochgeladen_am: datetime


class SchulungVorgangRead(BaseModel):
    id: int
    #: Diskriminator für die gemeinsame Vorgangs-Liste im Frontend.
    typ: str = "schulung"
    doc_uid: str
    employee_id: int | None
    mitarbeiter_name: str
    funktion: str | None
    status: str
    erstellt_am: datetime
    uebergeben_am: datetime | None
    zurueck_am: datetime | None
    geprueft_am: datetime | None
    vollstaendig: bool | None
    kommentar: str | None
    hat_scan: bool
    pruef_ergebnis: dict | None
    #: Schulungen des Vorgangs (Namen) — für das Zuordnungs-Dropdown + Fbl.-68-Download.
    schulungen: list[str]
    zertifikate: list[SchulungZertifikatRead]


class SchulungVorgangAnlegen(BaseModel):
    employee_id: int


class SchulungStatusSetzen(BaseModel):
    status: str


class SchulungVorgangAktualisieren(BaseModel):
    kommentar: str | None = None
    vollstaendig: bool | None = None
    bestaetigte_felder: list[str] | None = None


_SCHULUNG_STATUS_FELD = {
    "uebergeben": "uebergeben_am",
    "zurueck": "zurueck_am",
    "geprueft": "geprueft_am",
}


def _zertifikat_read(z: SchulungZertifikat) -> SchulungZertifikatRead:
    return SchulungZertifikatRead(
        id=z.id,
        schulung_bezeichnung=z.schulung_bezeichnung,
        dateiname=z.dateiname,
        hochgeladen_am=z.hochgeladen_am,
    )


def _schulung_vorgang_read(
    d: SchulungDokument, zertifikate: list[SchulungZertifikat]
) -> SchulungVorgangRead:
    return SchulungVorgangRead(
        id=d.id,
        doc_uid=d.doc_uid,
        employee_id=d.employee_id,
        mitarbeiter_name=d.mitarbeiter_name,
        funktion=d.funktion,
        status=d.status,
        erstellt_am=d.erstellt_am,
        uebergeben_am=d.uebergeben_am,
        zurueck_am=d.zurueck_am,
        geprueft_am=d.geprueft_am,
        vollstaendig=d.vollstaendig,
        kommentar=d.kommentar,
        hat_scan=d.scan_uuid is not None,
        pruef_ergebnis=d.pruef_ergebnis,
        schulungen=[s.get("name", "") for s in (d.schulungen or [])],
        zertifikate=[_zertifikat_read(z) for z in zertifikate],
    )


async def _hole_schulung_vorgang(db: AsyncSession, dok_id: int) -> SchulungDokument:
    d = (
        await db.execute(select(SchulungDokument).where(SchulungDokument.id == dok_id))
    ).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="Schulungsvorgang nicht gefunden.")
    return d


async def _zertifikate_von(db: AsyncSession, dok_id: int) -> list[SchulungZertifikat]:
    return list(
        (
            await db.execute(
                select(SchulungZertifikat)
                .where(SchulungZertifikat.dokument_id == dok_id)
                .order_by(SchulungZertifikat.hochgeladen_am)
            )
        ).scalars().all()
    )


async def _schulung_read_voll(db: AsyncSession, d: SchulungDokument) -> SchulungVorgangRead:
    return _schulung_vorgang_read(d, await _zertifikate_von(db, d.id))


def _mime_von_bytes(daten: bytes) -> tuple[str, str]:
    if daten[:4] == b"%PDF":
        return "application/pdf", "pdf"
    if daten[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    if daten[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    return "application/octet-stream", "bin"


@router.post("/dokument")
async def schulung_dokument_anlegen(
    eingabe: SchulungVorgangAnlegen, db: AsyncSession = Depends(get_async_db_session)
) -> SchulungVorgangRead:
    """Schulungsvorgang anlegen: Formblatt 71 mit QR aus dem Soll-Schulungsplan."""
    emp = (
        await db.execute(
            select(PersonioEmployee).where(PersonioEmployee.id == eingabe.employee_id)
        )
    ).scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")
    plan = await schulungsplan(db, emp)
    ids = [s.schulung_id for s in plan.soll]
    trainer = (
        dict(
            (
                await db.execute(
                    select(SchulungKatalog.id, SchulungKatalog.verantwortlicher).where(
                        SchulungKatalog.id.in_(ids)
                    )
                )
            ).all()
        )
        if ids
        else {}
    )
    schulungen = [
        {
            "name": f"{s.bereich}: {s.name}" if s.bereich else s.name,
            "trainer": trainer.get(s.schulung_id) or "",
        }
        for s in plan.soll
    ]
    dok = await schulung_vorgang.vorgang_anlegen(
        db,
        employee_id=emp.id,
        name=plan.name,
        funktion=plan.position or "",
        schulungen=schulungen,
        logo=await lade_logo(db),
    )
    return await _schulung_read_voll(db, dok)


@router.get("/dokumente")
async def schulung_dokumente(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[SchulungVorgangRead]:
    rows = (
        await db.execute(
            select(SchulungDokument).order_by(SchulungDokument.erstellt_am.desc())
        )
    ).scalars().all()
    return [await _schulung_read_voll(db, d) for d in rows]


@router.get("/dokument/{dok_id}")
async def schulung_dokument(
    dok_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> SchulungVorgangRead:
    return await _schulung_read_voll(db, await _hole_schulung_vorgang(db, dok_id))


@router.get("/dokument/{dok_id}/pdf")
async def schulung_dokument_pdf(
    dok_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    d = await _hole_schulung_vorgang(db, dok_id)
    if not d.pdf_uuid:
        raise HTTPException(status_code=404, detail="Kein PDF hinterlegt.")
    # Das komplette Bündel (Fbl. 71 + Fbl. 68 je Schulung) wurde beim Anlegen
    # erzeugt und gespeichert — hier nur noch abrufen, keine erneute Generierung.
    pdf = await datei_laden(d.pdf_uuid)
    # Der Download zum Ausdrucken gilt als Übergabe → einmalig datieren.
    if d.uebergeben_am is None:
        d.uebergeben_am = datetime.now(timezone.utc)
        if d.status == "erstellt":
            d.status = "uebergeben"
        await db.commit()
    teil = "_".join(d.mitarbeiter_name.split()) or "Unbekannt"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{teil}_Schulungsuebersicht.pdf"'},
    )


@router.get("/dokument/{dok_id}/nachweis/{index}/pdf")
async def schulung_nachweis_pdf(
    dok_id: int, index: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    """Vorausgefülltes Fbl. 68 (Schulungsnachweis) für eine Schulung des Vorgangs.

    Titel = Schulung, Teilnehmer = Mitarbeiter, Trainer = Verantwortlicher. Der QR
    kodiert ``doc_uid#index`` — der ausgefüllte, eingescannte Nachweis wird darüber
    automatisch dieser Schulung als Zertifikat zugeordnet.
    """
    d = await _hole_schulung_vorgang(db, dok_id)
    schulungen = d.schulungen or []
    if not (0 <= index < len(schulungen)):
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")
    s = schulungen[index]
    pdf = await erzeuge_schulungsprotokoll_pdf(
        titel=s.get("name", ""),
        teilnehmer=[d.mitarbeiter_name],
        trainer=s.get("trainer") or "",
        qr_payload=f"{d.doc_uid}#{index}",
        logo=await lade_logo(db),
    )
    fn = protokoll_dateiname(s.get("name", "Schulung"), date.today())
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fn}.pdf"'},
    )


@router.get("/dokument/{dok_id}/scan")
async def schulung_dokument_scan(
    dok_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    d = await _hole_schulung_vorgang(db, dok_id)
    if not d.scan_uuid:
        raise HTTPException(status_code=404, detail="Kein Scan hinterlegt.")
    daten = await datei_laden(d.scan_uuid)
    mime, ext = _mime_von_bytes(daten)
    return Response(
        content=daten,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="scan_{d.doc_uid}.{ext}"'},
    )


@router.patch("/dokument/{dok_id}/status")
async def schulung_status_setzen(
    dok_id: int,
    eingabe: SchulungStatusSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> SchulungVorgangRead:
    if eingabe.status not in _SCHULUNG_STATUS_FELD:
        raise HTTPException(status_code=400, detail="Unbekannter Status.")
    d = await _hole_schulung_vorgang(db, dok_id)
    setattr(d, _SCHULUNG_STATUS_FELD[eingabe.status], datetime.now(timezone.utc))
    d.status = eingabe.status
    await db.commit()
    await db.refresh(d)
    return await _schulung_read_voll(db, d)


@router.post("/scan")
async def schulung_scan_hochladen(
    datei: UploadFile = File(...), db: AsyncSession = Depends(get_async_db_session)
) -> dict:
    daten = await datei.read()
    ist_pdf = (datei.content_type == "application/pdf") or (
        (datei.filename or "").lower().endswith(".pdf")
    )
    dok, ergebnis = await schulung_vorgang.scan_verarbeiten(db, daten, ist_pdf)
    if dok is None:
        raise HTTPException(status_code=422, detail=ergebnis)
    return {"dokument": await _schulung_read_voll(db, dok), "ergebnis": ergebnis}


@router.patch("/dokument/{dok_id}")
async def schulung_dokument_aktualisieren(
    dok_id: int,
    eingabe: SchulungVorgangAktualisieren,
    db: AsyncSession = Depends(get_async_db_session),
) -> SchulungVorgangRead:
    d = await _hole_schulung_vorgang(db, dok_id)
    if eingabe.kommentar is not None:
        d.kommentar = eingabe.kommentar
    if eingabe.bestaetigte_felder is not None:
        erg = dict(d.pruef_ergebnis or {})
        keys = set(eingabe.bestaetigte_felder)
        felder = [{**f, "bestaetigt": f["key"] in keys} for f in erg.get("felder", [])]
        offen = [f["label"] for f in felder if not (f.get("erkannt") or f.get("bestaetigt"))]
        vollstaendig = bool(felder) and not offen
        erg["felder"] = felder
        erg["fehlend"] = offen
        erg["vollstaendig"] = vollstaendig
        d.pruef_ergebnis = erg
        d.vollstaendig = vollstaendig
    if eingabe.vollstaendig is not None:
        d.vollstaendig = eingabe.vollstaendig
    await db.commit()
    await db.refresh(d)
    return await _schulung_read_voll(db, d)


# ── Zertifikate / Schulungsnachweise (je Schulungszeile) ──────────────────
@router.post("/dokument/{dok_id}/zertifikat")
async def schulung_zertifikat_hochladen(
    dok_id: int,
    datei: UploadFile = File(...),
    schulung_bezeichnung: str | None = Form(default=None),
    db: AsyncSession = Depends(get_async_db_session),
) -> SchulungVorgangRead:
    """Zertifikat/Nachweis hochladen und (optional) einer Schulungszeile zuordnen."""
    d = await _hole_schulung_vorgang(db, dok_id)
    daten = await datei.read()
    _, ext = _mime_von_bytes(daten)
    ref = await datei_speichern(
        datei.filename or f"zertifikat_{d.doc_uid}.{ext}",
        daten,
        datei.content_type or "application/octet-stream",
    )
    db.add(
        SchulungZertifikat(
            dokument_id=d.id,
            schulung_bezeichnung=(schulung_bezeichnung or None),
            datei_uuid=ref,
            dateiname=datei.filename or f"zertifikat.{ext}",
        )
    )
    await db.commit()
    await db.refresh(d)
    return await _schulung_read_voll(db, d)


@router.get("/zertifikat/{zert_id}/datei")
async def schulung_zertifikat_datei(
    zert_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    z = (
        await db.execute(select(SchulungZertifikat).where(SchulungZertifikat.id == zert_id))
    ).scalar_one_or_none()
    if z is None:
        raise HTTPException(status_code=404, detail="Zertifikat nicht gefunden.")
    daten = await datei_laden(z.datei_uuid)
    mime, _ = _mime_von_bytes(daten)
    return Response(
        content=daten,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{z.dateiname}"'},
    )


@router.delete("/zertifikat/{zert_id}")
async def schulung_zertifikat_loeschen(
    zert_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> SchulungVorgangRead:
    z = (
        await db.execute(select(SchulungZertifikat).where(SchulungZertifikat.id == zert_id))
    ).scalar_one_or_none()
    if z is None:
        raise HTTPException(status_code=404, detail="Zertifikat nicht gefunden.")
    dok_id = z.dokument_id
    await db.delete(z)
    await db.commit()
    return await _schulung_read_voll(db, await _hole_schulung_vorgang(db, dok_id))
