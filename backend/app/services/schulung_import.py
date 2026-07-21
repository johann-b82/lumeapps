"""Import der Schulungsübersicht: Personio-Zuordnung, Vorschau, Übernahme.

Die Excel identifiziert Mitarbeiter über die **Personalnummer**. In Personio
liegt sie im Freifeld "DATEV Personalnummer". Dieses Feld wird über sein
*Label* gesucht statt über die instanz-spezifische Feld-ID, damit der Import
nicht bricht, wenn Personio die ID ändert.

Nicht zuordenbare Zeilen werden bewusst NICHT verworfen: sie landen mit
Personalnummer und Name in der Datenbank (``employee_id`` NULL) und werden in
der Vorschau als solche ausgewiesen.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PersonioEmployee, SchulungImport, SchulungKatalog, SchulungTeilnahme
from app.parsing.schulung_parser import ParseResult

#: Label des Personio-Freifelds, das die Personalnummer trägt.
PERSONALNUMMER_LABEL = "datev personalnummer"


@dataclass
class NichtZugeordnet:
    personalnummer: str
    mitarbeiter_name: str | None
    anzahl_teilnahmen: int


@dataclass
class ImportVorschau:
    dateiname: str
    schulungen_gesamt: int
    schulungen_neu: int
    teilnahmen_gesamt: int
    teilnahmen_zugeordnet: int
    bereiche: dict[str, int]
    nicht_zugeordnet: list[NichtZugeordnet]
    warnungen: list[str]


def _personalnummer(raw: object) -> str | None:
    """Personalnummer aus einem Personio-Rohdatensatz lesen (über das Label)."""
    if not isinstance(raw, dict):
        return None
    for feld in (raw.get("attributes") or {}).values():
        if not isinstance(feld, dict):
            continue
        if str(feld.get("label", "")).strip().lower() == PERSONALNUMMER_LABEL:
            wert = feld.get("value")
            text = str(wert).strip() if wert is not None else ""
            return text or None
    return None


async def personio_lookup(db: AsyncSession) -> dict[str, int]:
    """{Personalnummer: personio_employee_id} über alle Mitarbeiter."""
    rows = (await db.execute(select(PersonioEmployee))).scalars().all()
    lookup: dict[str, int] = {}
    for emp in rows:
        nummer = _personalnummer(emp.raw_json)
        if nummer:
            lookup[nummer] = emp.id
    return lookup


def _plus_monate(start: date, monate: int) -> date:
    """Monate addieren; der Tag wird auf den letzten gültigen Tag begrenzt
    (31.01. + 1 Monat → 28./29.02.). Bewusst ohne Zusatz-Abhängigkeit."""
    gesamt = start.month - 1 + monate
    jahr = start.year + gesamt // 12
    monat = gesamt % 12 + 1
    letzter_tag = calendar.monthrange(jahr, monat)[1]
    return date(jahr, monat, min(start.day, letzter_tag))


def _faellig_am(aktuell: date | None, monate: int | None) -> date | None:
    """Nächste Fälligkeit — nur wenn Datum UND Periode bekannt sind."""
    if aktuell is None or not monate:
        return None
    return _plus_monate(aktuell, monate)


def _sammle_nicht_zugeordnet(
    parsed: ParseResult, lookup: dict[str, int]
) -> list[NichtZugeordnet]:
    offen: dict[str, NichtZugeordnet] = {}
    for schulung in parsed.schulungen:
        for t in schulung.teilnahmen:
            if t.personalnummer in lookup:
                continue
            eintrag = offen.get(t.personalnummer)
            if eintrag is None:
                offen[t.personalnummer] = NichtZugeordnet(
                    personalnummer=t.personalnummer,
                    mitarbeiter_name=t.mitarbeiter_name,
                    anzahl_teilnahmen=1,
                )
            else:
                eintrag.anzahl_teilnahmen += 1
    return sorted(offen.values(), key=lambda e: e.personalnummer)


async def baue_vorschau(
    db: AsyncSession, parsed: ParseResult, dateiname: str
) -> ImportVorschau:
    """Analysiert den Import, ohne etwas zu schreiben."""
    lookup = await personio_lookup(db)

    vorhanden = {
        (k.bereich, k.name)
        for k in (await db.execute(select(SchulungKatalog))).scalars().all()
    }
    neu = sum(1 for s in parsed.schulungen if (s.bereich, s.name) not in vorhanden)

    bereiche: dict[str, int] = {}
    zugeordnet = 0
    for s in parsed.schulungen:
        bereiche[s.bereich] = bereiche.get(s.bereich, 0) + 1
        zugeordnet += sum(1 for t in s.teilnahmen if t.personalnummer in lookup)

    return ImportVorschau(
        dateiname=dateiname,
        schulungen_gesamt=len(parsed.schulungen),
        schulungen_neu=neu,
        teilnahmen_gesamt=parsed.teilnahmen_gesamt,
        teilnahmen_zugeordnet=zugeordnet,
        bereiche=bereiche,
        nicht_zugeordnet=_sammle_nicht_zugeordnet(parsed, lookup),
        warnungen=list(parsed.warnungen),
    )


async def uebernehmen(
    db: AsyncSession, parsed: ParseResult, dateiname: str
) -> ImportVorschau:
    """Schreibt Katalog und Teilnahmen (idempotenter Upsert) und protokolliert."""
    vorschau = await baue_vorschau(db, parsed, dateiname)
    lookup = await personio_lookup(db)

    protokoll = SchulungImport(
        dateiname=dateiname,
        schulungen_gesamt=vorschau.schulungen_gesamt,
        teilnahmen_gesamt=vorschau.teilnahmen_gesamt,
        nicht_zugeordnet=len(vorschau.nicht_zugeordnet),
    )
    db.add(protokoll)
    await db.flush()

    katalog = {
        (k.bereich, k.name): k
        for k in (await db.execute(select(SchulungKatalog))).scalars().all()
    }

    for s in parsed.schulungen:
        eintrag = katalog.get((s.bereich, s.name))
        if eintrag is None:
            eintrag = SchulungKatalog(bereich=s.bereich, name=s.name)
            db.add(eintrag)
            katalog[(s.bereich, s.name)] = eintrag
        # Turnus/Reihenfolge folgen immer der zuletzt importierten Datei.
        eintrag.turnus = s.turnus
        eintrag.turnus_monate = s.turnus_monate
        eintrag.sort_order = s.sort_order
        await db.flush()

        zeilen = (
            (
                await db.execute(
                    select(SchulungTeilnahme).where(
                        SchulungTeilnahme.schulung_id == eintrag.id
                    )
                )
            )
            .scalars()
            .all()
        )
        # Zwei Zugriffswege, weil Zeilen aus dem Onboarding nur die Personio-ID
        # tragen (keine Personalnummer). Ohne den zweiten Weg entstünde für
        # dieselbe Person eine zweite Zeile.
        nach_persnr = {z.personalnummer: z for z in zeilen if z.personalnummer}
        nach_employee = {z.employee_id: z for z in zeilen if z.employee_id is not None}

        for t in s.teilnahmen:
            emp_id = lookup.get(t.personalnummer)
            ziel = nach_persnr.get(t.personalnummer) or (
                nach_employee.get(emp_id) if emp_id is not None else None
            )
            if ziel is None:
                ziel = SchulungTeilnahme(
                    schulung_id=eintrag.id, personalnummer=t.personalnummer
                )
                db.add(ziel)
            ziel.employee_id = lookup.get(t.personalnummer)
            ziel.mitarbeiter_name = t.mitarbeiter_name
            ziel.abteilung_kuerzel = t.abteilung_kuerzel
            ziel.initial_datum = t.initial_datum
            ziel.aktuell_datum = t.aktuell_datum
            ziel.naechste_faellig = t.naechste_faellig
            ziel.naechste_faellig_am = _faellig_am(t.aktuell_datum, s.turnus_monate)
            ziel.import_id = protokoll.id

    await db.commit()
    return vorschau
