"""Kompetenzen — Qualifikationsmatrix je Bereich (v1.90).

Der gesamte Router ist admin-gated, wie das Schulungs-Modul: die Matrizen
enthalten personenbezogene Leistungsbewertungen.

Compute-justified: clause 1 (file parsing) — die Import-Routen lesen eine
hochgeladene .xlsx serverseitig ein; clause 3 (multi-row atomic compute) — die
Übernahme ersetzt eine Matrix samt Qualifikationen, Personen und Bewertungen
in einer Transaktion.
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_db_session
from app.models import (
    KompetenzBewertung,
    KompetenzKategorie,
    KompetenzMatrix,
    KompetenzPerson,
    KompetenzQualifikation,
    PersonioEmployee,
)
from app.models.kompetenz import KOMPETENZ_BEREICHE
from app.parsing.kompetenz_parser import parse_qualifikationsmatrix
from app.security.directus_auth import get_current_user, require_admin
from app.services.kompetenz_import import ImportVorschau, baue_vorschau, uebernehmen

router = APIRouter(
    prefix="/api/hr/kompetenzen",
    tags=["kompetenzen"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


class MatrixVorschauRead(BaseModel):
    blatt: str
    titel: str | None
    qualifikationen: int
    personen: int
    bewertungen: int
    zugeordnet: int
    nicht_zugeordnet: list[str]
    platzhalter: int


class ImportVorschauRead(BaseModel):
    """Ergebnis von Vorschau und Übernahme — bewusst identische Form."""

    dateiname: str
    bereich: str
    matrizen: list[MatrixVorschauRead]
    warnungen: list[str]


class MatrixUebersichtRead(BaseModel):
    """Eine Matrix ohne ihre Zellen — für die Auswahl."""

    id: int
    bereich: str
    blatt: str
    titel: str | None
    stand: date | None
    qualifikationen: int
    personen: int
    importiert_am: datetime


class PersonRead(BaseModel):
    id: int
    name: str
    employee_id: int | None
    #: Durchschnittlicher Erfüllungsgrad über alle bewerteten Qualifikationen.
    durchschnitt: int | None
    #: Anzahl Qualifikationen, bei denen der Erfüllungsgrad unter 100 % liegt
    #: und ein Anforderungslevel gesetzt ist.
    luecken: int


class ZelleRead(BaseModel):
    person_id: int
    anforderungslevel: int | None
    erfuellungsgrad: int | None


class QualifikationRead(BaseModel):
    id: int
    nr: int | None
    kategorie: str | None
    bezeichnung: str
    #: Aus den Zellen berechnet, nicht aus der Excel übernommen.
    anzahl_mitarbeiter: int
    durchschnitt: int | None
    zellen: list[ZelleRead]


class MatrixRead(BaseModel):
    id: int
    bereich: str
    blatt: str
    titel: str | None
    stand: date | None
    importiert_am: datetime
    personen: list[PersonRead]
    qualifikationen: list[QualifikationRead]
    #: Alle Kategorien der Matrix in Anzeigereihenfolge — deklarierte (auch leere)
    #: und aus Qualifikationen abgeleitete, ohne Dubletten. "Ohne Kategorie" ist
    #: nicht enthalten (das ist die Sammelgruppe der Zeilen ohne Kategorie).
    kategorien: list[str]


def _als_read(v: ImportVorschau) -> ImportVorschauRead:
    return ImportVorschauRead(
        dateiname=v.dateiname,
        bereich=v.bereich,
        matrizen=[MatrixVorschauRead(**vars(m)) for m in v.matrizen],
        warnungen=v.warnungen,
    )


def _pruefe_bereich(bereich: str) -> str:
    if bereich not in KOMPETENZ_BEREICHE:
        raise HTTPException(status_code=400, detail="Unbekannter Bereich.")
    return bereich


async def _parse_upload(file: UploadFile):
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Bitte eine .xlsx-Datei hochladen.")
    inhalt = await file.read()
    try:
        return parse_qualifikationsmatrix(inhalt, file.filename or "unbenannt.xlsx")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # openpyxl wirft je nach Defekt sehr unterschiedlich
        raise HTTPException(
            status_code=400, detail=f"Datei konnte nicht gelesen werden: {exc}"
        ) from exc


# Die beiden Import-Routen haben seit v1.91 keine Oberfläche mehr: führend ist
# die Tabelle in der App, nicht die Excel. Sie bleiben für die Erstbefüllung
# eines Bereichs bestehen (Betrieb ruft sie einmalig auf) — ein Aufruf ERSETZT
# die Matrizen des Bereichs blattweise und verwirft dabei alles von Hand
# Gepflegte. Ohne Oberfläche kann das niemand mehr versehentlich auslösen.


@router.post("/{bereich}/import/preview", response_model=ImportVorschauRead)
async def import_preview(
    bereich: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> ImportVorschauRead:
    """Datei analysieren, ohne etwas zu schreiben."""
    parsed = await _parse_upload(file)
    return _als_read(await baue_vorschau(db, parsed, _pruefe_bereich(bereich)))


@router.post("/{bereich}/import/commit", response_model=ImportVorschauRead)
async def import_commit(
    bereich: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> ImportVorschauRead:
    """Datei übernehmen — ersetzt die Matrizen dieses Bereichs blattweise."""
    parsed = await _parse_upload(file)
    return _als_read(await uebernehmen(db, parsed, _pruefe_bereich(bereich)))


@router.get("", response_model=list[MatrixUebersichtRead])
async def liste_matrizen(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[MatrixUebersichtRead]:
    """Alle importierten Matrizen, ohne Zellen."""
    matrizen = (
        (
            await db.execute(
                select(KompetenzMatrix)
                .options(
                    selectinload(KompetenzMatrix.qualifikationen),
                    selectinload(KompetenzMatrix.personen),
                )
                .order_by(KompetenzMatrix.bereich, KompetenzMatrix.blatt)
            )
        )
        .scalars()
        .all()
    )
    return [
        MatrixUebersichtRead(
            id=m.id,
            bereich=m.bereich,
            blatt=m.blatt,
            titel=m.titel,
            stand=m.stand,
            qualifikationen=len(m.qualifikationen),
            personen=len(m.personen),
            importiert_am=m.importiert_am,
        )
        for m in matrizen
    ]


@router.get("/matrix/{matrix_id}", response_model=MatrixRead)
async def matrix_ansehen(
    matrix_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> MatrixRead:
    """Eine vollständige Matrix samt Zellen.

    ``anzahl_mitarbeiter`` und ``durchschnitt`` werden hier berechnet — in der
    Excel stehen dafür Formeln, die beim Import bewusst verworfen wurden.
    """
    matrix = (
        await db.execute(
            select(KompetenzMatrix)
            .options(selectinload(KompetenzMatrix.personen))
            .where(KompetenzMatrix.id == matrix_id)
        )
    ).scalar_one_or_none()
    if matrix is None:
        raise HTTPException(status_code=404, detail="Matrix nicht gefunden.")

    qualifikationen = (
        (
            await db.execute(
                select(KompetenzQualifikation)
                .options(selectinload(KompetenzQualifikation.bewertungen))
                .where(KompetenzQualifikation.matrix_id == matrix_id)
                .order_by(KompetenzQualifikation.reihenfolge)
            )
        )
        .scalars()
        .all()
    )

    # Kennzahlen je Person über alle Qualifikationen hinweg.
    summen: dict[int, list[int]] = {p.id: [] for p in matrix.personen}
    luecken: dict[int, int] = {p.id: 0 for p in matrix.personen}

    qual_read: list[QualifikationRead] = []
    for q in qualifikationen:
        grade = [b.erfuellungsgrad for b in q.bewertungen if b.erfuellungsgrad is not None]
        for b in q.bewertungen:
            if b.erfuellungsgrad is not None:
                summen[b.person_id].append(b.erfuellungsgrad)
                if b.anforderungslevel and b.erfuellungsgrad < 100:
                    luecken[b.person_id] += 1
        qual_read.append(
            QualifikationRead(
                id=q.id,
                nr=q.nr,
                kategorie=q.kategorie,
                bezeichnung=q.bezeichnung,
                anzahl_mitarbeiter=len(q.bewertungen),
                durchschnitt=round(sum(grade) / len(grade)) if grade else None,
                zellen=[
                    ZelleRead(
                        person_id=b.person_id,
                        anforderungslevel=b.anforderungslevel,
                        erfuellungsgrad=b.erfuellungsgrad,
                    )
                    for b in q.bewertungen
                ],
            )
        )

    # Kategorien in Anzeigereihenfolge: erst wie sie in den Qualifikationen
    # (nach reihenfolge sortiert) zuerst auftauchen, dann deklarierte, die noch
    # keine Qualifikation tragen (leere Kategorien), am Ende.
    kategorien: list[str] = []
    for q in qualifikationen:
        if q.kategorie and q.kategorie not in kategorien:
            kategorien.append(q.kategorie)
    deklariert = (
        (
            await db.execute(
                select(KompetenzKategorie)
                .where(KompetenzKategorie.matrix_id == matrix_id)
                .order_by(KompetenzKategorie.reihenfolge, KompetenzKategorie.id)
            )
        )
        .scalars()
        .all()
    )
    for k in deklariert:
        if k.name not in kategorien:
            kategorien.append(k.name)

    personen = sorted(matrix.personen, key=lambda p: p.reihenfolge)
    return MatrixRead(
        id=matrix.id,
        bereich=matrix.bereich,
        blatt=matrix.blatt,
        titel=matrix.titel,
        stand=matrix.stand,
        importiert_am=matrix.importiert_am,
        kategorien=kategorien,
        personen=[
            PersonRead(
                id=p.id,
                name=p.name,
                employee_id=p.employee_id,
                durchschnitt=(
                    round(sum(summen[p.id]) / len(summen[p.id])) if summen[p.id] else None
                ),
                luecken=luecken[p.id],
            )
            for p in personen
        ],
        qualifikationen=qual_read,
    )


# --------------------------------------------------------------------------
# Bearbeiten
#
# Die Matrix ist nach dem Import kein eingefrorener Abzug: Bewertungen ändern
# sich laufend, Personen kommen und gehen. Ein erneuter Import ersetzt den
# Bereich blattweise und überschreibt Handarbeit — der Hinweis darauf steht in
# der Oberfläche am Import.
# --------------------------------------------------------------------------


class ZelleSetzen(BaseModel):
    qualifikation_id: int
    person_id: int
    #: 0-4; None löscht die Anforderung.
    anforderungslevel: int | None = None
    #: 0-100 %; None löscht den Erfüllungsgrad.
    erfuellungsgrad: int | None = None


class PersonAnlegen(BaseModel):
    name: str
    #: Optionale Verknüpfung nach Personio.
    employee_id: int | None = None


class QualifikationAnlegen(BaseModel):
    bezeichnung: str
    kategorie: str | None = None
    nr: int | None = None


class KategorieUmbenennen(BaseModel):
    #: Bestehender Kategoriename in dieser Matrix.
    alt: str
    #: Neuer Name; darf nicht leer sein.
    neu: str


class KategorieAnlegen(BaseModel):
    #: Name der neuen (zunächst leeren) Kategorie.
    name: str


class VerfuegbarePersonRead(BaseModel):
    """Ein Personio-Mitarbeiter, der noch nicht in dieser Matrix steht."""

    employee_id: int
    name: str
    abteilung: str | None
    position: str | None


async def _matrix(db: AsyncSession, matrix_id: int) -> KompetenzMatrix:
    m = (
        await db.execute(select(KompetenzMatrix).where(KompetenzMatrix.id == matrix_id))
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Matrix nicht gefunden.")
    return m


@router.get("/matrix/{matrix_id}/verfuegbar", response_model=list[VerfuegbarePersonRead])
async def verfuegbare_personen(
    matrix_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[VerfuegbarePersonRead]:
    """Aktive Personio-Mitarbeiter, die noch keine Spalte in dieser Matrix haben.

    Damit ein neuer Mitarbeiter direkt aus Personio übernommen wird, statt den
    Namen abzutippen — abgetippte Namen finden später keinen Treffer mehr
    (siehe die Fälle ohne Zuordnung aus dem Erstimport).
    """
    await _matrix(db, matrix_id)

    schon_drin = set(
        (
            await db.execute(
                select(KompetenzPerson.employee_id).where(
                    KompetenzPerson.matrix_id == matrix_id,
                    KompetenzPerson.employee_id.isnot(None),
                )
            )
        )
        .scalars()
        .all()
    )
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
        VerfuegbarePersonRead(
            employee_id=e.id,
            name=f"{e.first_name or ''} {e.last_name or ''}".strip() or f"#{e.id}",
            abteilung=e.department,
            position=e.position,
        )
        for e in aktive
        if e.id not in schon_drin
    ]


@router.put("/matrix/{matrix_id}/zelle", response_model=ZelleRead)
async def zelle_setzen(
    matrix_id: int,
    eingabe: ZelleSetzen,
    db: AsyncSession = Depends(get_async_db_session),
) -> ZelleRead:
    """Anforderungslevel und Erfüllungsgrad einer Zelle setzen.

    Legt die Zelle an, falls es sie noch nicht gibt — in der importierten Matrix
    existieren nur Zellen, die in der Excel gefüllt waren.
    """
    if eingabe.anforderungslevel is not None and not 0 <= eingabe.anforderungslevel <= 4:
        raise HTTPException(status_code=400, detail="Anforderungslevel muss 0-4 sein.")
    if eingabe.erfuellungsgrad is not None and not 0 <= eingabe.erfuellungsgrad <= 100:
        raise HTTPException(status_code=400, detail="Erfüllungsgrad muss 0-100 sein.")

    await _matrix(db, matrix_id)
    qual = (
        await db.execute(
            select(KompetenzQualifikation).where(
                KompetenzQualifikation.id == eingabe.qualifikation_id,
                KompetenzQualifikation.matrix_id == matrix_id,
            )
        )
    ).scalar_one_or_none()
    person = (
        await db.execute(
            select(KompetenzPerson).where(
                KompetenzPerson.id == eingabe.person_id,
                KompetenzPerson.matrix_id == matrix_id,
            )
        )
    ).scalar_one_or_none()
    if qual is None or person is None:
        raise HTTPException(
            status_code=404, detail="Zeile oder Spalte gehört nicht zu dieser Matrix."
        )

    zelle = (
        await db.execute(
            select(KompetenzBewertung).where(
                KompetenzBewertung.qualifikation_id == qual.id,
                KompetenzBewertung.person_id == person.id,
            )
        )
    ).scalar_one_or_none()
    if zelle is None:
        zelle = KompetenzBewertung(qualifikation_id=qual.id, person_id=person.id)
        db.add(zelle)
    zelle.anforderungslevel = eingabe.anforderungslevel
    zelle.erfuellungsgrad = eingabe.erfuellungsgrad
    await db.commit()
    await db.refresh(zelle)
    return ZelleRead(
        person_id=person.id,
        anforderungslevel=zelle.anforderungslevel,
        erfuellungsgrad=zelle.erfuellungsgrad,
    )


@router.post("/matrix/{matrix_id}/person", response_model=PersonRead, status_code=201)
async def person_anlegen(
    matrix_id: int,
    eingabe: PersonAnlegen,
    db: AsyncSession = Depends(get_async_db_session),
) -> PersonRead:
    """Eine Spalte ergänzen (neue Person in der Matrix).

    Regelfall ist die Übernahme aus Personio über ``employee_id``; der Name
    kommt dann aus dem Stammsatz. Freitext bleibt möglich für Personen, die
    (noch) nicht in Personio stehen — Leiharbeit, Praktikum, externe Prüfer.
    """
    await _matrix(db, matrix_id)

    name = eingabe.name.strip()
    if eingabe.employee_id is not None:
        emp = (
            await db.execute(
                select(PersonioEmployee).where(PersonioEmployee.id == eingabe.employee_id)
            )
        ).scalar_one_or_none()
        if emp is None:
            raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden.")
        # Der Stammsatz gewinnt: sonst driften Schreibweisen wieder auseinander.
        name = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or f"#{emp.id}"

        doppelt = (
            await db.execute(
                select(KompetenzPerson).where(
                    KompetenzPerson.matrix_id == matrix_id,
                    KompetenzPerson.employee_id == emp.id,
                )
            )
        ).scalars().first()
        if doppelt is not None:
            raise HTTPException(
                status_code=409, detail="Diese Person steht bereits in der Matrix."
            )

    if not name:
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein.")

    vorhanden = (
        await db.execute(
            select(KompetenzPerson).where(
                KompetenzPerson.matrix_id == matrix_id, KompetenzPerson.name == name
            )
        )
    ).scalars().first()
    if vorhanden is not None:
        raise HTTPException(
            status_code=409, detail="Diese Person steht bereits in der Matrix."
        )

    letzte = (
        await db.execute(
            select(KompetenzPerson.reihenfolge)
            .where(KompetenzPerson.matrix_id == matrix_id)
            .order_by(KompetenzPerson.reihenfolge.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    person = KompetenzPerson(
        matrix_id=matrix_id,
        name=name,
        employee_id=eingabe.employee_id,
        reihenfolge=(letzte or 0) + 1,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    # Frisch angelegt: noch keine Bewertungen, daher kein Durchschnitt.
    return PersonRead(
        id=person.id,
        name=person.name,
        employee_id=person.employee_id,
        durchschnitt=None,
        luecken=0,
    )


@router.delete("/matrix/{matrix_id}/person/{person_id}", status_code=204)
async def person_entfernen(
    matrix_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Spalte samt ihrer Bewertungen entfernen."""
    person = (
        await db.execute(
            select(KompetenzPerson).where(
                KompetenzPerson.id == person_id, KompetenzPerson.matrix_id == matrix_id
            )
        )
    ).scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail="Person nicht gefunden.")
    await db.delete(person)
    await db.commit()


@router.post(
    "/matrix/{matrix_id}/qualifikation",
    response_model=QualifikationRead,
    status_code=201,
)
async def qualifikation_anlegen(
    matrix_id: int,
    eingabe: QualifikationAnlegen,
    db: AsyncSession = Depends(get_async_db_session),
) -> QualifikationRead:
    """Eine Zeile ergänzen (neue Qualifikation)."""
    bezeichnung = eingabe.bezeichnung.strip()
    if not bezeichnung:
        raise HTTPException(status_code=400, detail="Bezeichnung darf nicht leer sein.")
    await _matrix(db, matrix_id)

    letzte = (
        await db.execute(
            select(KompetenzQualifikation.reihenfolge)
            .where(KompetenzQualifikation.matrix_id == matrix_id)
            .order_by(KompetenzQualifikation.reihenfolge.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    qual = KompetenzQualifikation(
        matrix_id=matrix_id,
        bezeichnung=bezeichnung,
        kategorie=(eingabe.kategorie or "").strip() or None,
        nr=eingabe.nr,
        reihenfolge=(letzte or 0) + 1,
    )
    db.add(qual)
    await db.commit()
    await db.refresh(qual)
    return QualifikationRead(
        id=qual.id,
        nr=qual.nr,
        kategorie=qual.kategorie,
        bezeichnung=qual.bezeichnung,
        anzahl_mitarbeiter=0,
        durchschnitt=None,
        zellen=[],
    )


@router.delete("/matrix/{matrix_id}/qualifikation/{qualifikation_id}", status_code=204)
async def qualifikation_entfernen(
    matrix_id: int,
    qualifikation_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Zeile samt ihrer Bewertungen entfernen."""
    qual = (
        await db.execute(
            select(KompetenzQualifikation).where(
                KompetenzQualifikation.id == qualifikation_id,
                KompetenzQualifikation.matrix_id == matrix_id,
            )
        )
    ).scalar_one_or_none()
    if qual is None:
        raise HTTPException(status_code=404, detail="Qualifikation nicht gefunden.")
    await db.delete(qual)
    await db.commit()


async def _deklarierte_kategorie(
    db: AsyncSession, matrix_id: int, name: str
) -> KompetenzKategorie | None:
    return (
        await db.execute(
            select(KompetenzKategorie).where(
                KompetenzKategorie.matrix_id == matrix_id,
                KompetenzKategorie.name == name,
            )
        )
    ).scalar_one_or_none()


async def _kategorie_belegt(db: AsyncSession, matrix_id: int, name: str) -> bool:
    """Ob eine Qualifikation dieser Matrix die Kategorie trägt."""
    return (
        await db.execute(
            select(KompetenzQualifikation.id)
            .where(
                KompetenzQualifikation.matrix_id == matrix_id,
                KompetenzQualifikation.kategorie == name,
            )
            .limit(1)
        )
    ).scalar_one_or_none() is not None


@router.post("/matrix/{matrix_id}/kategorie", status_code=201)
async def kategorie_anlegen(
    matrix_id: int,
    eingabe: KategorieAnlegen,
    db: AsyncSession = Depends(get_async_db_session),
) -> dict:
    """Eine neue, zunächst leere Kategorie anlegen.

    Sie erscheint sofort als eigene Gruppe und kann danach gefüllt werden.
    409, wenn es die Kategorie schon gibt — deklariert oder an einer
    Qualifikation.
    """
    name = eingabe.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein.")
    await _matrix(db, matrix_id)

    if await _deklarierte_kategorie(db, matrix_id, name) or await _kategorie_belegt(
        db, matrix_id, name
    ):
        raise HTTPException(status_code=409, detail="Kategorie existiert bereits.")

    letzte = (
        await db.execute(
            select(KompetenzKategorie.reihenfolge)
            .where(KompetenzKategorie.matrix_id == matrix_id)
            .order_by(KompetenzKategorie.reihenfolge.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    db.add(
        KompetenzKategorie(
            matrix_id=matrix_id, name=name, reihenfolge=(letzte or 0) + 1
        )
    )
    await db.commit()
    return {"name": name}


@router.put("/matrix/{matrix_id}/kategorie", status_code=204)
async def kategorie_umbenennen(
    matrix_id: int,
    eingabe: KategorieUmbenennen,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine Kategorie in dieser Matrix umbenennen.

    Setzt ``kategorie`` auf allen Qualifikationen dieser Matrix, die ``alt``
    tragen, auf ``neu`` und benennt zusätzlich die deklarierte Kategorie (falls
    vorhanden) um — beide Seiten bleiben synchron. Funktioniert auch für eine
    noch leere, nur deklarierte Kategorie.
    """
    neu = eingabe.neu.strip()
    if not neu:
        raise HTTPException(status_code=400, detail="Neuer Name darf nicht leer sein.")
    if neu == eingabe.alt:
        return
    await _matrix(db, matrix_id)

    zeilen = (
        await db.execute(
            select(KompetenzQualifikation).where(
                KompetenzQualifikation.matrix_id == matrix_id,
                KompetenzQualifikation.kategorie == eingabe.alt,
            )
        )
    ).scalars().all()
    deklariert = await _deklarierte_kategorie(db, matrix_id, eingabe.alt)
    if not zeilen and deklariert is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")

    # Zielname darf nicht schon als andere Kategorie existieren (kein Merge).
    if await _kategorie_belegt(db, matrix_id, neu) or await _deklarierte_kategorie(
        db, matrix_id, neu
    ):
        raise HTTPException(status_code=409, detail="Zielname existiert bereits.")

    for q in zeilen:
        q.kategorie = neu
    if deklariert is not None:
        deklariert.name = neu
    await db.commit()


@router.delete("/matrix/{matrix_id}/kategorie/{name}", status_code=204)
async def kategorie_entfernen(
    matrix_id: int,
    name: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    """Eine deklarierte Kategorie entfernen — nur solange sie leer ist.

    Trägt noch eine Qualifikation die Kategorie, kommt 409: erst die Zeilen
    entfernen oder umkategorisieren.
    """
    deklariert = await _deklarierte_kategorie(db, matrix_id, name)
    if deklariert is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")
    if await _kategorie_belegt(db, matrix_id, name):
        raise HTTPException(
            status_code=409,
            detail="Kategorie enthält Qualifikationen — erst leeren.",
        )
    await db.delete(deklariert)
    await db.commit()
