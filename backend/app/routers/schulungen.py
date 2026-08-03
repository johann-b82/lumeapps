"""Schulungs-Modul — Import der Schulungsübersicht und Auswertungen.

Der gesamte Router ist admin-gated (Stufe 1 des Moduls ist HR-intern). Sobald
Vorgesetzten- und Trainer-Sichten dazukommen, wird die Gate-Struktur hier
aufgeteilt und im Docstring dokumentiert.

Compute-justified: clause 1 (file parsing) — die Import-Routen lesen eine
hochgeladene .xlsx serverseitig ein; clause 3 (multi-row atomic compute) — die
Übernahme schreibt Katalog und Teilnahmen in einer Transaktion.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import (
    PersonioEmployee,
    SchulungKatalog,
    SchulungPflicht,
    SchulungTeilnahme,
    SchulungUnterlage,
)
from app.models.schulung import PFLICHT_EBENEN
from app.parsing.schulung_parser import parse_schulungsuebersicht
# Bewusst wiederverwendet statt dupliziert: der JSON-Pfad zum Vorgesetzten in
# den Personio-Rohdaten soll nur an einer Stelle gepflegt werden.
from app.routers.hr_kpis import _extract_supervisor_id
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
    _personalnummer,
    baue_vorschau,
    uebernehmen,
)

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
    return None


def _schluessel_filter(schluessel: str):
    """Übersetzt einen Schlüssel in die passende WHERE-Bedingung."""
    art, _, wert = schluessel.partition(":")
    if art == "p" and wert:
        return SchulungTeilnahme.personalnummer == wert
    if art == "e" and wert.isdigit():
        return SchulungTeilnahme.employee_id == int(wert)
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
    """Aktive Mitarbeiter für die Einzelzuweisung.

    Quelle ist Personio, nicht der Teilnahme-Bestand: zuweisen muss auch für
    jemanden möglich sein, der noch gar keine Schulung hat.
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
    return [
        ZuweisbarerMitarbeiterRead(
            employee_id=e.id,
            personalnummer=_personalnummer(e.raw_json),
            name=f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}",
            abteilung=e.department,
        )
        for e in aktive
    ]


@router.post("/zuweisen", response_model=ZuweisungRead, status_code=201)
async def schulung_zuweisen(
    eingabe: ZuweisungSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> ZuweisungRead:
    """Eine einzelne Schulung einer einzelnen Person zuweisen.

    Ergänzt die Anforderungsmatrix, die nur abteilungsweit wirkt. Die Zeile
    entsteht ohne Datumsangaben ("offen") — eine Fälligkeit wäre erfunden,
    solange die Schulung nicht stattgefunden hat.
    """
    emp = (
        await db.execute(
            select(PersonioEmployee).where(PersonioEmployee.id == eingabe.employee_id)
        )
    ).scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")

    katalog = (
        await db.execute(
            select(SchulungKatalog).where(SchulungKatalog.id == eingabe.schulung_id)
        )
    ).scalar_one_or_none()
    if katalog is None:
        raise HTTPException(status_code=404, detail="Schulung nicht gefunden.")

    persnr = _personalnummer(emp.raw_json)
    # Doppelzuweisung über beide Identitätsarten prüfen — die partiellen Unique-
    # Indizes aus v1_89 greifen je nur für eine davon.
    bedingungen = [SchulungTeilnahme.employee_id == emp.id]
    if persnr:
        bedingungen.append(SchulungTeilnahme.personalnummer == persnr)
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

    name = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or f"#{emp.id}"
    zeile = SchulungTeilnahme(
        schulung_id=katalog.id,
        employee_id=emp.id,
        personalnummer=persnr,
        mitarbeiter_name=name,
    )
    db.add(zeile)
    await db.commit()
    await db.refresh(zeile)
    return ZuweisungRead(
        teilnahme_id=zeile.id,
        employee_id=emp.id,
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

    ergebnis: list[OffeneSchulungRead] = []
    for t, k in zeilen:
        emp = mitarbeiter.get(t.employee_id or -1)
        faellig = _effektive_faelligkeit(
            t, k.frist_tage, emp.hire_date if emp else None
        )
        # Nur was eine berechenbare Frist hat und im Fenster (überfällig / ≤ 3 Mon.) liegt.
        if faellig is None or faellig > grenze:
            continue
        ergebnis.append(
            OffeneSchulungRead(
                schluessel=_schluessel(t) or f"t:{t.id}",
                personalnummer=t.personalnummer,
                mitarbeiter_name=t.mitarbeiter_name
                or f"#{t.personalnummer or t.employee_id}",
                abteilung=emp.department if emp else None,
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

    # Abteilung + Eintrittsdatum aus Personio, wo zugeordnet.
    mitarbeiter = {
        e.id: e for e in (await db.execute(select(PersonioEmployee))).scalars().all()
    }

    gruppen: dict[str, MitarbeiterRead] = {}
    for teilnahme, katalog in zeilen:
        schluessel = _schluessel(teilnahme)
        if schluessel is None:
            continue  # weder Personalnummer noch Personio-Zuordnung — nicht adressierbar
        emp = mitarbeiter.get(teilnahme.employee_id or -1)
        eintrag = gruppen.get(schluessel)
        if eintrag is None:
            eintrag = MitarbeiterRead(
                schluessel=schluessel,
                employee_id=teilnahme.employee_id,
                personalnummer=teilnahme.personalnummer,
                name=teilnahme.mitarbeiter_name
                or f"#{teilnahme.personalnummer or teilnahme.employee_id}",
                abteilung=emp.department if emp else None,
                schulungen=0,
                ueberfaellig=0,
                bald_faellig=0,
                naechste_faelligkeit=None,
            )
            gruppen[schluessel] = eintrag

        eintrag.schulungen += 1
        faellig = _effektive_faelligkeit(
            teilnahme, katalog.frist_tage, emp.hire_date if emp else None
        )
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

    return sorted(
        gruppen.values(),
        key=lambda m: (-m.ueberfaellig, -m.bald_faellig, m.name.lower()),
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
    emp_id = zeilen[0][0].employee_id
    hire_date = None
    if emp_id is not None:
        emp = (
            await db.execute(
                select(PersonioEmployee).where(PersonioEmployee.id == emp_id)
            )
        ).scalar_one_or_none()
        hire_date = emp.hire_date if emp else None

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
