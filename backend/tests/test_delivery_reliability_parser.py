"""Unit tests for the Einkauf/OTD delivery-reliability parser (no DB).

Source: dev_excel_Liefertreue_Einkauf.txt — tab-separated, cp1252, with an
optional row-1 "Auswertung: Liefertreue (von DD.MM.YYYY bis DD.MM.YYYY)"
title, the column header on the next line, and one row per delivery position.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.parsing.delivery_reliability_parser import (
    parse_delivery_reliability_file,
)

# Column order mirrors the real export.
_HEADER = [
    "Auftrag", "Pos", "UPos", "Kunde", "LS-Nr", "LS-Pos", "LS-Upos",
    "bestätigt", "Lieferdatum", "Wunschdatum", "geliefert", "Verzug (Tage)",
    "Artikel", "Bezeichnung", "ME", "Menge", "Wert", "Währung", "Ihr Zeichen",
    "Ihr Datum", "Kundennummer", "Zahlungsbedingung", "Lager", "PLZ",
    "Spedition", "Eintrefftag", "FA", "FA-Stop", "FA Istmenge",
]

_TITLE = "Auswertung:\tLiefertreue (von 01.01.2026 bis 30.04.2026)"


def _row(**over) -> list:
    """One canonical data row; override individual cells by header name."""
    base = {
        "Auftrag": "4017418", "Pos": "1", "UPos": "0",
        "Kunde": "Mattes & Ammann GmbH & Co.KG", "LS-Nr": "36156",
        "LS-Pos": "1", "LS-Upos": "0", "bestätigt": "11.09.2025",
        "Lieferdatum": "30.10.2025", "Wunschdatum": "", "geliefert": "05.01.2026",
        "Verzug (Tage)": "47", "Artikel": "L 2124",
        "Bezeichnung": "Cotton knit fabric  No. 40 719 SSD", "ME": "LFM",
        "Menge": "55,3", "Wert": "464,52", "Währung": "EUR", "Ihr Zeichen": "",
        "Ihr Datum": "", "Kundennummer": "81105", "Zahlungsbedingung": "9",
        "Lager": "HH-WE-LAGER", "PLZ": "72469", "Spedition": "0",
        "Eintrefftag": "", "FA": "0", "FA-Stop": "", "FA Istmenge": "0",
    }
    base.update(over)
    return [base[h] for h in _HEADER]


def _build(rows: list[list], *, title: bool = True) -> bytes:
    lines: list[str] = []
    if title:
        lines.append(_TITLE)
    lines.append("\t".join(_HEADER))
    for r in rows:
        lines.append("\t".join("" if c is None else str(c) for c in r))
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")


def test_parses_one_line_with_period():
    rows, errors, period = parse_delivery_reliability_file(
        _build([_row()]), "OTD.txt"
    )
    assert errors == []
    assert period == (date(2026, 1, 1), date(2026, 4, 30))
    assert len(rows) == 1
    r = rows[0]
    assert r["auftrag"] == "4017418"
    assert r["pos"] == 1
    assert r["upos"] == 0
    assert r["adr_nr"] == "81105"
    assert r["supplier_name"] == "Mattes & Ammann GmbH & Co.KG"
    assert r["delivered_date"] == date(2026, 1, 5)
    assert r["target_date"] == date(2025, 10, 30)
    assert r["verzug_tage"] == 47
    assert r["quantity"] == Decimal("55.3")
    assert r["unit"] == "LFM"
    assert r["article_number"] == "L 2124"


def test_negative_verzug_is_kept_signed():
    rows, errors, _ = parse_delivery_reliability_file(
        _build([_row(**{"Verzug (Tage)": "-3"})]), "OTD.txt"
    )
    assert errors == []
    assert rows[0]["verzug_tage"] == -3


def test_header_without_title_row_still_parses():
    rows, errors, period = parse_delivery_reliability_file(
        _build([_row()], title=False), "OTD.txt"
    )
    assert errors == []
    assert period is None
    assert len(rows) == 1
    assert rows[0]["auftrag"] == "4017418"


def test_missing_auftrag_is_error():
    rows, errors, _ = parse_delivery_reliability_file(
        _build([_row(Auftrag="")]), "OTD.txt"
    )
    assert rows == []
    assert errors[0]["column"] == "Auftrag"


def test_missing_pos_is_error():
    rows, errors, _ = parse_delivery_reliability_file(
        _build([_row(Pos="")]), "OTD.txt"
    )
    assert rows == []
    assert errors[0]["column"] == "Pos"


def test_in_file_duplicate_composite_key_reported_once():
    rows, errors, _ = parse_delivery_reliability_file(
        _build([_row(), _row(**{"Verzug (Tage)": "9"})]), "OTD.txt"
    )
    assert len(rows) == 1
    assert len(errors) == 1
    assert "duplicate" in errors[0]["message"]


def test_required_column_missing_reports_one_error():
    body = (
        "Auftrag\tPos\tgeliefert\r\n"
        "4017418\t1\t05.01.2026\r\n"
    ).encode("cp1252")
    rows, errors, _ = parse_delivery_reliability_file(body, "broken.txt")
    assert rows == []
    assert len(errors) == 1
    assert "Required column" in errors[0]["message"]
