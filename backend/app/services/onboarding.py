"""Onboarding — Schulungsplan aus der Anforderungsmatrix ableiten.

Schritte 4/5 des Prozesskonzepts: für eine Person ermitteln, welche Schulungen
laut Anforderungsmatrix Pflicht sind (Soll), was davon bereits vorliegt (Ist),
und die fehlenden als offene Zeilen anlegen.

Die Matrix kennt zwei Ebenen:

* ``personio`` — greift direkt über ``personio_employees.department``.
* ``kuerzel``  — greift über die Zuordnung Position → Abteilungskürzel
  (``schulung_rolle``). Ohne Eintrag dort bleibt die feine Ebene für diese
  Person wirkungslos; das wird als ``kuerzel_fehlt`` gemeldet statt still
  übergangen, weil sonst unbemerkt zu wenige Pflichtschulungen entstünden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PersonioEmployee,
    SchulungKatalog,
    SchulungPflicht,
    SchulungRolle,
    SchulungTeilnahme,
)
from app.services.schulung_import import _personalnummer


def normalisiere_position(text: str | None) -> str:
    """Kleinschreibung + Whitespace zusammenfassen — Personio ist uneinheitlich."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class SollSchulung:
    schulung_id: int
    bereich: str
    name: str
    turnus: str | None
    #: Über welche Ebene die Pflicht entsteht ("personio" / "kuerzel").
    quelle: str
    abteilung: str
    #: True, wenn die Person dazu bereits einen Eintrag hat.
    vorhanden: bool


@dataclass
class SchulungsplanErgebnis:
    personalnummer: str | None
    name: str
    position: str | None
    abteilung: str | None
    abteilung_kuerzel: str | None
    #: Position ist in schulung_rolle nicht zugeordnet -> feine Ebene greift nicht.
    kuerzel_fehlt: bool
    soll: list[SollSchulung] = field(default_factory=list)

    @property
    def fehlend(self) -> list[SollSchulung]:
        return [s for s in self.soll if not s.vorhanden]


async def _kuerzel_fuer_position(db: AsyncSession, position: str | None) -> str | None:
    norm = normalisiere_position(position)
    if not norm:
        return None
    treffer = (
        await db.execute(
            select(SchulungRolle).where(SchulungRolle.position_norm == norm)
        )
    ).scalar_one_or_none()
    return treffer.abteilung_kuerzel if treffer else None


async def schulungsplan(
    db: AsyncSession, employee: PersonioEmployee
) -> SchulungsplanErgebnis:
    """Soll/Ist für eine Person ermitteln (schreibt nichts)."""
    persnr = _personalnummer(employee.raw_json)
    kuerzel = await _kuerzel_fuer_position(db, employee.position)

    ergebnis = SchulungsplanErgebnis(
        personalnummer=persnr,
        name=" ".join(x for x in (employee.first_name, employee.last_name) if x).strip()
        or f"#{employee.id}",
        position=employee.position,
        abteilung=employee.department,
        abteilung_kuerzel=kuerzel,
        kuerzel_fehlt=kuerzel is None and bool(normalisiere_position(employee.position)),
    )

    # Passende Regeln beider Ebenen einsammeln.
    bedingungen = []
    if employee.department:
        bedingungen.append(("personio", employee.department.strip()))
    if kuerzel:
        bedingungen.append(("kuerzel", kuerzel))
    if not bedingungen:
        return ergebnis

    regeln = (
        await db.execute(
            select(SchulungPflicht, SchulungKatalog)
            .join(SchulungKatalog, SchulungKatalog.id == SchulungPflicht.schulung_id)
            .where(
                or_(
                    *[
                        and_(
                            SchulungPflicht.ebene == e,
                            SchulungPflicht.abteilung == a,
                        )
                        for e, a in bedingungen
                    ]
                )
            )
        )
    ).all()

    # Was hat die Person schon? Über beide Identitäten suchen: die Personio-ID
    # (immer vorhanden) und die Personalnummer (nur bei Excel-Historie).
    bedingung_person = [SchulungTeilnahme.employee_id == employee.id]
    if persnr:
        bedingung_person.append(SchulungTeilnahme.personalnummer == persnr)
    vorhandene = {
        row[0]
        for row in (
            await db.execute(
                select(SchulungTeilnahme.schulung_id).where(or_(*bedingung_person))
            )
        ).all()
    }

    gesehen: set[int] = set()
    for pflicht, katalog in regeln:
        if katalog.id in gesehen:
            continue  # Eine Schulung kann über beide Ebenen Pflicht sein.
        gesehen.add(katalog.id)
        ergebnis.soll.append(
            SollSchulung(
                schulung_id=katalog.id,
                bereich=katalog.bereich,
                name=katalog.name,
                turnus=katalog.turnus,
                quelle=pflicht.ebene,
                abteilung=pflicht.abteilung,
                vorhanden=katalog.id in vorhandene,
            )
        )
    ergebnis.soll.sort(key=lambda s: (s.bereich, s.name))
    return ergebnis


async def plan_anlegen(
    db: AsyncSession, employee: PersonioEmployee
) -> SchulungsplanErgebnis:
    """Fehlende Pflichtschulungen als offene Zeilen anlegen (Schritt 5).

    "Offen" heißt: Zeile ohne Datumsangaben. Damit taucht die Person in der
    Mitarbeiterübersicht auf, ohne eine Fälligkeit vorzutäuschen.
    """
    plan = await schulungsplan(db, employee)

    # Schlüssel ist die Personio-ID; die Personalnummer wird mitgeführt, wenn
    # sie gepflegt ist (verbindet die Zeile mit der Excel-Historie).
    for s in plan.fehlend:
        db.add(
            SchulungTeilnahme(
                schulung_id=s.schulung_id,
                employee_id=employee.id,
                personalnummer=plan.personalnummer,
                mitarbeiter_name=plan.name,
                abteilung_kuerzel=plan.abteilung_kuerzel,
            )
        )
    await db.commit()
    return await schulungsplan(db, employee)
