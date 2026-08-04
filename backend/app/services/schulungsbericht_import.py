"""Schulungsbericht-Import — Zuordnung + Vorschau/Übernahme.

Nimmt die vom :mod:`app.parsing.schulungsbericht_parser` extrahierten Zeilen
``(Mitarbeitername, Schulungsname, Datum)`` und ordnet sie zu:

* **Mitarbeiter** über den Namen gegen Personio (aktiv + onboarding). Es gibt
  keine Personalnummer im Bericht, daher Name-Matching (beide Reihenfolgen).
  Nicht/mehrdeutig Gefundene werden NICHT geschrieben, sondern in der Vorschau
  ausgewiesen.
* **Schulung** über den Namen gegen den Schulungskatalog (normalisiert). Fehlt
  sie, wird sie bei der Übernahme automatisch als Katalogeintrag angelegt
  (bereich ``"Sonstige"``) — bewusste Produktentscheidung.

Übernahme setzt je Treffer das Durchführungsdatum auf der Teilnahme (legt die
Teilnahme an, falls die Person die Schulung noch nicht hat) — dieselbe Semantik
wie ``/durchgefuehrt`` (Formblatt-68-Ablauf), nur namensbasiert und für beide
Formblätter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PersonioEmployee, SchulungKatalog, SchulungTeilnahme
from app.parsing.schulungsbericht_parser import BerichtZeile, parse_bericht
from app.services.schulung_import import _faellig_am, _personalnummer

#: bereich für automatisch angelegte Katalogeinträge (aus einem Bericht).
AUTO_BEREICH = "Sonstige"

_FORMAT_LABEL = {
    "fbl68": "Schulungsnachweis (Formblatt 68)",
    "fbl71": "Schulungsübersicht (Formblatt 71)",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


@dataclass
class ZeileErgebnis:
    """Eine zugeordnete Berichtszeile für Vorschau/Übernahme."""

    mitarbeiter_name: str
    schulung_name: str
    datum: date | None
    #: "ok" | "nicht_gefunden" | "mehrdeutig"
    mitarbeiter_status: str
    matched_mitarbeiter: str | None  # aufgelöster Personio-Name
    schulung_im_katalog: bool
    #: True = wird (bzw. wurde) geschrieben.
    uebernommen: bool


@dataclass
class BerichtErgebnis:
    format: str
    format_label: str
    zeilen: list[ZeileErgebnis] = field(default_factory=list)
    gesamt: int = 0
    uebernehmbar: int = 0
    ohne_mitarbeiter: int = 0
    ohne_datum: int = 0
    neue_schulungen: int = 0
    eingetragen: int = 0  # nur nach Übernahme


def _mitarbeiter_index(mitarbeiter: list[PersonioEmployee]) -> dict[str, list[PersonioEmployee]]:
    """name-norm (beide Reihenfolgen) → Mitarbeiter (Liste = Mehrdeutigkeit)."""
    idx: dict[str, list[PersonioEmployee]] = {}
    for e in mitarbeiter:
        vor = (e.first_name or "").strip()
        nach = (e.last_name or "").strip()
        varianten = {_norm(f"{vor} {nach}"), _norm(f"{nach} {vor}")}
        for key in varianten:
            if key:
                idx.setdefault(key, [])
                if e not in idx[key]:
                    idx[key].append(e)
    return idx


async def _auswerten(db: AsyncSession, daten: bytes, *, uebernehmen: bool) -> BerichtErgebnis:
    fmt, zeilen = parse_bericht(daten)

    mitarbeiter = (
        await db.execute(
            select(PersonioEmployee).where(
                PersonioEmployee.status.in_(("active", "onboarding"))
            )
        )
    ).scalars().all()
    ma_idx = _mitarbeiter_index(mitarbeiter)

    katalog = (await db.execute(select(SchulungKatalog))).scalars().all()
    kat_idx: dict[str, SchulungKatalog] = {}
    for k in katalog:
        kat_idx.setdefault(_norm(k.name), k)

    #: in DIESEM Lauf neu angelegte Katalogeinträge (norm → Objekt), damit ein
    #: mehrfach vorkommender Name nur einmal angelegt wird.
    neu_angelegt: dict[str, SchulungKatalog] = {}
    #: Schulungsnamen (norm), die NICHT im Bestandskatalog waren — für die Zählung.
    neue_norms: set[str] = set()

    erg = BerichtErgebnis(format=fmt, format_label=_FORMAT_LABEL.get(fmt, fmt))

    for z in zeilen:
        erg.gesamt += 1
        kandidaten = ma_idx.get(_norm(z.mitarbeiter_name), [])
        if len(kandidaten) == 1:
            ma_status, emp = "ok", kandidaten[0]
        elif len(kandidaten) == 0:
            ma_status, emp = "nicht_gefunden", None
        else:
            ma_status, emp = "mehrdeutig", None

        kat_norm = _norm(z.schulung_name)
        im_katalog = kat_norm in kat_idx  # im Bestands-Katalog?
        if not im_katalog:
            neue_norms.add(kat_norm)

        schreibbar = emp is not None and z.datum is not None
        if emp is None:
            erg.ohne_mitarbeiter += 1
        if z.datum is None:
            erg.ohne_datum += 1
        if schreibbar:
            erg.uebernehmbar += 1
            if uebernehmen:
                eintrag = kat_idx.get(kat_norm) or neu_angelegt.get(kat_norm)
                if eintrag is None:  # Katalogeintrag anlegen
                    eintrag = SchulungKatalog(
                        bereich=AUTO_BEREICH, name=z.schulung_name.strip(), sort_order=0
                    )
                    db.add(eintrag)
                    await db.flush()  # id + für Folgezeilen sichtbar
                    neu_angelegt[kat_norm] = eintrag
                await _durchgefuehrt_setzen(db, emp, eintrag, z.datum)
                erg.eingetragen += 1

        erg.zeilen.append(
            ZeileErgebnis(
                mitarbeiter_name=z.mitarbeiter_name,
                schulung_name=z.schulung_name,
                datum=z.datum,
                mitarbeiter_status=ma_status,
                matched_mitarbeiter=(
                    f"{emp.first_name or ''} {emp.last_name or ''}".strip() if emp else None
                ),
                schulung_im_katalog=im_katalog,
                uebernommen=schreibbar,
            )
        )

    erg.neue_schulungen = len(neue_norms)
    if uebernehmen:
        await db.commit()
    return erg


async def _durchgefuehrt_setzen(
    db: AsyncSession, emp: PersonioEmployee, katalog: SchulungKatalog, datum: date
) -> None:
    """Teilnahme finden/anlegen und Durchführungsdatum setzen (wie /durchgefuehrt)."""
    persnr = _personalnummer(emp.raw_json)
    conds = [SchulungTeilnahme.employee_id == emp.id]
    if persnr:
        conds.append(SchulungTeilnahme.personalnummer == persnr)
    zeile = (
        await db.execute(
            select(SchulungTeilnahme).where(
                SchulungTeilnahme.schulung_id == katalog.id, or_(*conds)
            )
        )
    ).scalars().first()
    if zeile is None:
        name = f"{emp.first_name or ''} {emp.last_name or ''}".strip() or f"#{emp.id}"
        zeile = SchulungTeilnahme(
            schulung_id=katalog.id,
            mitarbeiter_name=name,
            employee_id=emp.id,
            personalnummer=persnr,
        )
        db.add(zeile)
    zeile.aktuell_datum = datum
    if zeile.initial_datum is None:
        zeile.initial_datum = datum
    zeile.naechste_faellig_am = _faellig_am(datum, katalog.turnus_monate)


async def vorschau(db: AsyncSession, daten: bytes) -> BerichtErgebnis:
    """Nur auswerten/zuordnen — nichts schreiben."""
    return await _auswerten(db, daten, uebernehmen=False)


async def uebernehmen(db: AsyncSession, daten: bytes) -> BerichtErgebnis:
    """Auswerten UND schreiben (Durchführungsdaten + fehlende Katalogeinträge)."""
    return await _auswerten(db, daten, uebernehmen=True)
