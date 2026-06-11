"""Unit tests for the v1.49 8D parser (no DB)."""
from __future__ import annotations

from datetime import date

from app.parsing.quality_parser import parse_quality_file


# Minimal header — only the columns the parser actually reads. The real
# 8D.txt has 40+ columns; pandas tolerates extras as long as the row
# widths match.
_HEADER = (
    "Nr.\tDatum\tAussteller\tAdress Nr.\tAdressen\tArtikel\tBezeichnung\t"
    "Status\tgelöscht\tArt\tProblembeschreibung\tUrsache\r\n"
)


def _build(rows: list[str], encoding: str = "cp1252") -> bytes:
    return (_HEADER + "".join(rows)).encode(encoding)


def test_parses_major_finding_as_level_1():
    body = _build([
        "1116\t01.04.2026\tBROSE\t12040\tZIM Aircraft Seating GmbH\t"
        "Audit Major Level 1\tDummy für Major\tCAR MA 4\tN\tKU AUD\t"
        "Wartung nicht durchgeführt\tUmzug nach Hamburg\r\n"
    ])
    rows, errors = parse_quality_file(body, "8D.txt")
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r["report_nr"] == "1116"
    assert r["report_date"] == date(2026, 4, 1)
    assert r["art"] == "KU AUD"
    assert r["level"] == 1
    assert r["issuer"] == "BROSE"
    assert r["customer_name"] == "ZIM Aircraft Seating GmbH"
    assert r["designation"] == "Dummy für Major"
    assert r["problem_description"].startswith("Wartung")


def test_parses_minor_finding_as_level_2():
    body = _build([
        "1127\t01.04.2026\tBROSE\t12040\tZIM Aircraft Seating GmbH\t"
        "Audit Minor Level 2\tDummy für Minor\tCAR MI 11\tN\tKU AUD\t\t\r\n"
    ])
    rows, _ = parse_quality_file(body, "8D.txt")
    assert rows[0]["level"] == 2


def test_unknown_artikel_text_yields_null_level():
    body = _build([
        "9001\t01.04.2026\t\t\t\tIrgendetwas anderes\t\t\tN\tBH AUD\t\t\r\n",
    ])
    rows, _ = parse_quality_file(body, "8D.txt")
    assert rows[0]["level"] is None


def test_keeps_non_audit_art_rows_for_future_complaints_branch():
    # Reklamationen rows (art empty or non-audit) are still ingested so
    # the future complaints KPI can read them without re-upload.
    body = _build([
        "2001\t02.04.2026\t\t\t\tQ-Note: Verpackung\t\t\tN\t\t\t\r\n",
        "2002\t02.04.2026\t\t\t\t\t\t\tN\tKU REK\t\t\r\n",
    ])
    rows, errors = parse_quality_file(body, "8D.txt")
    assert errors == []
    assert {r["art"] for r in rows} == {None, "KU REK"}
    assert all(r["level"] is None for r in rows)


def test_dropped_rows_with_geloescht_J():
    body = _build([
        "3001\t05.04.2026\t\t\t\tAudit Major Level 1\t\t\tJ\tIN AUD\t\t\r\n",
        "3002\t05.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tIN AUD\t\t\r\n",
    ])
    rows, errors = parse_quality_file(body, "8D.txt")
    assert errors == []
    assert [r["report_nr"] for r in rows] == ["3002"]


def test_unparseable_date_is_error_not_silent_drop():
    body = _build([
        "4001\tNOTADATE\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
    ])
    rows, errors = parse_quality_file(body, "8D.txt")
    assert rows == []
    assert len(errors) == 1
    assert errors[0]["column"] == "Datum"


def test_missing_report_nr_is_error_not_silent_drop():
    body = _build([
        "\t01.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
    ])
    rows, errors = parse_quality_file(body, "8D.txt")
    assert rows == []
    assert errors[0]["column"] == "Nr."


def test_in_file_duplicate_report_nr_reported_once_not_twice():
    body = _build([
        "5001\t01.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
        "5001\t02.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tIN AUD\t\t\r\n",
    ])
    rows, errors = parse_quality_file(body, "8D.txt")
    assert [r["report_nr"] for r in rows] == ["5001"]
    assert len(errors) == 1
    assert "duplicate" in errors[0]["message"]


def test_decodes_cp1252_umlauts():
    # Encoded with cp1252 so 'ü' is 0xFC, not the UTF-8 two-byte sequence.
    body = _build([
        "6001\t01.04.2026\tMüller\t\t\tAudit Major Level 1\t\t\tN\tBH AUD\t"
        "Maßnahme fehlt\tFehlanpassung\r\n",
    ], encoding="cp1252")
    rows, _ = parse_quality_file(body, "8D.txt")
    assert rows[0]["issuer"] == "Müller"
    assert rows[0]["problem_description"] == "Maßnahme fehlt"


def test_recognises_all_four_audit_art_codes():
    body = _build([
        "7001\t01.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tBH AUD\t\t\r\n",
        "7002\t02.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tEX AUD\t\t\r\n",
        "7003\t03.04.2026\t\t\t\tAudit Major Level 1\t\t\tN\tIN AUD\t\t\r\n",
        "7004\t04.04.2026\t\t\t\tAudit Minor Level 2\t\t\tN\tKU AUD\t\t\r\n",
    ])
    rows, errors = parse_quality_file(body, "8D.txt")
    assert errors == []
    assert {r["art"] for r in rows} == {"BH AUD", "EX AUD", "IN AUD", "KU AUD"}
