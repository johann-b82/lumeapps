"""Parser tests for app.parsing.auftrag_positionen_parser.

Mirrors the real position-level ``AswKpf_AUF.txt`` export: 21 columns,
tab-separated, Latin-1, German dates/decimals.
"""
from datetime import date
from decimal import Decimal

from app.parsing.auftrag_positionen_parser import parse_auftrag_positionen_file


HEADER = (
    "Typ\tVorgang Nr.\tPos\tUPos\tDatum\tAdr Nr.\tName 1\tOrt\tArtnr\tVersion\t"
    "Bezeichnung 1\tMenge\tME\tSt\tLieferdatum\tPreis\tPos Wert\tPos Typ 2\t"
    "Fremdnr\tSperre manuell\tSperre K-Limit\r\n"
)


def _row(vorgang, pos, lieferdatum, *, typ="AUF", pos_typ_2="AV-F",
         menge="10", preis="128,26", pos_wert="1213,43"):
    parts = [
        typ, vorgang, pos, "0", "02.01.2025", "10005", "Diehl", "Laupheim",
        "12900", "", "NET LIT POCKET", menge, "STK", "1", lieferdatum,
        preis, pos_wert, pos_typ_2, "VM31", "N", "0",
    ]
    return "\t".join(parts) + "\r\n"


def _fixture(rows: list[str]) -> bytes:
    return (HEADER + "".join(rows)).encode("latin-1")


def test_parser_extracts_mapped_columns():
    rows, errors = parse_auftrag_positionen_file(
        _fixture([_row("1023950", "1", "07.03.2025")]), "AswKpf_AUF.txt"
    )
    assert errors == []
    r = rows[0]
    assert r["vorgang_nr"] == "1023950"
    assert r["pos"] == 1
    assert r["upos"] == 0
    assert r["typ"] == "AUF"
    assert r["lieferdatum"] == date(2025, 3, 7)
    assert r["entry_date"] == date(2025, 1, 2)
    assert r["pos_typ_2"] == "AV-F"
    assert r["quantity"] == Decimal("10")
    assert r["price"] == Decimal("128.26")
    assert r["position_value"] == Decimal("1213.43")


def test_parser_keeps_all_positions_of_an_order():
    rows, errors = parse_auftrag_positionen_file(
        _fixture([
            _row("1023951", "1", "24.01.2025"),
            _row("1023951", "2", "14.02.2025"),
            _row("1023951", "3", "14.02.2025"),
        ]),
        "f.txt",
    )
    assert errors == []
    assert len(rows) == 3
    assert max(r["lieferdatum"] for r in rows) == date(2025, 2, 14)


def test_parser_drops_non_auf_rows():
    rows, errors = parse_auftrag_positionen_file(
        _fixture([_row("1", "1", "07.03.2025", typ="LS")]), "f.txt"
    )
    assert rows == []
    assert errors == []


def test_parser_dedups_composite_key_in_file():
    rows, errors = parse_auftrag_positionen_file(
        _fixture([
            _row("9", "1", "07.03.2025"),
            _row("9", "1", "09.03.2025"),
        ]),
        "f.txt",
    )
    assert len(rows) == 1
    assert any("duplicate" in e["message"] for e in errors)


def test_parser_reports_missing_required_column():
    bad = "Typ\tVorgang Nr.\tPos\r\nAUF\t1\t1\r\n".encode("latin-1")
    rows, errors = parse_auftrag_positionen_file(bad, "f.txt")
    assert rows == []
    assert any("Lieferdatum" in e["column"] for e in errors)
