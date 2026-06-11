"""Parser tests for app.parsing.angebote_parser.

Builds a minimal fixture mirroring the real ``AswKpf_ANG.txt`` export:
18 columns, tab-separated, Latin-1 encoded.
"""
from datetime import date
from decimal import Decimal

from app.parsing.angebote_parser import parse_angebote_file


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
    adr_nr: str = "",
    name: str = "",
    ort: str = "",
) -> bytes:
    parts = [
        "ANG", vorgang_nr, datum, adr_nr, name, "", "", ort,
        erfasser, erfasser, "1", "STD", "", "",
        wert, "EUR", wert, "EUR",
    ]
    return ("\t".join(parts) + "\r\n").encode("latin-1")


def _fixture(rows: list[bytes]) -> bytes:
    return HEADER + b"".join(rows) + b"\r\n"


def test_parser_extracts_mapped_columns():
    payload = _fixture([
        _row("5002640", "22.01.2026", "SCHMIDT", "322611,16",
             adr_nr="10005", name="Diehl Aviation Laupheim GmbH", ort="Laupheim"),
    ])
    rows, errors = parse_angebote_file(payload, "AswKpf_ANG.txt")
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r["vorgang_nr"] == "5002640"
    assert r["datum"] == date(2026, 1, 22)
    assert r["erfasser"] == "SCHMIDT"
    assert r["wert_eur"] == Decimal("322611.16")
    assert r["adr_nr"] == "10005"
    assert r["name"] == "Diehl Aviation Laupheim GmbH"
    assert r["ort"] == "Laupheim"


def test_parser_handles_plain_integer_wert():
    payload = _fixture([_row("5002641", "19.01.2026", "SCHMIDT", "84000")])
    rows, errors = parse_angebote_file(payload, "f.txt")
    assert errors == []
    assert rows[0]["wert_eur"] == Decimal("84000")


def test_parser_skips_blank_trailing_rows():
    payload = HEADER + _row("5002640", "22.01.2026", "SCHMIDT", "100") + (
        b"\t" * 17 + b"\r\n"
    ) * 5
    rows, errors = parse_angebote_file(payload, "f.txt")
    assert len(rows) == 1
    assert errors == []


def test_parser_reports_unparseable_date():
    payload = _fixture([_row("999", "NOT-A-DATE", "SCHMIDT", "100")])
    rows, errors = parse_angebote_file(payload, "f.txt")
    assert rows == []
    assert any(e["field"] == "Datum" for e in errors)


def test_parser_reports_unparseable_wert():
    payload = _fixture([_row("999", "01.01.2026", "SCHMIDT", "NOT-A-NUMBER")])
    rows, errors = parse_angebote_file(payload, "f.txt")
    assert rows == []
    assert any(e["field"] == "Wert" for e in errors)


def test_parser_reports_missing_vorgang_nr():
    payload = _fixture([_row("", "01.01.2026", "SCHMIDT", "100")])
    rows, errors = parse_angebote_file(payload, "f.txt")
    assert rows == []
    assert any(e["field"] == "Vorgang Nr." for e in errors)


def test_parser_last_wins_on_duplicate_vorgang_nr():
    payload = _fixture([
        _row("42", "01.01.2026", "SCHMIDT", "100"),
        _row("42", "02.01.2026", "HOHL", "500"),
    ])
    rows, errors = parse_angebote_file(payload, "f.txt")
    assert errors == []
    assert len(rows) == 1
    assert rows[0]["erfasser"] == "HOHL"
    assert rows[0]["wert_eur"] == Decimal("500")
