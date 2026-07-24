"""Onboarding-Paket: Einarbeitungsplan + Schulungsübersicht als ein PDF (v1.92).

Beide Formblätter landen als zwei Blätter EINER Arbeitsmappe; LibreOffice
konvertiert sie in einem Rutsch zu einem mehrseitigen PDF. So bleibt es ein
Dokument zur Übergabe an den Vorgesetzten — ohne eine zusätzliche
PDF-Merge-Abhängigkeit.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO

from openpyxl import Workbook

from app.services import einarbeitung_pdf, schulungsuebersicht_pdf
from app.services.einarbeitung_pdf import EinarbeitungZeile
from app.services.maintenance_pdf import convert_xlsx_to_pdf
from app.services.pdf_logo import LogoBild
from app.services.schulungsuebersicht_pdf import UebersichtZeile


async def erzeuge_onboarding_paket_pdf(
    name: str,
    stelle: str,
    beginn: date | None,
    einarbeitung: list[EinarbeitungZeile],
    schulungen: list[UebersichtZeile],
    logo: LogoBild | None = None,
) -> bytes:
    wb = Workbook()
    # Blatt 1: Einarbeitungsplan (nutzt das Standard-Blatt der Mappe).
    einarbeitung_pdf.fuelle_blatt(wb.active, name, stelle, beginn, einarbeitung, logo)
    # Blatt 2: Schulungsübersicht.
    schulungsuebersicht_pdf.fuelle_blatt(
        wb.create_sheet(), name, stelle, schulungen, logo=logo
    )

    puffer = BytesIO()
    wb.save(puffer)
    return await convert_xlsx_to_pdf(puffer.getvalue())
