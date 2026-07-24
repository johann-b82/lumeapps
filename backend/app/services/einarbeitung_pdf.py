"""Einarbeitungsbogen je Person als PDF (v1.92).

Bildet die Vorlage "Einarbeitungsplan" nach: Kopf mit Name/Stelle/Beginn,
feste Einleitung (Regeln + Ziele), die Inhalts-Tabelle (Abteilung ·
Ansprechpartner · Inhalt · Wann? · Erledigt/Unterschrift) und der Fußblock
(weiterer Schulungsbedarf, Laufweg).

Aufbau wie die Schulungsübersicht: openpyxl schreibt eine .xlsx, LibreOffice
headless macht daraus ein PDF.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.page import PageMargins

from app.services.maintenance_pdf import convert_xlsx_to_pdf
from app.services.pdf_logo import LogoBild, bild_einsetzen

FORMBLATT = "Einarbeitungsplan"

#: Spalten wie in der Vorlage: A ist eine schmale Gutter-Spalte, dann B=Abteilung,
#: C=Ansprechpartner, D:F=Inhalt, G=Wann?, H=Erledigt/Unterschrift.
SP_ABT, SP_PART, SP_INHALT, SP_WANN, SP_ERLEDIGT = 2, 3, 4, 7, 8

_REGELN = [
    "Jeder neue Mitarbeiter wird anhand eines Einarbeitungsplans systematisch eingelernt.",
    "Die einzelnen Einarbeitungsschritte werden vom Mitarbeiter dokumentiert.",
    "Innerhalb der ersten 4 Wochen findet ein Feedbackgespräch statt.",
]
_ZIELE = (
    "Ziel der Einarbeitung ist die gezielte Unterstützung der Abteilung durch den "
    "Aufbau der notwendigen Kenntnisse und Fähigkeiten in den relevanten Prozessen."
)

_THIN = Side(style="thin", color="000000")
_RAHMEN = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_LINKS_OBEN = Alignment(horizontal="left", vertical="top", wrap_text=True)
_LINKS = Alignment(horizontal="left", vertical="center")


@dataclass
class EinarbeitungZeile:
    abteilung: str
    inhalt: str
    ansprechpartner: str = ""


def _fett(ws, ref: str, size: int = 11) -> None:
    ws[ref].font = Font(size=size, bold=True)


def _kopf(ws, name: str, stelle: str, beginn: date | None, logo: LogoBild | None = None) -> int:
    # Mit Logo entsteht oben ein Logo-Band; der Titel rückt darunter.
    titelzeile = 2
    if logo is not None:
        bild_einsetzen(ws, logo, "B1")
        for r in (1, 2, 3):
            ws.row_dimensions[r].height = 20
        titelzeile = 4
    ws.cell(row=titelzeile, column=2, value=FORMBLATT).font = Font(size=16, bold=True)

    zeilen = [
        ("Name des Mitarbeiters:", name),
        ("Stellenbezeichnung:", stelle or "—"),
        ("Beginn der Tätigkeit:", beginn.strftime("%d.%m.%Y") if beginn else "—"),
    ]
    r = titelzeile + 2
    for label, wert in zeilen:
        ws.cell(row=r, column=2, value=label).font = Font(bold=True)
        z = ws.cell(row=r, column=4, value=wert)
        z.alignment = _LINKS
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
        r += 1

    ws.cell(row=r, column=2, value="Einarbeitungszeit von:").font = Font(bold=True)
    ws.cell(row=r, column=5, value="bis:").font = Font(bold=True)
    r += 2
    ws.cell(row=r, column=2, value="Feedbackgespräch nach spätestens 4 Wochen:").font = Font(bold=True)
    ws.cell(row=r, column=5, value="Datum:")
    ws.cell(row=r, column=7, value="Unterschrift Vorgesetzter")
    return r + 2


def _einleitung(ws, r: int) -> int:
    ws.cell(row=r, column=2, value="Wichtige Einarbeitungsregeln:").font = Font(bold=True)
    r += 1
    for regel in _REGELN:
        ws.cell(row=r, column=2, value=f"• {regel}")
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
        r += 1
    r += 1
    ws.cell(row=r, column=2, value="Ziele der Einarbeitung:").font = Font(bold=True)
    r += 1
    ziel = ws.cell(row=r, column=2, value=_ZIELE)
    ziel.alignment = _LINKS_OBEN
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
    ws.row_dimensions[r].height = 30
    return r + 2


def _tabelle(ws, r: int, zeilen: list[EinarbeitungZeile]) -> int:
    kopf = {
        SP_ABT: "Abteilung",
        SP_PART: "Ansprechpartner",
        SP_INHALT: "Inhalte der Einarbeitung",
        SP_WANN: "Wann?",
        SP_ERLEDIGT: "Erledigt/\nUnterschrift",
    }
    for c, text in kopf.items():
        zelle = ws.cell(row=r, column=c, value=text)
        zelle.font = Font(size=9, bold=True)
        zelle.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        zelle.border = _RAHMEN
    ws.merge_cells(start_row=r, start_column=SP_INHALT, end_row=r, end_column=SP_WANN - 1)
    ws.row_dimensions[r].height = 26
    r += 1

    for z in zeilen:
        ws.cell(row=r, column=SP_ABT, value=z.abteilung)
        ws.cell(row=r, column=SP_PART, value=z.ansprechpartner)
        ws.cell(row=r, column=SP_INHALT, value=z.inhalt)
        ws.merge_cells(
            start_row=r, start_column=SP_INHALT, end_row=r, end_column=SP_WANN - 1
        )
        for c in range(SP_ABT, SP_ERLEDIGT + 1):
            zelle = ws.cell(row=r, column=c)
            zelle.border = _RAHMEN
            zelle.font = Font(size=9)
            zelle.alignment = _LINKS_OBEN
        ws.row_dimensions[r].height = 26
        r += 1
    return r


def _fuss(ws, r: int) -> int:
    r += 1
    ws.cell(row=r, column=2, value="Weiterer Schulungsbedarf notwendig?").font = Font(bold=True)
    ws.cell(row=r, column=6, value="☐ ja    ☐ nein")
    r += 1
    ws.cell(row=r, column=2, value="Falls ja, bitte Schulungsbedarf erläutern:")
    r += 3

    ws.cell(row=r, column=2, value="Laufweg:").font = Font(bold=True)
    r += 1
    for label in ("Bearbeitung:", "Personalabteilung", "Fachabteilung", "Rücklauf zur Personalabteilung"):
        ws.cell(row=r, column=2, value=label)
        if label == "Bearbeitung:":
            ws.cell(row=r, column=4, value="Eingang am:")
            ws.cell(row=r, column=6, value="Ausgang am:")
            ws.cell(row=r, column=8, value="Unterschrift").font = Font(size=9)
        r += 1
    return r


def baue_xlsx(
    name: str,
    stelle: str,
    beginn: date | None,
    zeilen: list[EinarbeitungZeile],
    logo: LogoBild | None = None,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Einarbeitungsplan"

    for spalte, breite in zip("ABCDEFGH", (3, 13, 20, 14, 14, 14, 9, 16)):
        ws.column_dimensions[spalte].width = breite

    r = _kopf(ws, name, stelle, beginn, logo)
    r = _einleitung(ws, r)
    tab_start = r
    r = _tabelle(ws, r, zeilen)
    _fuss(ws, r)

    ws.print_area = f"A1:H{r + 8}"
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.5, right=0.4, top=0.5, bottom=0.5)
    # Läuft die Liste auf eine zweite Seite, wiederholt sich der Tabellenkopf.
    ws.print_title_rows = f"{tab_start}:{tab_start}"

    puffer = BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


async def erzeuge_einarbeitung_pdf(
    name: str,
    stelle: str,
    beginn: date | None,
    zeilen: list[EinarbeitungZeile],
    logo: LogoBild | None = None,
) -> bytes:
    return await convert_xlsx_to_pdf(baue_xlsx(name, stelle, beginn, zeilen, logo))


def dateiname(name: str, stand: date) -> str:
    teil = "_".join(name.split()) or "Unbekannt"
    return f"{stand:%Y.%m.%d}_{teil}_Einarbeitungsplan"
