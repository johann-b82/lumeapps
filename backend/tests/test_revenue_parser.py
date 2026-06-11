"""Parser tests for app.parsing.revenue_parser.

Builds a minimal fixture mirroring the real ``AswKpf_RG.txt`` export:
18 columns, tab-separated, Latin-1 encoded. Rows are RG (Rechnung,
positive wert) or GS (Gutschrift, negative wert).
"""
from datetime import date
from decimal import Decimal

from app.parsing.revenue_parser import parse_revenue_file


HEADER = (
    "Typ\tVorgang Nr.\tDatum\tAdr Nr.\tName 1\tName 2\tName 3\tOrt\t"
    "Erfasst durch\tGe\xe4ndert durch\tAnz Pos\tAA\tTyp 2\tRab Aktion\t"
    "Wert\teigene W\xe4hrung\tGes.Wert FW\tWAHR\r\n"
).encode("latin-1")


def _row(
    typ: str,
    vorgang_nr: str,
    datum: str,
    wert: str,
    *,
    adr_nr: str = "",
    name: str = "",
    ort: str = "",
    erfasser: str = "ZETTLER",
) -> bytes:
    parts = [
        typ, vorgang_nr, datum, adr_nr, name, "", "", ort,
        erfasser, erfasser, "1", "STD", "", "",
        wert, "EUR", wert, "EUR",
    ]
    return ("\t".join(parts) + "\r\n").encode("latin-1")


def _fixture(rows: list[bytes]) -> bytes:
    return HEADER + b"".join(rows) + b"\r\n"


def test_parser_extracts_RG_and_GS_rows():
    payload = _fixture([
        _row("RG", "3030989", "07.01.2025", "255,6",
             adr_nr="10005", name="ABC gmBH", ort="Laupheim"),
        _row("GS", "3030988", "07.01.2025", "-332,48",
             adr_nr="10005", name="abc GmbH", ort="Laupheim"),
    ])
    rows, errors = parse_revenue_file(payload, "AswKpf_RG.txt")
    assert errors == []
    assert len(rows) == 2
    rg = next(r for r in rows if r["typ"] == "RG")
    gs = next(r for r in rows if r["typ"] == "GS")
    assert rg["vorgang_nr"] == "3030989"
    assert rg["wert_eur"] == Decimal("255.60")
    assert rg["datum"] == date(2025, 1, 7)
    assert gs["vorgang_nr"] == "3030988"
    assert gs["wert_eur"] == Decimal("-332.48")
    assert gs["customer_name"] == "abc GmbH"


def test_parser_preserves_negative_decimal_for_GS():
    payload = _fixture([_row("GS", "1", "01.01.2025", "-1.234,56")])
    rows, errors = parse_revenue_file(payload, "f.txt")
    assert errors == []
    assert rows[0]["wert_eur"] == Decimal("-1234.56")


def test_parser_skips_blank_trailing_rows():
    payload = HEADER + _row("RG", "1", "01.01.2025", "100") + (
        b"\t" * 17 + b"\r\n"
    ) * 3
    rows, errors = parse_revenue_file(payload, "f.txt")
    assert len(rows) == 1
    assert errors == []


def test_parser_reports_missing_typ():
    payload = _fixture([_row("", "1", "01.01.2025", "100")])
    rows, errors = parse_revenue_file(payload, "f.txt")
    assert rows == []
    assert any(e["field"] == "Typ" for e in errors)


def test_parser_reports_unparseable_date():
    payload = _fixture([_row("RG", "1", "NOT-A-DATE", "100")])
    rows, errors = parse_revenue_file(payload, "f.txt")
    assert rows == []
    assert any(e["field"] == "Datum" for e in errors)


def test_parser_last_wins_on_duplicate_vorgang_nr():
    payload = _fixture([
        _row("RG", "42", "01.01.2025", "100"),
        _row("GS", "42", "02.01.2025", "-50"),
    ])
    rows, errors = parse_revenue_file(payload, "f.txt")
    assert errors == []
    assert len(rows) == 1
    assert rows[0]["typ"] == "GS"
    assert rows[0]["wert_eur"] == Decimal("-50")
