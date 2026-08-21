"""Arbeitszeugnisse — Stammdaten, Bewertung, KI-Text und DOCX/PDF (v1.110).

Komplett admin-gated (HR-intern, personenbezogene Leistungsdaten). Personen
kommen aus Personio bzw. der Externe-Liste (Regel „Personen immer aus Personio")
— hier ohne Status-Filter, weil Zeugnisse häufig für Ausgetretene entstehen.

Compute-justified: clause 2 (document generation) — /docx und /pdf bauen das
Zeugnis serverseitig auf und konvertieren es über LibreOffice.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_db_session
from app.models import OnboardingExtern, PersonioEmployee, Zeugnis, ZeugnisAussteller, ZeugnisBewertung
from app.models.zeugnis import ZEUGNIS_ABSCHNITTE, ZEUGNIS_ARTEN, ZEUGNIS_DIMENSIONEN
from app.security.directus_auth import get_current_user, require_admin
from app.services.pdf_logo import lade_logo
from app.services.zeugnis_dokument import build_zeugnis_docx, convert_docx_to_pdf
from app.services.zeugnis_ki import ZeugnisKIError, generiere_abschnitte

router = APIRouter(
    prefix="/api/hr/zeugnisse",
    tags=["zeugnisse"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class PersonRead(BaseModel):
    #: Positiv = Personio-``employee_id``; negativ = ``-onboarding_extern.id``.
    employee_id: int
    name: str
    abteilung: str | None = None
    position: str | None = None
    status: str | None = None


class ZeugnisListRead(BaseModel):
    id: int
    name: str
    taetigkeit: str | None
    art: str
    status: str
    schlussnote: float | None
    aktualisiert_am: datetime


class ZeugnisRead(BaseModel):
    id: int
    employee_id: int | None
    extern_id: int | None
    name: str
    geschlecht: str | None
    geburtsdatum: date | None
    personalnummer: str | None
    abteilung: str | None
    taetigkeit: str | None
    eintritt: date | None
    austritt: date | None
    art: str
    anlass: str | None
    fuehrungskraft: bool
    ausstellungsdatum: date | None
    taetigkeit_stichpunkte: str | None
    besondere_kompetenzen: str | None
    besondere_erfolge: str | None
    schlussnote: float | None
    bewertungen: dict[str, int]
    abschnitte: dict[str, str] | None
    status: str


class ZeugnisCreate(BaseModel):
    #: Positiv = Personio; negativ = -onboarding_extern.id.
    employee_id: int
    art: str = "qualifiziert"


class ZeugnisUpdate(BaseModel):
    name: str | None = None
    geschlecht: str | None = None
    geburtsdatum: date | None = None
    personalnummer: str | None = None
    abteilung: str | None = None
    taetigkeit: str | None = None
    eintritt: date | None = None
    austritt: date | None = None
    art: str | None = None
    anlass: str | None = None
    fuehrungskraft: bool | None = None
    ausstellungsdatum: date | None = None
    taetigkeit_stichpunkte: str | None = None
    besondere_kompetenzen: str | None = None
    besondere_erfolge: str | None = None
    status: str | None = None
    #: Note je Dimension (1–4); ersetzt die gesetzten Dimensionen.
    bewertungen: dict[str, int] | None = None
    #: Editierte Abschnitte (überschreibt den generierten Text).
    abschnitte: dict[str, str] | None = None


class AusstellerRead(BaseModel):
    firma: str
    standort: str | None
    unterzeichner1_name: str | None
    unterzeichner1_titel: str | None
    unterzeichner2_name: str | None
    unterzeichner2_titel: str | None


class AusstellerUpdate(BaseModel):
    firma: str
    standort: str | None = None
    unterzeichner1_name: str | None = None
    unterzeichner1_titel: str | None = None
    unterzeichner2_name: str | None = None
    unterzeichner2_titel: str | None = None


# --------------------------------------------------------------------------
# Hilfen
# --------------------------------------------------------------------------


def _noten(z: Zeugnis) -> dict[str, int]:
    return {b.dimension: b.note for b in z.bewertungen}


def _schnitt(noten: dict[str, int]) -> Decimal | None:
    werte = [n for n in noten.values() if n]
    if not werte:
        return None
    schnitt = Decimal(sum(werte)) / Decimal(len(werte))
    return schnitt.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _read(z: Zeugnis) -> ZeugnisRead:
    return ZeugnisRead(
        id=z.id,
        employee_id=z.employee_id,
        extern_id=z.extern_id,
        name=z.name,
        geschlecht=z.geschlecht,
        geburtsdatum=z.geburtsdatum,
        personalnummer=z.personalnummer,
        abteilung=z.abteilung,
        taetigkeit=z.taetigkeit,
        eintritt=z.eintritt,
        austritt=z.austritt,
        art=z.art,
        anlass=z.anlass,
        fuehrungskraft=z.fuehrungskraft,
        ausstellungsdatum=z.ausstellungsdatum,
        taetigkeit_stichpunkte=z.taetigkeit_stichpunkte,
        besondere_kompetenzen=z.besondere_kompetenzen,
        besondere_erfolge=z.besondere_erfolge,
        schlussnote=float(z.schlussnote) if z.schlussnote is not None else None,
        bewertungen=_noten(z),
        abschnitte=z.abschnitte_json,
        status=z.status,
    )


def _anrede(geschlecht: str | None) -> str:
    return {"w": "Frau", "m": "Herr"}.get((geschlecht or "").lower(), "Herr/Frau")


def _name_ersetzen(abschnitte: dict[str, str], z: Zeugnis) -> dict[str, str]:
    """Platzhalter [NAME] durch „Anrede Nachname" ersetzen (nach der KI)."""
    nachname = (z.name or "").split()[-1] if (z.name or "").strip() else ""
    ersatz = f"{_anrede(z.geschlecht)} {nachname}".strip()
    return {k: (v or "").replace("[NAME]", ersatz) for k, v in abschnitte.items()}


async def _hole(db: AsyncSession, zeugnis_id: int) -> Zeugnis:
    z = (
        await db.execute(
            select(Zeugnis)
            .where(Zeugnis.id == zeugnis_id)
            .options(selectinload(Zeugnis.bewertungen))
        )
    ).scalar_one_or_none()
    if z is None:
        raise HTTPException(status_code=404, detail="Zeugnis nicht gefunden.")
    return z


async def _aussteller(db: AsyncSession) -> ZeugnisAussteller | None:
    return (
        await db.execute(select(ZeugnisAussteller).order_by(ZeugnisAussteller.id).limit(1))
    ).scalar_one_or_none()


# --------------------------------------------------------------------------
# Personen (Personio + Externe)
# --------------------------------------------------------------------------


@router.get("/personen", response_model=list[PersonRead])
async def personen(db: AsyncSession = Depends(get_async_db_session)) -> list[PersonRead]:
    """Alle Personio-Mitarbeiter (inkl. Ausgetretene — Zeugnisse sind oft für
    Leaver) plus Externe (negative ID)."""
    mitarbeiter = (
        (
            await db.execute(
                select(PersonioEmployee).order_by(
                    PersonioEmployee.last_name, PersonioEmployee.first_name
                )
            )
        )
        .scalars()
        .all()
    )
    ergebnis = [
        PersonRead(
            employee_id=e.id,
            name=f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}",
            abteilung=e.department,
            position=e.position,
            status=e.status,
        )
        for e in mitarbeiter
    ]
    externe = (
        (await db.execute(select(OnboardingExtern).order_by(OnboardingExtern.name)))
        .scalars()
        .all()
    )
    ergebnis.extend(
        PersonRead(
            employee_id=-x.id,
            name=x.name,
            abteilung=x.abteilung,
            position=x.position,
            status="extern",
        )
        for x in externe
    )
    return ergebnis


# --------------------------------------------------------------------------
# Aussteller-Profil
# --------------------------------------------------------------------------


@router.get("/aussteller", response_model=AusstellerRead | None)
async def aussteller_lesen(db: AsyncSession = Depends(get_async_db_session)):
    a = await _aussteller(db)
    if a is None:
        return None
    return AusstellerRead(
        firma=a.firma,
        standort=a.standort,
        unterzeichner1_name=a.unterzeichner1_name,
        unterzeichner1_titel=a.unterzeichner1_titel,
        unterzeichner2_name=a.unterzeichner2_name,
        unterzeichner2_titel=a.unterzeichner2_titel,
    )


@router.put("/aussteller", response_model=AusstellerRead)
async def aussteller_speichern(
    eingabe: AusstellerUpdate, db: AsyncSession = Depends(get_async_db_session)
):
    a = await _aussteller(db)
    if a is None:
        a = ZeugnisAussteller(firma=eingabe.firma, aktualisiert_am=_jetzt())
        db.add(a)
    a.firma = eingabe.firma.strip()
    a.standort = (eingabe.standort or "").strip() or None
    a.unterzeichner1_name = (eingabe.unterzeichner1_name or "").strip() or None
    a.unterzeichner1_titel = (eingabe.unterzeichner1_titel or "").strip() or None
    a.unterzeichner2_name = (eingabe.unterzeichner2_name or "").strip() or None
    a.unterzeichner2_titel = (eingabe.unterzeichner2_titel or "").strip() or None
    a.aktualisiert_am = _jetzt()
    await db.commit()
    await db.refresh(a)
    return AusstellerRead(
        firma=a.firma,
        standort=a.standort,
        unterzeichner1_name=a.unterzeichner1_name,
        unterzeichner1_titel=a.unterzeichner1_titel,
        unterzeichner2_name=a.unterzeichner2_name,
        unterzeichner2_titel=a.unterzeichner2_titel,
    )


# --------------------------------------------------------------------------
# Zeugnis-CRUD
# --------------------------------------------------------------------------


@router.get("", response_model=list[ZeugnisListRead])
async def liste(db: AsyncSession = Depends(get_async_db_session)) -> list[ZeugnisListRead]:
    zeugnisse = (
        (await db.execute(select(Zeugnis).order_by(Zeugnis.aktualisiert_am.desc())))
        .scalars()
        .all()
    )
    return [
        ZeugnisListRead(
            id=z.id,
            name=z.name,
            taetigkeit=z.taetigkeit,
            art=z.art,
            status=z.status,
            schlussnote=float(z.schlussnote) if z.schlussnote is not None else None,
            aktualisiert_am=z.aktualisiert_am,
        )
        for z in zeugnisse
    ]


@router.post("", response_model=ZeugnisRead, status_code=201)
async def anlegen(
    eingabe: ZeugnisCreate, db: AsyncSession = Depends(get_async_db_session)
) -> ZeugnisRead:
    if eingabe.art not in ZEUGNIS_ARTEN:
        raise HTTPException(status_code=400, detail="Unbekannte Zeugnisart.")
    eid = eingabe.employee_id
    if eid == 0:
        raise HTTPException(status_code=400, detail="Bitte eine Person aus der Liste wählen.")

    z = Zeugnis(art=eingabe.art, erstellt_am=_jetzt(), aktualisiert_am=_jetzt(), name="")
    if eid > 0:
        emp = await db.get(PersonioEmployee, eid)
        if emp is None:
            raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")
        z.employee_id = emp.id
        z.name = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or f"#{emp.id}"
        z.abteilung = emp.department
        z.taetigkeit = emp.position
        z.eintritt = emp.hire_date
        z.austritt = emp.termination_date
    else:
        ext = await db.get(OnboardingExtern, -eid)
        if ext is None:
            raise HTTPException(status_code=404, detail="Externe Person nicht gefunden.")
        z.extern_id = ext.id
        z.name = ext.name
        z.abteilung = ext.abteilung
        z.taetigkeit = ext.position
        z.eintritt = ext.hire_date
    db.add(z)
    await db.commit()
    z = await _hole(db, z.id)
    return _read(z)


@router.get("/{zeugnis_id}", response_model=ZeugnisRead)
async def lesen(zeugnis_id: int, db: AsyncSession = Depends(get_async_db_session)) -> ZeugnisRead:
    return _read(await _hole(db, zeugnis_id))


@router.put("/{zeugnis_id}", response_model=ZeugnisRead)
async def aendern(
    zeugnis_id: int, eingabe: ZeugnisUpdate, db: AsyncSession = Depends(get_async_db_session)
) -> ZeugnisRead:
    z = await _hole(db, zeugnis_id)

    # Skalare Felder (nur gesetzte übernehmen).
    for feld in (
        "name", "geschlecht", "geburtsdatum", "personalnummer", "abteilung",
        "taetigkeit", "eintritt", "austritt", "anlass", "ausstellungsdatum",
        "taetigkeit_stichpunkte", "besondere_kompetenzen", "besondere_erfolge",
    ):
        wert = getattr(eingabe, feld)
        if wert is not None:
            setattr(z, feld, wert)
    if eingabe.fuehrungskraft is not None:
        z.fuehrungskraft = eingabe.fuehrungskraft
    if eingabe.art is not None:
        if eingabe.art not in ZEUGNIS_ARTEN:
            raise HTTPException(status_code=400, detail="Unbekannte Zeugnisart.")
        z.art = eingabe.art
    if eingabe.status is not None:
        if eingabe.status not in ("entwurf", "final"):
            raise HTTPException(status_code=400, detail="Unbekannter Status.")
        z.status = eingabe.status

    if eingabe.bewertungen is not None:
        neu = {}
        for dim, note in eingabe.bewertungen.items():
            if dim not in ZEUGNIS_DIMENSIONEN:
                raise HTTPException(status_code=400, detail=f"Unbekannte Dimension: {dim}")
            if note not in (1, 2, 3, 4):
                raise HTTPException(status_code=400, detail="Note muss 1–4 sein.")
            neu[dim] = note
        z.bewertungen.clear()
        for dim, note in neu.items():
            z.bewertungen.append(ZeugnisBewertung(dimension=dim, note=note))
        z.schlussnote = _schnitt(neu)

    if eingabe.abschnitte is not None:
        z.abschnitte_json = {
            k: str(eingabe.abschnitte.get(k, "") or "") for k in ZEUGNIS_ABSCHNITTE
        }

    z.aktualisiert_am = _jetzt()
    await db.commit()
    z = await _hole(db, z.id)
    return _read(z)


@router.delete("/{zeugnis_id}", status_code=204)
async def entfernen(zeugnis_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    z = await _hole(db, zeugnis_id)
    await db.delete(z)
    await db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------
# KI-Generierung
# --------------------------------------------------------------------------


@router.post("/{zeugnis_id}/generate", response_model=ZeugnisRead)
async def generieren(
    zeugnis_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> ZeugnisRead:
    z = await _hole(db, zeugnis_id)
    noten = _noten(z)
    if not noten:
        raise HTTPException(
            status_code=400, detail="Bitte zuerst mindestens eine Note vergeben."
        )
    try:
        abschnitte = await generiere_abschnitte(
            geschlecht=z.geschlecht,
            taetigkeit=z.taetigkeit,
            abteilung=z.abteilung,
            eintritt=z.eintritt,
            austritt=z.austritt,
            art=z.art,
            fuehrungskraft=z.fuehrungskraft,
            noten=noten,
            stichpunkte=z.taetigkeit_stichpunkte,
            kompetenzen=z.besondere_kompetenzen,
            erfolge=z.besondere_erfolge,
        )
    except ZeugnisKIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    z.abschnitte_json = _name_ersetzen(abschnitte, z)
    z.schlussnote = _schnitt(noten)
    z.aktualisiert_am = _jetzt()
    await db.commit()
    z = await _hole(db, z.id)
    return _read(z)


# --------------------------------------------------------------------------
# Dokumente
# --------------------------------------------------------------------------


async def _dateiname(z: Zeugnis, endung: str) -> str:
    basis = (z.name or "Zeugnis").replace(" ", "_")
    return f"Arbeitszeugnis_{basis}.{endung}"


@router.get("/{zeugnis_id}/docx")
async def docx(zeugnis_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    z = await _hole(db, zeugnis_id)
    if not z.abschnitte_json:
        raise HTTPException(status_code=400, detail="Noch kein Text generiert.")
    logo = await lade_logo(db)
    daten = build_zeugnis_docx(z, await _aussteller(db), logo.daten if logo else None)
    return Response(
        content=daten,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{await _dateiname(z, "docx")}"'},
    )


@router.get("/{zeugnis_id}/pdf")
async def pdf(zeugnis_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    z = await _hole(db, zeugnis_id)
    if not z.abschnitte_json:
        raise HTTPException(status_code=400, detail="Noch kein Text generiert.")
    logo = await lade_logo(db)
    docx_bytes = build_zeugnis_docx(z, await _aussteller(db), logo.daten if logo else None)
    try:
        pdf_bytes = await convert_docx_to_pdf(docx_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"PDF-Erzeugung fehlgeschlagen: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{await _dateiname(z, "pdf")}"'},
    )
