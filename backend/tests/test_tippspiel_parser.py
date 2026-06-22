"""Unit tests for the WM-Tippspiel Excel parser (no DB)."""
from __future__ import annotations

from datetime import date, time
from io import BytesIO

import openpyxl

from app.parsing.tippspiel_parser import parse_tippspiel_file

_HEADER = [
    "Gruppe", "Datum", "Spiel",
    "Büro-Admin / Hamburg", "Wandverkleidung", "Schaum / Montage",
    "Näherei / Teppich", "ACM-Team: Memmingen", "Ergebnis ", "Punkte ",
]
_DEPTS = _HEADER[3:8]


def _build(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "WM 2026 Tipps"
    ws.append(_HEADER)
    for r in rows:
        ws.append(list(r) + [None] * (len(_HEADER) - len(r)))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_departments_read_from_header():
    _, _, depts = parse_tippspiel_file(_build([]), "t.xlsx")
    assert depts == _DEPTS


def test_match_row_maps_teams_dates_and_tips():
    rows, errors, _ = parse_tippspiel_file(_build([
        ["Gruppe A", None, None, None, None, None, None, None],  # header → skip
        ["A", "Do., 11.06.", "Mexiko – Südafrika", "2:1", "2:0", "1:1", "2:1", "0:0"],
    ]), "t.xlsx")
    assert errors == []
    assert len(rows) == 5  # one row per department
    r = rows[0]
    assert r["gruppe"] == "A"
    assert r["home"] == "Mexico"
    assert r["away"] == "South Africa"
    assert r["match_date"] == date(2026, 6, 11)
    assert r["department"] == "Büro-Admin / Hamburg"
    assert (r["tip_home"], r["tip_away"]) == (2, 1)


def test_excel_time_artifact_tip_is_recovered():
    # Excel turned "2:0" into a time(2,0); "1:3" into time(1,3).
    rows, _, _ = parse_tippspiel_file(_build([
        ["A", "Fr., 12.06.", "Südkorea – Tschechien",
         time(2, 0), time(1, 3), "1:2", "1:1", "0:0"],
    ]), "t.xlsx")
    by = {r["department"]: (r["tip_home"], r["tip_away"]) for r in rows}
    assert by["Büro-Admin / Hamburg"] == (2, 0)
    assert by["Wandverkleidung"] == (1, 3)


def test_unknown_team_is_reported_and_row_dropped():
    rows, errors, _ = parse_tippspiel_file(_build([
        ["X", "Do., 11.06.", "Atlantis – Mexiko", "1:0", "1:0", "1:0", "1:0", "1:0"],
    ]), "t.xlsx")
    assert rows == []
    assert any("Atlantis" in e.get("message", "") for e in errors)


def test_empty_tip_cells_are_skipped():
    rows, _, _ = parse_tippspiel_file(_build([
        ["A", "Do., 11.06.", "Mexiko – Südafrika", "2:1", None, "", "2:1", "0:0"],
    ]), "t.xlsx")
    assert len(rows) == 3  # two empty tips dropped
