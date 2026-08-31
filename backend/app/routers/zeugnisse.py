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
from app.models import (
    OnboardingExtern,
    PersonioEmployee,
    Zeugnis,
    ZeugnisAussteller,
    ZeugnisBaustein,
    ZeugnisBewertung,
    ZeugnisVorlage,
)
from app.models.zeugnis import ZEUGNIS_ABSCHNITTE, ZEUGNIS_ARTEN, ZEUGNIS_DIMENSIONEN
from app.security.directus_auth import get_current_user, require_admin
from app.services.pdf_logo import lade_logo
from app.services.zeugnis_baukasten import (
    baue_abschnitte,
    bausteine_defaults,
    ersetze_pronomen,
)
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
    #: HR-Manager (2. Unterschrift) als Personio-Employee-ID; Anzeige-Name/​Titel
    #: kommen live aus Personio.
    hr_employee_id: int | None = None
    hr_name: str | None = None
    hr_titel: str | None = None


class AusstellerUpdate(BaseModel):
    firma: str
    standort: str | None = None
    unterzeichner1_name: str | None = None
    unterzeichner1_titel: str | None = None
    unterzeichner2_name: str | None = None
    unterzeichner2_titel: str | None = None
    hr_employee_id: int | None = None


class VorlageRead(BaseModel):
    id: int
    name: str
    noten: dict[str, int]


class VorlageCreate(BaseModel):
    name: str
    #: {dimension: note} — Noten 1–4.
    noten: dict[str, int]


class BausteinRead(BaseModel):
    dimension: str
    note: int
    text: str


class BausteinWrite(BaseModel):
    #: Zu speichernde Bausteine (dimension, note 1–4, text).
    bausteine: list[BausteinRead]


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


def _name_ersetzen(
    abschnitte: dict[str, str], z: Zeugnis, *, pronomen: bool = False
) -> dict[str, str]:
    """Platzhalter im generierten Text ersetzen.

    - **Einleitung**: [NAME] → „Anrede Vorname Nachname" (einmalige volle Nennung).
    - **Übrige Abschnitte**: mit ``pronomen`` (Baukasten) → Personalpronomen
      (er/sie), damit sich „Herr/Frau Nachname" nicht wiederholt; sonst (KI, die
      eigene Pronomen schreibt) → „Anrede Nachname".
    - Pronomen-Platzhalter ([ER_SIE], [IHM_IHR] …) werden geschlechtsgerecht ersetzt.
    """
    voll = f"{_anrede(z.geschlecht)} {(z.name or '').strip()}".strip()
    nachname = (z.name or "").split()[-1] if (z.name or "").strip() else ""
    kurz = f"{_anrede(z.geschlecht)} {nachname}".strip()
    ergebnis: dict[str, str] = {}
    for k, v in abschnitte.items():
        text = v or ""
        if k == "einleitung":
            text = text.replace("[NAME]", voll)
        elif pronomen:
            text = text.replace("[NAME]", "[ER_SIE]")
        else:
            text = text.replace("[NAME]", kurz)
        ergebnis[k] = ersetze_pronomen(text, z.geschlecht)
    return ergebnis


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


async def _bausteine(db: AsyncSession) -> dict[str, dict[int, str]]:
    """DB-Textbausteine als ``{dimension: {note: text}}`` (leere Tabelle → {})."""
    rows = (await db.execute(select(ZeugnisBaustein))).scalars().all()
    daten: dict[str, dict[int, str]] = {}
    for b in rows:
        daten.setdefault(b.dimension, {})[b.note] = b.text
    return daten


def _pfad(daten: dict | None, *keys: str):
    """Sicher durch verschachteltes Personio-raw_json navigieren."""
    cur = daten
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


async def _supervisor(
    db: AsyncSession, z: Zeugnis, aussteller: ZeugnisAussteller | None
) -> tuple[str | None, str | None]:
    """Vorgesetzte:r der Person aus Personio (Name + dessen Position als Titel).

    Der Supervisor hängt über die Personio-Org-Struktur an der Abteilung. Fällt
    er weg (Externe, kein Supervisor gepflegt), greift ``unterzeichner1`` aus dem
    Ausstellerprofil.
    """
    fallback = (
        (aussteller.unterzeichner1_name, aussteller.unterzeichner1_titel)
        if aussteller
        else (None, None)
    )
    if not z.employee_id or z.employee_id <= 0:
        return fallback
    mitarbeiter = await db.get(PersonioEmployee, z.employee_id)
    sup = _pfad(
        mitarbeiter.raw_json if mitarbeiter else None,
        "attributes", "supervisor", "value", "attributes",
    )
    if not isinstance(sup, dict):
        return fallback
    name = _pfad(sup, "preferred_name", "value") or " ".join(
        x for x in (_pfad(sup, "first_name", "value"), _pfad(sup, "last_name", "value")) if x
    )
    if not name:
        return fallback
    titel = None
    sup_id = _pfad(sup, "id", "value")
    if sup_id:
        chef = await db.get(PersonioEmployee, sup_id)
        titel = chef.position if chef else None
    return (name, titel)


def _personio_geburtstag(mitarbeiter: PersonioEmployee | None) -> date | None:
    """Geburtsdatum aus Personio (dynamisches Feld mit Label „Geburtsdatum")."""
    attrs = _pfad(mitarbeiter.raw_json if mitarbeiter else None, "attributes")
    if not isinstance(attrs, dict):
        return None
    for feld in attrs.values():
        if (
            isinstance(feld, dict)
            and feld.get("type") == "date"
            and (feld.get("label") or "").strip().lower() == "geburtsdatum"
            and feld.get("value")
        ):
            try:
                return date.fromisoformat(str(feld["value"])[:10])
            except ValueError:
                return None
    return None


def _personio_geschlecht(mitarbeiter: PersonioEmployee | None) -> str | None:
    """Personio-``gender`` → 'm' | 'w' | 'd' (unbekannt → None)."""
    wert = (_pfad(mitarbeiter.raw_json if mitarbeiter else None, "attributes", "gender", "value") or "")
    return {"male": "m", "female": "w", "diverse": "d"}.get(str(wert).strip().lower())


async def _hr_manager(
    db: AsyncSession, aussteller: ZeugnisAussteller | None
) -> tuple[str | None, str | None]:
    """HR-Manager (2. Unterschrift): live aus Personio über ``hr_employee_id``.

    Wie beim Vorgesetzten kommen Name + Position aus Personio. Ist keine
    HR-Person gewählt, greifen die Freitextfelder ``unterzeichner2``.
    """
    fallback = (
        (aussteller.unterzeichner2_name, aussteller.unterzeichner2_titel)
        if aussteller
        else (None, None)
    )
    if not aussteller or not aussteller.hr_employee_id:
        return fallback
    hr = await db.get(PersonioEmployee, aussteller.hr_employee_id)
    if hr is None:
        return fallback
    name = f"{hr.first_name or ''} {hr.last_name or ''}".strip()
    return (name or fallback[0], hr.position or fallback[1])


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


async def _aussteller_read(db: AsyncSession, a: ZeugnisAussteller) -> AusstellerRead:
    """AusstellerRead inkl. live aus Personio aufgelöstem HR-Manager (Name/Titel)."""
    hr_name, hr_titel = await _hr_manager(db, a)
    return AusstellerRead(
        firma=a.firma,
        standort=a.standort,
        unterzeichner1_name=a.unterzeichner1_name,
        unterzeichner1_titel=a.unterzeichner1_titel,
        unterzeichner2_name=a.unterzeichner2_name,
        unterzeichner2_titel=a.unterzeichner2_titel,
        hr_employee_id=a.hr_employee_id,
        hr_name=hr_name,
        hr_titel=hr_titel,
    )


@router.get("/aussteller", response_model=AusstellerRead | None)
async def aussteller_lesen(db: AsyncSession = Depends(get_async_db_session)):
    a = await _aussteller(db)
    return await _aussteller_read(db, a) if a is not None else None


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
    a.hr_employee_id = eingabe.hr_employee_id
    a.aktualisiert_am = _jetzt()
    await db.commit()
    await db.refresh(a)
    return await _aussteller_read(db, a)


# --------------------------------------------------------------------------
# Bewertungs-Vorlagen (Profile)
# --------------------------------------------------------------------------


def _valide_noten(noten: dict[str, int]) -> dict[str, int]:
    rein: dict[str, int] = {}
    for dim, note in noten.items():
        if dim not in ZEUGNIS_DIMENSIONEN:
            raise HTTPException(status_code=400, detail=f"Unbekannte Dimension: {dim}")
        if note not in (1, 2, 3, 4):
            raise HTTPException(status_code=400, detail="Note muss 1–4 sein.")
        rein[dim] = note
    return rein


@router.get("/vorlagen", response_model=list[VorlageRead])
async def vorlagen(db: AsyncSession = Depends(get_async_db_session)) -> list[VorlageRead]:
    rows = (
        (await db.execute(select(ZeugnisVorlage).order_by(ZeugnisVorlage.name)))
        .scalars()
        .all()
    )
    return [VorlageRead(id=v.id, name=v.name, noten=v.noten) for v in rows]


@router.post("/vorlagen", response_model=VorlageRead, status_code=201)
async def vorlage_anlegen(
    eingabe: VorlageCreate, db: AsyncSession = Depends(get_async_db_session)
) -> VorlageRead:
    name = eingabe.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name ist Pflicht.")
    noten = _valide_noten(eingabe.noten)
    if not noten:
        raise HTTPException(status_code=400, detail="Mindestens eine Note nötig.")
    vorhanden = (
        await db.execute(select(ZeugnisVorlage).where(ZeugnisVorlage.name == name))
    ).scalar_one_or_none()
    if vorhanden is not None:
        vorhanden.noten = noten
        vorhanden.aktualisiert_am = _jetzt()
        v = vorhanden
    else:
        v = ZeugnisVorlage(name=name, noten=noten, aktualisiert_am=_jetzt())
        db.add(v)
    await db.commit()
    await db.refresh(v)
    return VorlageRead(id=v.id, name=v.name, noten=v.noten)


@router.delete("/vorlagen/{vorlage_id}", status_code=204)
async def vorlage_entfernen(
    vorlage_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    v = await db.get(ZeugnisVorlage, vorlage_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden.")
    await db.delete(v)
    await db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------
# Textbausteine (editierbare Standardformulierungen je Dimension × Note)
# --------------------------------------------------------------------------


async def _baustein_gitter(db: AsyncSession) -> list[BausteinRead]:
    """Vollständiges Raster (alle Dimensionen × Noten 1–4): DB-Text, sonst Default."""
    eff = bausteine_defaults()
    for dim, noten in (await _bausteine(db)).items():
        for note, text in noten.items():
            if text and text.strip():
                eff.setdefault(dim, {})[note] = text
    return [
        BausteinRead(dimension=dim, note=note, text=eff.get(dim, {}).get(note, ""))
        for dim in ZEUGNIS_DIMENSIONEN
        for note in (1, 2, 3, 4)
    ]


@router.get("/bausteine", response_model=list[BausteinRead])
async def bausteine_lesen(db: AsyncSession = Depends(get_async_db_session)) -> list[BausteinRead]:
    """Alle Textbausteine als Raster (Dimension × Note); fehlende mit Default gefüllt."""
    return await _baustein_gitter(db)


@router.put("/bausteine", response_model=list[BausteinRead])
async def bausteine_speichern(
    eingabe: BausteinWrite, db: AsyncSession = Depends(get_async_db_session)
) -> list[BausteinRead]:
    """Geänderte Textbausteine speichern (Upsert je Dimension × Note)."""
    vorhanden = {
        (b.dimension, b.note): b
        for b in (await db.execute(select(ZeugnisBaustein))).scalars().all()
    }
    for e in eingabe.bausteine:
        if e.dimension not in ZEUGNIS_DIMENSIONEN:
            raise HTTPException(status_code=400, detail=f"Unbekannte Dimension: {e.dimension}")
        if e.note not in (1, 2, 3, 4):
            raise HTTPException(status_code=400, detail="Note muss 1–4 sein.")
        row = vorhanden.get((e.dimension, e.note))
        if row is not None:
            row.text = e.text
            row.aktualisiert_am = _jetzt()
        else:
            db.add(ZeugnisBaustein(
                dimension=e.dimension, note=e.note, text=e.text, aktualisiert_am=_jetzt(),
            ))
    await db.commit()
    return await _baustein_gitter(db)


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
        z.geburtsdatum = _personio_geburtstag(emp)
        z.geschlecht = _personio_geschlecht(emp)
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
        # Löschungen zuerst ausspielen, sonst kollidieren die neuen Zeilen mit den
        # alten am UNIQUE(zeugnis_id, dimension) (Insert-vor-Delete im selben Flush).
        await db.flush()
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
    if z.ausstellungsdatum is None:
        z.ausstellungsdatum = date.today()
    z.aktualisiert_am = _jetzt()
    await db.commit()
    z = await _hole(db, z.id)
    return _read(z)


@router.post("/{zeugnis_id}/generate/{abschnitt}", response_model=ZeugnisRead)
async def generieren_abschnitt(
    zeugnis_id: int,
    abschnitt: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> ZeugnisRead:
    """Nur einen einzelnen Abschnitt gezielt neu erzeugen (Ton auf die übrigen abgestimmt)."""
    if abschnitt not in ZEUGNIS_ABSCHNITTE:
        raise HTTPException(status_code=404, detail="Unbekannter Abschnitt.")
    z = await _hole(db, zeugnis_id)
    noten = _noten(z)
    if not noten:
        raise HTTPException(
            status_code=400, detail="Bitte zuerst mindestens eine Note vergeben."
        )
    try:
        neu = await generiere_abschnitte(
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
            nur_abschnitt=abschnitt,
            bestehende=dict(z.abschnitte_json or {}),
        )
    except ZeugnisKIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    zusammen = dict(z.abschnitte_json or {})
    zusammen.update(_name_ersetzen(neu, z))
    z.abschnitte_json = zusammen
    z.aktualisiert_am = _jetzt()
    await db.commit()
    z = await _hole(db, z.id)
    return _read(z)


async def _baue(db: AsyncSession, z: Zeugnis) -> dict[str, str]:
    """Deterministischer Textbaustein-Aufbau (ohne KI, ohne API-Key)."""
    noten = _noten(z)
    if not noten:
        raise HTTPException(
            status_code=400, detail="Bitte zuerst mindestens eine Note vergeben."
        )
    schnitt = _schnitt(noten)
    # Geburtsdatum: manueller Wert hat Vorrang, sonst live aus Personio
    # (deckt ältere Zeugnisse ab, die vor dem Personio-Abgleich angelegt wurden).
    geburtsdatum = z.geburtsdatum
    if geburtsdatum is None and z.employee_id and z.employee_id > 0:
        geburtsdatum = _personio_geburtstag(await db.get(PersonioEmployee, z.employee_id))
    return baue_abschnitte(
        geschlecht=z.geschlecht,
        geburtsdatum=geburtsdatum,
        taetigkeit=z.taetigkeit,
        abteilung=z.abteilung,
        eintritt=z.eintritt,
        austritt=z.austritt,
        art=z.art,
        anlass=z.anlass,
        fuehrungskraft=z.fuehrungskraft,
        noten=noten,
        schnitt=float(schnitt) if schnitt is not None else None,
        stichpunkte=z.taetigkeit_stichpunkte,
        kompetenzen=z.besondere_kompetenzen,
        erfolge=z.besondere_erfolge,
        bausteine=await _bausteine(db),
    )


@router.post("/{zeugnis_id}/baukasten", response_model=ZeugnisRead)
async def baukasten(
    zeugnis_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> ZeugnisRead:
    """Gesamtes Zeugnis aus Textbausteinen erzeugen (ohne KI)."""
    z = await _hole(db, zeugnis_id)
    abschnitte = await _baue(db, z)
    z.abschnitte_json = _name_ersetzen(abschnitte, z, pronomen=True)
    z.schlussnote = _schnitt(_noten(z))
    if z.ausstellungsdatum is None:
        z.ausstellungsdatum = date.today()
    z.aktualisiert_am = _jetzt()
    await db.commit()
    z = await _hole(db, z.id)
    return _read(z)


@router.post("/{zeugnis_id}/baukasten/{abschnitt}", response_model=ZeugnisRead)
async def baukasten_abschnitt(
    zeugnis_id: int,
    abschnitt: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> ZeugnisRead:
    """Einen einzelnen Abschnitt aus Textbausteinen (neu) erzeugen (ohne KI)."""
    if abschnitt not in ZEUGNIS_ABSCHNITTE:
        raise HTTPException(status_code=404, detail="Unbekannter Abschnitt.")
    z = await _hole(db, zeugnis_id)
    abschnitte = await _baue(db, z)
    zusammen = dict(z.abschnitte_json or {})
    zusammen[abschnitt] = _name_ersetzen(abschnitte, z, pronomen=True)[abschnitt]
    z.abschnitte_json = zusammen
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
    aussteller = await _aussteller(db)
    sup_name, sup_titel = await _supervisor(db, z, aussteller)
    hr_name, hr_titel = await _hr_manager(db, aussteller)
    daten = build_zeugnis_docx(
        z, aussteller, logo.daten if logo else None,
        supervisor_name=sup_name, supervisor_titel=sup_titel,
        hr_name=hr_name, hr_titel=hr_titel,
        dateiname=await _dateiname(z, "docx"),
    )
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
    aussteller = await _aussteller(db)
    sup_name, sup_titel = await _supervisor(db, z, aussteller)
    hr_name, hr_titel = await _hr_manager(db, aussteller)
    docx_bytes = build_zeugnis_docx(
        z, aussteller, logo.daten if logo else None,
        supervisor_name=sup_name, supervisor_titel=sup_titel,
        hr_name=hr_name, hr_titel=hr_titel,
        dateiname=await _dateiname(z, "pdf"),
    )
    try:
        pdf_bytes = await convert_docx_to_pdf(docx_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"PDF-Erzeugung fehlgeschlagen: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{await _dateiname(z, "pdf")}"'},
    )
