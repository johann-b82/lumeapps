"""Schulungsplan-Paket: Fbl. 71 (Übersicht) + je Schulung ein vorausgefülltes
Fbl. 68 (Schulungsnachweis) als EIN mehrseitiges PDF.

Wie das Onboarding-Paket landen alle Formblätter als Blätter EINER Arbeitsmappe;
LibreOffice konvertiert sie in einem Rutsch — ohne PDF-Merge-Abhängigkeit. So
druckt der Schulungsplan direkt mit allen Nachweisen aus. Jedes Fbl. 68 trägt den
QR ``doc_uid#index``, damit der ausgefüllte Nachweis später automatisch der
Schulung zugeordnet wird.
"""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.services.maintenance_pdf import convert_xlsx_to_pdf
from app.services.pdf_logo import LogoBild
from app.services.schulungsprotokoll_pdf import fuelle_blatt as fuelle_nachweis_blatt
from app.services.schulungsuebersicht_pdf import UebersichtZeile, fuelle_vorgang_blatt


async def erzeuge_schulung_paket_pdf(
    name: str,
    funktion: str,
    schulungen: list[dict],
    doc_uid: str,
    logo: LogoBild | None = None,
) -> tuple[bytes, dict]:
    """Fbl. 71 (Blatt 1) + je Schulung ein Fbl. 68 (Blätter 2..N) als ein PDF.

    Gibt zusätzlich das Feld-Layout des Fbl. 71 (Blatt 1) zurück — dieselbe Mappe
    liefert damit sowohl das Druck-Bündel als auch die Scan-Prüf-Geometrie in
    einem LibreOffice-Durchlauf.
    """
    wb = Workbook()
    # Blatt 1: Schulungsübersicht als Vorgang (QR + Passermarken).
    zeilen = [UebersichtZeile(bezeichnung=s["name"]) for s in schulungen]
    layout = fuelle_vorgang_blatt(wb.active, name, funktion, zeilen, doc_uid, logo=logo)
    # Blätter 2..N: je Schulung ein vorausgefülltes Fbl. 68 mit QR doc_uid#index.
    for i, s in enumerate(schulungen):
        fuelle_nachweis_blatt(
            wb.create_sheet(),
            s["name"],
            [name],
            s.get("trainer") or "",
            True,
            logo,
            f"{doc_uid}#{i}",
        )

    puffer = BytesIO()
    wb.save(puffer)
    return await convert_xlsx_to_pdf(puffer.getvalue()), layout
