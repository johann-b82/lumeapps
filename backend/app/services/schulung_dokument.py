"""Schulungsvorgang: anlegen (Formblatt 71 + QR + Layout) und Scan verarbeiten.

Spiegelt ``einarbeitung_dokument`` und teilt sich die Kernservices: Scan-Prüfung
(``einarbeitung_pruefung``) und Datei-Ablage (``directus_files``). Die
Schulungszeilen kommen aus dem bestehenden Soll-Schulungsplan des Mitarbeiters.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SchulungDokument
from app.services.directus_files import datei_laden, datei_speichern
from app.services.einarbeitung_pruefung import feld_pruefung, qr_dekodieren, scan_rastern
from app.services.pdf_logo import LogoBild
from app.services.schulungsuebersicht_pdf import (
    UebersichtZeile,
    dateiname,
    erzeuge_schulung_vorgang_pdf,
)


def neue_doc_uid() -> str:
    """Kurzer, eindeutiger Token für QR + Zuordnung (Schulung)."""
    return "SCH-" + secrets.token_hex(5).upper()


async def vorgang_anlegen(
    db: AsyncSession,
    *,
    employee_id: int | None,
    name: str,
    funktion: str,
    zeilen: list[UebersichtZeile],
    logo: LogoBild | None,
) -> SchulungDokument:
    """Schulungsvorgang persistieren: Formblatt 71 mit QR/Marken erzeugen + ablegen."""
    doc_uid = neue_doc_uid()
    pdf, layout = await erzeuge_schulung_vorgang_pdf(name, funktion, zeilen, doc_uid, logo=logo)
    pdf_ref = await datei_speichern(f"{dateiname(name, date.today())}.pdf", pdf)

    dok = SchulungDokument(
        doc_uid=doc_uid,
        employee_id=employee_id,
        mitarbeiter_name=name,
        funktion=funktion or None,
        pdf_uuid=pdf_ref,
        feld_layout=layout,
        status="erstellt",
    )
    db.add(dok)
    await db.commit()
    await db.refresh(dok)
    return dok


async def scan_verarbeiten(
    db: AsyncSession, scan_bytes: bytes, ist_pdf: bool
) -> tuple[SchulungDokument | None, dict]:
    """Hochgeladenen Scan über den QR zuordnen, prüfen und am Vorgang speichern."""
    scan_img = await scan_rastern(scan_bytes, ist_pdf)
    treffer = qr_dekodieren(scan_img)
    if treffer is None:
        return None, {"qr_ok": False, "grund": "kein_qr"}

    dok = (
        await db.execute(
            select(SchulungDokument).where(SchulungDokument.doc_uid == treffer.doc_uid)
        )
    ).scalar_one_or_none()
    if dok is None:
        return None, {"qr_ok": True, "grund": "unbekannt", "doc_uid": treffer.doc_uid}

    blank_img = await scan_rastern(await datei_laden(dok.pdf_uuid), True)
    ergebnis = feld_pruefung(scan_img, dok.feld_layout or {}, referenz=blank_img)

    endung = "pdf" if ist_pdf else "png"
    mime = "application/pdf" if ist_pdf else "image/png"
    dok.scan_uuid = await datei_speichern(f"scan_{dok.doc_uid}.{endung}", scan_bytes, mime)
    dok.pruef_ergebnis = ergebnis
    dok.vollstaendig = bool(ergebnis.get("vollstaendig"))
    if dok.zurueck_am is None:
        dok.zurueck_am = datetime.now(timezone.utc)
        if dok.status in ("erstellt", "uebergeben"):
            dok.status = "zurueck"

    await db.commit()
    await db.refresh(dok)
    return dok, ergebnis
