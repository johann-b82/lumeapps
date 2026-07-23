"""Schulungsübersicht je Person als PDF — Formblatt 71 (v1.91).

Bildet das bestehende Papierformular nach: Kopf mit Name und Funktion, darunter
je Schulung eine Zeile mit laufender Nummer, Zeitraum, Bezeichnung, IN/EX-Kreuz
und dem Feld "Schulungsnachweis vorhanden".

Aufbau wie beim Wartungsnachweis (``maintenance_pdf``): openpyxl schreibt eine
.xlsx, LibreOffice headless macht daraus ein PDF. Kein UNO nötig — alles steht
in Zellen.

Für einen neuen Mitarbeiter sind Zeitraum und Nachweis-Spalte leer: das Blatt
ist dann der Plan, den er abarbeitet, und wird beim Absolvieren handschriftlich
oder über die Anwendung nachgeführt.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.worksheet.page import PageMargins

from app.services.maintenance_pdf import convert_xlsx_to_pdf

#: Kopfangaben des Formblatts. Stehen so auf dem Papierformular und ändern sich
#: nur mit einer neuen Revision des Formblatts selbst.
FORMBLATT = "Formblatt 71"
REVISIONS_INDEX = "A"
REVISIONS_STAND = "22.03.2022"
AUSGABEDATUM = "22.03.2022"

#: Spaltennummern der vier Ankreuzfelder (D-G).
SP_IN, SP_EX, SP_JA, SP_NEIN = 4, 5, 6, 7

_THIN = Side(style="thin", color="000000")
_RAHMEN = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_LINKS_OBEN = Alignment(horizontal="left", vertical="top", wrap_text=True)
_MITTE = Alignment(horizontal="center", vertical="center")


@dataclass
class UebersichtZeile:
    """Eine Zeile des Formblatts."""

    bezeichnung: str
    #: Freitext wie "16.03.2026 - 17.03.2026"; leer, solange nicht absolviert.
    zeitraum: str = ""
    #: Anbieter samt Anschrift, erscheint unter der Bezeichnung.
    anbieter: str = ""
    #: True = intern (IN), False = extern (EX), None = noch offen.
    intern: bool | None = None
    #: True/False setzt das Kreuz in "Schulungsnachweis vorhanden".
    nachweis: bool | None = None


def _kopf(ws, name: str, funktion: str) -> int:
    """Titelblock und Personenangaben. Gibt die nächste freie Zeile zurück."""
    ws["A1"] = "Schulungsübersicht"
    ws["A1"].font = Font(size=16, bold=True)
    # Nur A:B — ab Spalte C steht rechtsbündig der Formblatt-Block.
    ws.merge_cells("A1:B2")
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

    # Über C:G zusammengefasst und rechtsbündig — in einer schmalen Spalte
    # allein würde "Revisions-Stand: 22.03.2022" abgeschnitten.
    for i, text in enumerate(
        [
            FORMBLATT,
            f"Revisions-Index: {REVISIONS_INDEX}",
            f"Revisions-Stand: {REVISIONS_STAND}",
            "Blatt 1 von 1",
        ]
    ):
        zeile = 1 + i
        ws.merge_cells(start_row=zeile, start_column=3, end_row=zeile, end_column=SP_NEIN)
        zelle = ws.cell(row=zeile, column=3, value=text)
        zelle.font = Font(size=9)
        zelle.alignment = Alignment(horizontal="right", vertical="center")

    ws["A5"] = "Name:"
    ws["A5"].font = Font(bold=True)
    ws["B5"] = name
    ws["A6"] = "Funktion:"
    ws["A6"].font = Font(bold=True)
    ws["B6"] = funktion or "—"
    for zeile in (5, 6):
        ws.merge_cells(start_row=zeile, start_column=2, end_row=zeile, end_column=SP_NEIN)
    return 8


def _tabellenkopf(ws, zeile: int) -> int:
    """Zweizeiliger Tabellenkopf wie auf dem Formular.

    IN/EX und ja/nein sind vier eigene Ankreuzfelder, nicht zwei kombinierte —
    das Blatt wird ausgedruckt und von Hand abgehakt.
    """
    ws.cell(row=zeile, column=1, value="Laufende\nNummer:")
    ws.cell(row=zeile, column=2, value="durchgeführt am/\nvon … bis:")
    ws.cell(row=zeile, column=3, value="Bezeichnung der Aus- und Fortbildungsmaßnahme")
    ws.cell(row=zeile, column=SP_IN, value="Schulungsnachweis\nvorhanden")
    ws.merge_cells(start_row=zeile, start_column=SP_IN, end_row=zeile, end_column=SP_NEIN)

    unten = zeile + 1
    ws.cell(row=unten, column=3, value="Interne (IN) oder externe (EX) Maßnahme:")
    ws.cell(row=unten, column=SP_IN, value="IN")
    ws.cell(row=unten, column=SP_EX, value="EX")
    ws.cell(row=unten, column=SP_JA, value="ja")
    ws.cell(row=unten, column=SP_NEIN, value="nein")
    for spalte in (1, 2):
        ws.merge_cells(
            start_row=zeile, start_column=spalte, end_row=unten, end_column=spalte
        )

    for r in (zeile, unten):
        for c in range(1, SP_NEIN + 1):
            zelle = ws.cell(row=r, column=c)
            zelle.font = Font(size=9, bold=True)
            # wrap_text auch in den zentrierten Spalten, sonst läuft
            # "Schulungsnachweis vorhanden" in einer Zeile durch.
            zelle.alignment = (
                Alignment(horizontal="center", vertical="center", wrap_text=True)
                if c >= SP_IN
                else _LINKS_OBEN
            )
            zelle.border = _RAHMEN
    ws.row_dimensions[zeile].height = 32
    return unten + 1


def _zeile_schreiben(ws, r: int, nr: int, z: UebersichtZeile) -> None:
    ws.cell(row=r, column=1, value=f"{nr:02d}")
    ws.cell(row=r, column=2, value=z.zeitraum)
    # Anbieter kommt als zweiter Absatz in dieselbe Zelle — auf dem Formular
    # steht er unter der Bezeichnung, nicht in einer eigenen Spalte.
    text = z.bezeichnung + (f"\n\n{z.anbieter}" if z.anbieter else "")
    ws.cell(row=r, column=3, value=text)
    # Kreuz nur dort, wo die Angabe feststeht; offen bleibt leer zum Ankreuzen.
    ws.cell(row=r, column=SP_IN, value="X" if z.intern is True else "")
    ws.cell(row=r, column=SP_EX, value="X" if z.intern is False else "")
    ws.cell(row=r, column=SP_JA, value="X" if z.nachweis is True else "")
    ws.cell(row=r, column=SP_NEIN, value="X" if z.nachweis is False else "")

    for c in range(1, SP_NEIN + 1):
        zelle = ws.cell(row=r, column=c)
        zelle.border = _RAHMEN
        zelle.font = Font(size=9)
        zelle.alignment = _MITTE if c == 1 or c >= SP_IN else _LINKS_OBEN
    # Platz für Bezeichnung samt Anbieteranschrift, auch wenn beides noch leer
    # ist — sonst rutscht das Formular beim Ausfüllen von Hand aus dem Raster.
    ws.row_dimensions[r].height = 46 if z.anbieter else 30


def _fuss(ws, zeile: int, freigegeben_von: str, erstellt_von: str) -> None:
    ws.cell(row=zeile, column=1, value="Aktualisiert am:")
    ws.cell(row=zeile, column=3, value=f"Ausgabedatum: {AUSGABEDATUM}")
    ws.cell(row=zeile + 1, column=1, value=f"Freigegeben von: {freigegeben_von}")
    ws.cell(row=zeile + 1, column=3, value=f"Erstellt von: {erstellt_von}")
    for r in (zeile, zeile + 1):
        for c in (1, 3):
            ws.cell(row=r, column=c).font = Font(size=8)


def baue_xlsx(
    name: str,
    funktion: str,
    zeilen: list[UebersichtZeile],
    freigegeben_von: str,
    erstellt_von: str,
) -> bytes:
    """Formblatt 71 als .xlsx (Zwischenschritt zur PDF-Erzeugung)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Schulungsübersicht"

    for spalte, breite in zip("ABCDEFG", (11, 16, 58, 5, 5, 5, 6)):
        ws.column_dimensions[spalte].width = breite

    r = _kopf(ws, name, funktion)
    r = _tabellenkopf(ws, r)
    for i, z in enumerate(zeilen, start=1):
        _zeile_schreiben(ws, r, i, z)
        r += 1
    _fuss(ws, r + 1, freigegeben_von, erstellt_von)

    ws.print_area = f"A1:G{r + 2}"
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.5, right=0.4, top=0.5, bottom=0.5)

    puffer = BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


async def erzeuge_schulungsuebersicht_pdf(
    name: str,
    funktion: str,
    zeilen: list[UebersichtZeile],
    freigegeben_von: str = "",
    erstellt_von: str = "",
) -> bytes:
    return await convert_xlsx_to_pdf(
        baue_xlsx(name, funktion, zeilen, freigegeben_von, erstellt_von)
    )


def dateiname(name: str, stand: date) -> str:
    """Namensschema der Vorlage: 2026.03.03_Marcel_Brose_Schulungsübersicht."""
    teil = "_".join(name.split()) or "Unbekannt"
    return f"{stand:%Y.%m.%d}_{teil}_Schulungsuebersicht"
