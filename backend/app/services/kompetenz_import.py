"""Import der Qualifikationsmatrizen (v1.90).

Der Abgleich der Spaltenköpfe mit Personio ist die einzige heikle Stelle: die
Excel-Namen sind handgepflegt und weichen ab ("Fernando Gomes" statt "Fernando
Gomes Ferreira", "Antonio rombator" statt "Trombatore"). Deshalb wird in zwei
Stufen gesucht und alles Unklare gemeldet statt geraten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    KompetenzBewertung,
    KompetenzMatrix,
    KompetenzPerson,
    KompetenzQualifikation,
    PersonioEmployee,
)
from app.parsing.kompetenz_parser import ParsedDatei, ParsedMatrix

#: Spaltenköpfe, die keine Person bezeichnen (unbesetzte Stelle in der Excel).
PLATZHALTER = {"n/a", "na", "-", "tbd"}


@dataclass
class MatrixVorschau:
    blatt: str
    titel: str | None
    qualifikationen: int
    personen: int
    bewertungen: int
    zugeordnet: int
    #: Spaltenköpfe ohne Personio-Treffer (ohne die Platzhalter).
    nicht_zugeordnet: list[str] = field(default_factory=list)
    platzhalter: int = 0


@dataclass
class ImportVorschau:
    dateiname: str
    bereich: str
    matrizen: list[MatrixVorschau] = field(default_factory=list)
    warnungen: list[str] = field(default_factory=list)


def _normalisiere(name: str) -> str:
    """Kleinschreibung, Mehrfach-Leerzeichen weg — für den Namensvergleich."""
    return " ".join(name.split()).lower()


async def _personio_index(db: AsyncSession) -> tuple[dict[str, int], dict[str, list[int]]]:
    """Zwei Suchindizes: exakter Name und einzelne Namensbestandteile.

    Der zweite fängt die Fälle ab, in denen die Excel einen Namensteil weglässt
    oder ergänzt.
    """
    mitarbeiter = (
        (await db.execute(select(PersonioEmployee).where(PersonioEmployee.status == "active")))
        .scalars()
        .all()
    )
    exakt: dict[str, int] = {}
    nach_teilen: dict[str, list[int]] = {}
    for e in mitarbeiter:
        voll = _normalisiere(f"{e.first_name or ''} {e.last_name or ''}")
        if voll:
            exakt.setdefault(voll, e.id)
        for teil in voll.split():
            if len(teil) > 2:
                nach_teilen.setdefault(teil, []).append(e.id)
    return exakt, nach_teilen


def _finde_person(
    name: str, exakt: dict[str, int], nach_teilen: dict[str, list[int]]
) -> int | None:
    """Personio-ID zum Spaltenkopf, oder None.

    Stufe 1: exakter Name. Stufe 2: alle Namensteile der Excel zeigen auf
    dieselbe Person — deckt "Fernando Gomes" -> "Fernando Gomes Ferreira" ab.
    Bleibt es mehrdeutig, wird bewusst nicht zugeordnet.
    """
    norm = _normalisiere(name)
    if norm in exakt:
        return exakt[norm]

    teile = [t for t in norm.split() if len(t) > 2]
    if not teile:
        return None
    kandidaten: set[int] | None = None
    for t in teile:
        treffer = set(nach_teilen.get(t, []))
        if not treffer:
            return None  # ein Bestandteil passt nirgends -> kein Treffer
        kandidaten = treffer if kandidaten is None else (kandidaten & treffer)
        if not kandidaten:
            return None
    return next(iter(kandidaten)) if kandidaten and len(kandidaten) == 1 else None


async def _analysiere(
    db: AsyncSession, matrix: ParsedMatrix
) -> tuple[MatrixVorschau, list[int | None]]:
    """Kennzahlen einer Matrix samt Personio-Zuordnung je Spalte."""
    exakt, nach_teilen = await _personio_index(db)

    zuordnung: list[int | None] = []
    nicht_zugeordnet: list[str] = []
    platzhalter = 0
    for name in matrix.personen:
        if _normalisiere(name) in PLATZHALTER:
            platzhalter += 1
            zuordnung.append(None)
            continue
        treffer = _finde_person(name, exakt, nach_teilen)
        zuordnung.append(treffer)
        if treffer is None:
            nicht_zugeordnet.append(name)

    return (
        MatrixVorschau(
            blatt=matrix.blatt,
            titel=matrix.titel,
            qualifikationen=len(matrix.qualifikationen),
            personen=len(matrix.personen),
            bewertungen=sum(len(q.bewertungen) for q in matrix.qualifikationen),
            zugeordnet=sum(1 for z in zuordnung if z is not None),
            nicht_zugeordnet=nicht_zugeordnet,
            platzhalter=platzhalter,
        ),
        zuordnung,
    )


async def baue_vorschau(db: AsyncSession, parsed: ParsedDatei, bereich: str) -> ImportVorschau:
    """Analysieren, ohne zu schreiben."""
    vorschau = ImportVorschau(
        dateiname=parsed.dateiname, bereich=bereich, warnungen=list(parsed.warnungen)
    )
    for matrix in parsed.matrizen:
        kennzahlen, _ = await _analysiere(db, matrix)
        vorschau.matrizen.append(kennzahlen)
    return vorschau


async def uebernehmen(db: AsyncSession, parsed: ParsedDatei, bereich: str) -> ImportVorschau:
    """Matrizen übernehmen — je (Bereich, Blatt) ersetzend.

    Ersetzen statt Zusammenführen: die Excel ist die führende Quelle, und eine
    dort gelöschte Zeile soll auch hier verschwinden. Die Kaskade räumt
    Qualifikationen, Personen und Bewertungen mit ab.
    """
    vorschau = ImportVorschau(
        dateiname=parsed.dateiname, bereich=bereich, warnungen=list(parsed.warnungen)
    )

    for matrix in parsed.matrizen:
        kennzahlen, zuordnung = await _analysiere(db, matrix)
        vorschau.matrizen.append(kennzahlen)

        alt = (
            await db.execute(
                select(KompetenzMatrix).where(
                    KompetenzMatrix.bereich == bereich,
                    KompetenzMatrix.blatt == matrix.blatt,
                )
            )
        ).scalar_one_or_none()
        if alt is not None:
            await db.delete(alt)
            await db.flush()

        neu = KompetenzMatrix(
            bereich=bereich,
            blatt=matrix.blatt,
            titel=matrix.titel,
            stand=matrix.stand,
            dateiname=parsed.dateiname,
            importiert_am=datetime.now(timezone.utc),
        )
        db.add(neu)
        await db.flush()

        personen = [
            KompetenzPerson(
                matrix_id=neu.id, name=name, employee_id=zuordnung[i], reihenfolge=i
            )
            for i, name in enumerate(matrix.personen)
        ]
        db.add_all(personen)

        qualifikationen = [
            KompetenzQualifikation(
                matrix_id=neu.id,
                nr=q.nr,
                kategorie=q.kategorie,
                bezeichnung=q.bezeichnung,
                reihenfolge=q.reihenfolge,
            )
            for q in matrix.qualifikationen
        ]
        db.add_all(qualifikationen)
        await db.flush()

        db.add_all(
            [
                KompetenzBewertung(
                    qualifikation_id=qualifikationen[i].id,
                    person_id=personen[b.person_index].id,
                    anforderungslevel=b.anforderungslevel,
                    erfuellungsgrad=b.erfuellungsgrad,
                )
                for i, q in enumerate(matrix.qualifikationen)
                for b in q.bewertungen
            ]
        )

    await db.commit()
    return vorschau
