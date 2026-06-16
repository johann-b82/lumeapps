"""Unit tests for the v1.58 delivery parser (no DB)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import openpyxl

from app.parsing.delivery_parser import parse_delivery_file


_HEADER = [
    "Typ", "Vorgang Nr.", "Pos", "UPos", "Datum", "Adr Nr.", "Name 1",
    "Ort", "Artnr", "Version", "Bezeichnung 1", "Menge", "ME", "St",
    "Lieferdatum", "Preis", "Pos Wert", "Pos Typ 2", "Fremdnr",
    "Sperre manuell", "Sperre K-Limit", "Auftrag", "Pos.1",
]


def _build_xlsx(rows: list[list]) -> bytes:
    """Build an openpyxl workbook in memory mirroring AswKpf_LS.xlsx shape."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_HEADER)
    for r in rows:
        # pad to header length so missing trailing cells are None.
        padded = list(r) + [None] * (len(_HEADER) - len(r))
        ws.append(padded)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parses_one_line_with_canonical_fields():
    body = _build_xlsx([
        ["LS", "20189185", 1, 0, "2026-01-06", "12050",
         "SAFRAN SEATS FRANCE", "Issoudun", "8362", None,
         "Life Vest Pouch", 245, "STK", 1, "2026-01-06", 20.65, 5059.25,
         "AB", "F0505698", "N", 0, "1024592", 1],
    ])
    rows, errors = parse_delivery_file(body, "LS.xlsx")
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r["vorgang_nr"] == "20189185"
    assert r["pos"] == 1
    assert r["upos"] == 0
    assert r["typ"] == "LS"
    assert r["delivery_date"] == date(2026, 1, 6)
    assert r["customer_id"] == "12050"
    assert r["customer_name"] == "SAFRAN SEATS FRANCE"
    assert r["article_number"] == "8362"
    assert r["quantity"] == Decimal("245")
    assert r["unit"] == "STK"
    assert r["external_order_nr"] == "F0505698"
    assert r["order_nr"] == "1024592"


def test_drops_non_LS_typ_rows_silently():
    body = _build_xlsx([
        ["LS", "1000", 1, 0, "2026-02-01", "10",
         "X", "C", "A", None, "x", 5, "STK", 1, "2026-02-01", 1, 5,
         "AB", "ext", "N", 0, "ord", 1],
        # RG = Rechnung — should be silently skipped, not an error.
        ["RG", "2000", 1, 0, "2026-02-02", "10",
         "Y", "C", "B", None, "y", 7, "STK", 1, "2026-02-02", 1, 7,
         "AB", "ext", "N", 0, "ord", 1],
    ])
    rows, errors = parse_delivery_file(body, "LS.xlsx")
    assert errors == []
    assert len(rows) == 1
    assert rows[0]["vorgang_nr"] == "1000"


def test_missing_vorgang_nr_is_error_not_silent_drop():
    body = _build_xlsx([
        ["LS", "", 1, 0, "2026-02-01", "10", "X", "C", "A", None, "x", 5,
         "STK", 1, "2026-02-01", 1, 5, "AB", "ext", "N", 0, "ord", 1],
    ])
    rows, errors = parse_delivery_file(body, "LS.xlsx")
    assert rows == []
    assert errors[0]["column"] == "Vorgang Nr."


def test_missing_pos_is_error():
    body = _build_xlsx([
        ["LS", "1000", "", 0, "2026-02-01", "10", "X", "C", "A", None,
         "x", 5, "STK", 1, "2026-02-01", 1, 5, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    rows, errors = parse_delivery_file(body, "LS.xlsx")
    assert rows == []
    assert errors[0]["column"] == "Pos"


def test_in_file_duplicate_composite_key_reported_once():
    body = _build_xlsx([
        ["LS", "1000", 1, 0, "2026-02-01", "10", "X", "C", "A", None,
         "x", 5, "STK", 1, "2026-02-01", 1, 5, "AB", "ext", "N", 0,
         "ord", 1],
        ["LS", "1000", 1, 0, "2026-02-01", "10", "X", "C", "A", None,
         "x", 6, "STK", 1, "2026-02-01", 1, 6, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    rows, errors = parse_delivery_file(body, "LS.xlsx")
    assert len(rows) == 1
    assert len(errors) == 1
    assert "duplicate" in errors[0]["message"]


def test_uses_lieferdatum_not_datum_for_delivery_date():
    body = _build_xlsx([
        ["LS", "1000", 1, 0, "2026-01-01", "10", "X", "C", "A", None,
         "x", 5, "STK", 1, "2026-02-15", 1, 5, "AB", "ext", "N", 0,
         "ord", 1],
    ])
    rows, _ = parse_delivery_file(body, "LS.xlsx")
    assert rows[0]["entry_date"] == date(2026, 1, 1)
    assert rows[0]["delivery_date"] == date(2026, 2, 15)


def test_required_columns_missing_reports_one_error():
    # Build a workbook with only 3 columns — Vorgang Nr. and Menge absent.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Typ", "Pos", "Lieferdatum"])
    ws.append(["LS", 1, "2026-02-01"])
    buf = BytesIO()
    wb.save(buf)

    rows, errors = parse_delivery_file(buf.getvalue(), "broken.xlsx")
    assert rows == []
    assert len(errors) == 1
    assert "Required column" in errors[0]["message"]
