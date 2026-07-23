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
from app.models import KompetenzMatrix, KompetenzQualifikation
from app.models.kompetenz import ANFORDERUNGSLEVEL, KOMPETENZ_BEREICHE
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
    #: Legende der Anforderungslevel (Stufe -> Bedeutung).
    level_legende: dict[int, str]
    personen: list[PersonRead]
    qualifikationen: list[QualifikationRead]


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

    personen = sorted(matrix.personen, key=lambda p: p.reihenfolge)
    return MatrixRead(
        id=matrix.id,
        bereich=matrix.bereich,
        blatt=matrix.blatt,
        titel=matrix.titel,
        stand=matrix.stand,
        importiert_am=matrix.importiert_am,
        level_legende=ANFORDERUNGSLEVEL,
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
