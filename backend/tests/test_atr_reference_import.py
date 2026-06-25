from decimal import Decimal

import pytest

from app.services.atr_reference_import import norm_partno, parse_workbook
from tests._atr_fixtures import build_atr_workbook_bytes


def test_norm_partno_digits_only():
    assert norm_partno("VR11S 1010 048 000") == "111010048000"
    assert norm_partno("VR11S1010-027/A") == "111010027"


def test_parse_header_and_parts():
    pw = parse_workbook(build_atr_workbook_bytes(), "demo.xlsx")
    assert pw.header.customer == "Diehl Aviation Laupheim GmbH"
    assert pw.header.ata_chapter == "25"
    assert pw.header.nscm_code == "C9312"
    assert len(pw.parts) == 2
    p = pw.parts[0]
    assert p.part_number == "VR11S 1010 016 000"
    assert p.part_number_norm == "111010016000"
    assert p.part_name == "CARPET EMERGENCY EXIT HATCH"
    assert p.drawing_number_issue == "VR11S 1010-10/D"
    assert p.category == "CARPET"
    assert p.default_weight_kg == Decimal("0.413")
    assert p.qty == 1


def test_parse_collects_weight_warning():
    parts = [("6060", "VR11S 1010 016 000", "X", "N/A", "VR11S 1010-10/D", 1, "not-a-number")]
    pw = parse_workbook(build_atr_workbook_bytes(parts=parts), "bad.xlsx")
    assert pw.parts[0].default_weight_kg is None
    assert any("weight" in w.lower() for w in pw.warnings)


def test_parse_rejects_multiple_visible_sheets():
    from openpyxl import Workbook
    from io import BytesIO
    wb = Workbook()
    wb.active.title = "one"
    wb.create_sheet("two")  # visible by default → two visible sheets
    bio = BytesIO(); wb.save(bio)
    with pytest.raises(ValueError):
        parse_workbook(bio.getvalue(), "two-visible.xlsx")
