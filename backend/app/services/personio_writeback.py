"""Personio-Rückschreiben — Schulungs-/Kompetenznachweise ins Mitarbeiterprofil.

**INERT bis Freischaltung.** Nach jedem Schulungs- oder Kompetenz-Update wird ein
kurzer Nachweis (PDF) in die Personio-Dokumente des Mitarbeiters hochgeladen —
aber nur, wenn ``AppSettings.personio_writeback_enabled`` an ist UND eine
Dokumentenkategorie hinterlegt ist. Solange das nicht der Fall ist (Default), sind
alle Aufrufe stille No-Ops.

Voraussetzungen für den echten Push (extern zu erledigen):
* Personio-App braucht **Schreib-Scopes** (Dokumente lesen+schreiben) — die aktuell
  hinterlegten Credentials sind read-only. Bis dahin scheitert der Upload (wird
  geloggt, blockiert aber nie das lokale Update).
* Eine **Dokumentenkategorie** in Personio (ID in
  ``personio_writeback_kategorie_id``).

Design: Die Einstiegspunkte öffnen ihre EIGENE DB-Session (werden als
``asyncio.create_task`` fire-and-forget nach dem Commit gestartet) und werfen NIE —
ein Personio-Fehler darf das lokale Schreiben nicht beeinträchtigen.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import (
    AppSettings,
    KompetenzBewertung,
    KompetenzPerson,
    KompetenzQualifikation,
    PersonioEmployee,
    SchulungKatalog,
    SchulungTeilnahme,
)
from app.security.fernet import decrypt_credential
from app.services.personio_client import PERSONIO_BASE_URL

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Minimaler, abhängigkeitsfreier PDF-Generator (kein reportlab/fpdf im Image)
# ---------------------------------------------------------------------------

def _einfaches_pdf(titel: str, zeilen: list[str]) -> bytes:
    """Einseitiges PDF (A4) mit Titel + Textzeilen. Bewusst schlicht."""

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stroeme: list[str] = [f"BT /F1 16 Tf 50 800 Td ({esc(titel)}) Tj ET"]
    y = 770
    for zeile in zeilen:
        stroeme.append(f"BT /F1 10 Tf 50 {y} Td ({esc(zeile)}) Tj ET")
        y -= 15
        if y < 40:
            break
    inhalt = "\n".join(stroeme).encode("latin-1", "replace")

    objekte = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(inhalt), inhalt),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for i, obj in enumerate(objekte, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objekte) + 1,
        xref,
    )
    return out


# ---------------------------------------------------------------------------
# Konfiguration + Personio-Upload
# ---------------------------------------------------------------------------

async def _konfig(session) -> tuple[str, str, str] | None:
    """(client_id, client_secret, kategorie_id) — oder None, wenn inert/unkonfiguriert."""
    row = (
        await session.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()
    if (
        row is None
        or not row.personio_writeback_enabled
        or not row.personio_writeback_kategorie_id
        or not row.personio_client_id_enc
        or not row.personio_client_secret_enc
    ):
        return None
    return (
        decrypt_credential(row.personio_client_id_enc),
        decrypt_credential(row.personio_client_secret_enc),
        row.personio_writeback_kategorie_id,
    )


async def _push(
    cid: str,
    csec: str,
    kategorie_id: str,
    employee_id: int,
    titel: str,
    dateiname: str,
    pdf: bytes,
) -> None:
    """Dokument in die Personio-Dokumente des Mitarbeiters hochladen."""
    async with httpx.AsyncClient(base_url=PERSONIO_BASE_URL, timeout=60) as client:
        auth = await client.post("/auth", json={"client_id": cid, "client_secret": csec})
        auth.raise_for_status()
        token = auth.json()["data"]["token"]
        resp = await client.post(
            "/company/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "employee_id": str(employee_id),
                "document_category_id": str(kategorie_id),
                "title": titel,
            },
            files={"file": (dateiname, pdf, "application/pdf")},
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Inhalte je Mitarbeiter
# ---------------------------------------------------------------------------

async def _schulungszeilen(session, employee_id: int) -> list[str]:
    rows = (
        await session.execute(
            select(SchulungTeilnahme, SchulungKatalog)
            .join(SchulungKatalog, SchulungKatalog.id == SchulungTeilnahme.schulung_id)
            .where(SchulungTeilnahme.employee_id == employee_id)
        )
    ).all()
    zeilen = []
    for t, k in sorted(rows, key=lambda r: r[1].name.lower()):
        wann = t.aktuell_datum.strftime("%d.%m.%Y") if t.aktuell_datum else "offen"
        zeilen.append(f"{k.name}: {wann}")
    return zeilen or ["(keine Schulungen hinterlegt)"]


async def _kompetenzzeilen(session, employee_id: int) -> list[str]:
    personen = (
        await session.execute(
            select(KompetenzPerson).where(KompetenzPerson.employee_id == employee_id)
        )
    ).scalars().all()
    zeilen = []
    for p in personen:
        bews = (
            await session.execute(
                select(KompetenzBewertung, KompetenzQualifikation)
                .join(
                    KompetenzQualifikation,
                    KompetenzQualifikation.id == KompetenzBewertung.qualifikation_id,
                )
                .where(KompetenzBewertung.person_id == p.id)
            )
        ).all()
        for b, q in sorted(bews, key=lambda r: (r[1].bezeichnung or "").lower()):
            al = b.anforderungslevel if b.anforderungslevel is not None else "-"
            eg = b.erfuellungsgrad if b.erfuellungsgrad is not None else "-"
            zeilen.append(f"{q.bezeichnung}: AL {al} / Erfüllung {eg}%")
    return zeilen or ["(keine Bewertungen hinterlegt)"]


# ---------------------------------------------------------------------------
# Einstiegspunkte — fire-and-forget, werfen NIE
# ---------------------------------------------------------------------------

def _name(emp: PersonioEmployee) -> str:
    return f"{emp.first_name or ''} {emp.last_name or ''}".strip() or f"#{emp.id}"


async def nach_schulung_update(employee_id: int | None) -> None:
    """Schulungs-Nachweis ins Personio-Profil (No-Op wenn inert/extern/unbekannt)."""
    if employee_id is None or employee_id <= 0:
        return  # None oder externer (negativer) Mitarbeiter → kein Personio-Profil
    try:
        async with AsyncSessionLocal() as session:
            konfig = await _konfig(session)
            if konfig is None:
                return  # inert / nicht konfiguriert
            cid, csec, kat = konfig
            emp = (
                await session.execute(
                    select(PersonioEmployee).where(PersonioEmployee.id == employee_id)
                )
            ).scalar_one_or_none()
            if emp is None:
                return
            name = _name(emp)
            pdf = _einfaches_pdf(
                f"Schulungsübersicht — {name}", await _schulungszeilen(session, employee_id)
            )
            await _push(
                cid, csec, kat, employee_id,
                f"Schulungsübersicht {name}",
                f"Schulungsuebersicht_{employee_id}.pdf",
                pdf,
            )
    except Exception:  # noqa: BLE001 - darf das lokale Update nie beeinträchtigen
        log.warning("personio_writeback (Schulung) fehlgeschlagen emp=%s", employee_id, exc_info=True)


async def nach_kompetenz_update(employee_id: int | None) -> None:
    """Kompetenz-Nachweis ins Personio-Profil (No-Op wenn inert/unbekannt)."""
    if employee_id is None or employee_id <= 0:
        return
    try:
        async with AsyncSessionLocal() as session:
            konfig = await _konfig(session)
            if konfig is None:
                return
            cid, csec, kat = konfig
            emp = (
                await session.execute(
                    select(PersonioEmployee).where(PersonioEmployee.id == employee_id)
                )
            ).scalar_one_or_none()
            if emp is None:
                return
            name = _name(emp)
            pdf = _einfaches_pdf(
                f"Qualifikationsübersicht — {name}",
                await _kompetenzzeilen(session, employee_id),
            )
            await _push(
                cid, csec, kat, employee_id,
                f"Qualifikationsübersicht {name}",
                f"Qualifikationsuebersicht_{employee_id}.pdf",
                pdf,
            )
    except Exception:  # noqa: BLE001
        log.warning("personio_writeback (Kompetenz) fehlgeschlagen emp=%s", employee_id, exc_info=True)
