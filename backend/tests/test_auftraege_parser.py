"""Parser tests for app.parsing.auftraege_parser.

Builds a minimal fixture mirroring the real ``AswKpf_AUF.txt`` export:
18 columns, tab-separated, Latin-1 encoded.
"""
from datetime import date
from decimal import Decimal

from app.parsing.auftraege_parser import parse_auftraege_file


HEADER = (
    "Typ\tVorgang Nr.\tDatum\tAdr Nr.\tName 1\tName 2\tName 3\tOrt\t"
    "Erfasst durch\tGe\xe4ndert durch\tAnz Pos\tAA\tTyp 2\tRab Aktion\t"
    "Wert\teigene W\xe4hrung\tGes.Wert FW\tWAHR\r\n"
).encode("latin-1")


def _row(
    vorgang_nr: str,
    datum: str,
    erfasser: str,
    wert: str,
    *,
    typ: str = "AUF",
    adr_nr: str = "",
    name: str = "",
    ort: str = "",
) -> bytes:
    parts = [
        typ, vorgang_nr, datum, adr_nr, name, "", "", ort,
        erfasser, erfasser, "1", "STD", "", "",
        wert, "EUR", wert, "EUR",
    ]
    return ("\t".join(parts) + "\r\n").encode("latin-1")


def _fixture(rows: list[bytes]) -> bytes:
    return HEADER + b"".join(rows) + b"\r\n"


def test_parser_extracts_mapped_columns():
    payload = _fixture([
        _row("1023950", "02.01.2025", "ZETTLER", "1213,43",
             adr_nr="10005", name="abc GmbH", ort="Laupheim"),
    ])
    rows, errors = parse_auftraege_file(payload, "AswKpf_AUF.txt")
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r["vorgang_nr"] == "1023950"
    assert r["typ"] == "AUF"
    assert r["datum"] == date(2025, 1, 2)
    assert r["adr_nr"] == "10005"
    assert r["customer_name"] == "abc GmbH"
    assert r["erfasser"] == "ZETTLER"
    assert r["wert_eur"] == Decimal("1213.43")


def test_parser_handles_german_thousands_decimal():
    payload = _fixture([_row("9", "03.01.2025", "ZETTLER", "1.234,56")])
    rows, errors = parse_auftraege_file(payload, "f.txt")
    assert errors == []
    assert rows[0]["wert_eur"] == Decimal("1234.56")


def test_parser_skips_blank_trailing_rows():
    payload = HEADER + _row("1", "01.01.2025", "X", "100") + (
        b"\t" * 17 + b"\r\n"
    ) * 4
    rows, errors = parse_auftraege_file(payload, "f.txt")
    assert len(rows) == 1
    assert errors == []


def test_parser_reports_missing_vorgang_nr():
    payload = _fixture([_row("", "01.01.2025", "X", "100")])
    rows, errors = parse_auftraege_file(payload, "f.txt")
    assert rows == []
    assert any(e["field"] == "Vorgang Nr." for e in errors)


def test_parser_reports_unparseable_date():
    payload = _fixture([_row("1", "NOT-A-DATE", "X", "100")])
    rows, errors = parse_auftraege_file(payload, "f.txt")
    assert rows == []
    assert any(e["field"] == "Datum" for e in errors)


def test_parser_last_wins_on_duplicate_vorgang_nr():
    payload = _fixture([
        _row("42", "01.01.2025", "ZETTLER", "100"),
        _row("42", "02.01.2025", "HOHL", "500"),
    ])
    rows, errors = parse_auftraege_file(payload, "f.txt")
    assert errors == []
    assert len(rows) == 1
    assert rows[0]["erfasser"] == "HOHL"
    assert rows[0]["wert_eur"] == Decimal("500")
