"""Schulungsbericht-Import — Zuordnung (Vorschau) + Übernahme bearbeiteter Zeilen.

Ablauf:

1. **Vorschau** (:func:`vorschau`): PDF parsen (:mod:`.schulungsbericht_parser`),
   je Zeile ``(Mitarbeitername, Schulungsname, Datum)`` zuordnen:
   * **Mitarbeiter** über den Namen gegen Personio (aktiv + onboarding; beide
     Reihenfolgen). Es gibt keine Personalnummer im Bericht. Treffer liefert
     ``employee_id``; nicht/mehrdeutig → ``None`` (in der Oberfläche korrigierbar).
   * **Schulung** normalisiert gegen den Katalog (nur Info „im Katalog?").
2. **Bearbeiten** in der Oberfläche: Mitarbeiter (Dropdown), Schulungstext und
   Datum sind editierbar.
3. **Übernahme** (:func:`uebernehmen_zeilen`): schreibt die BEARBEITETEN Zeilen —
   je Zeile Durchführungsdatum auf der Teilnahme setzen (Teilnahme anlegen, falls
   fehlend), fehlende Schulung als Katalogeintrag (bereich ``"Sonstige"``) anlegen.
   Dieselbe Semantik wie ``/durchgefuehrt``, nur für beliebige (mitarbeiter, schulung,
   datum)-Tripel.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PersonioEmployee, SchulungKatalog, SchulungTeilnahme
from app.parsing.schulungsbericht_parser import parse_bericht
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
    """Eine zugeordnete Berichtszeile für die Vorschau."""

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


@dataclass
class CommitZeile:
    """Eine bearbeitete Zeile zur Übernahme."""

    employee_id: int
    schulung_name: str
    datum: date


def _mitarbeiter_index(
    mitarbeiter: list[PersonioEmployee],
) -> dict[str, list[PersonioEmployee]]:
    """name-norm (beide Reihenfolgen) → Mitarbeiter (Liste = Mehrdeutigkeit)."""
    idx: dict[str, list[PersonioEmployee]] = {}
    for e in mitarbeiter:
        vor = (e.first_name or "").strip()
        nach = (e.last_name or "").strip()
        for key in {_norm(f"{vor} {nach}"), _norm(f"{nach} {vor}")}:
            if key:
                idx.setdefault(key, [])
                if e not in idx[key]:
                    idx[key].append(e)
    return idx


async def vorschau(db: AsyncSession, daten: bytes) -> BerichtErgebnis:
    """PDF parsen und zuordnen — nichts schreiben."""
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
    kat_idx = {_norm(k.name) for k in katalog}

    erg = BerichtErgebnis(format=fmt, format_label=_FORMAT_LABEL.get(fmt, fmt))
    neue_norms: set[str] = set()

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
        im_katalog = kat_norm in kat_idx
        if not im_katalog:
            neue_norms.add(kat_norm)

        schreibbar = emp is not None and z.datum is not None
        if emp is None:
            erg.ohne_mitarbeiter += 1
        if z.datum is None:
            erg.ohne_datum += 1
        if schreibbar:
            erg.uebernehmbar += 1

        erg.zeilen.append(
            ZeileErgebnis(
                mitarbeiter_name=z.mitarbeiter_name,
                schulung_name=z.schulung_name,
                datum=z.datum,
                mitarbeiter_status=ma_status,
                employee_id=emp.id if emp else None,
                matched_mitarbeiter=(
                    f"{emp.first_name or ''} {emp.last_name or ''}".strip() if emp else None
                ),
                schulung_im_katalog=im_katalog,
                uebernehmbar=schreibbar,
            )
        )

    erg.neue_schulungen = len(neue_norms)
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


async def uebernehmen_zeilen(db: AsyncSession, zeilen: list[CommitZeile]) -> dict:
    """Bearbeitete Zeilen übernehmen: Durchführung setzen, fehlende Schulungen anlegen."""
    if not zeilen:
        return {"eingetragen": 0, "angelegte_schulungen": 0}

    katalog = (await db.execute(select(SchulungKatalog))).scalars().all()
    kat_idx: dict[str, SchulungKatalog] = {}
    for k in katalog:
        kat_idx.setdefault(_norm(k.name), k)

    ids = {z.employee_id for z in zeilen}
    emp_by_id = {
        e.id: e
        for e in (
            await db.execute(
                select(PersonioEmployee).where(PersonioEmployee.id.in_(ids))
            )
        ).scalars().all()
    }

    neu_angelegt: dict[str, SchulungKatalog] = {}
    eingetragen = 0
    for z in zeilen:
        emp = emp_by_id.get(z.employee_id)
        name = (z.schulung_name or "").strip()
        if emp is None or not name:
            continue
        kat_norm = _norm(name)
        eintrag = kat_idx.get(kat_norm) or neu_angelegt.get(kat_norm)
        if eintrag is None:
            eintrag = SchulungKatalog(bereich=AUTO_BEREICH, name=name, sort_order=0)
            db.add(eintrag)
            await db.flush()
            neu_angelegt[kat_norm] = eintrag
        await _durchgefuehrt_setzen(db, emp, eintrag, z.datum)
        eingetragen += 1

    await db.commit()
    return {"eingetragen": eingetragen, "angelegte_schulungen": len(neu_angelegt)}
