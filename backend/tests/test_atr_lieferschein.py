# backend/tests/test_atr_lieferschein.py
from pathlib import Path

from app.services.atr_lieferschein import parse_lieferschein_text

FIX = Path(__file__).parent / "fixtures" / "atr" / "lieferschein_sample.txt"


def test_parse_header_and_positions():
    pl = parse_lieferschein_text(FIX.read_text(encoding="utf-8"))
    assert pl.lieferschein_nr == "20189798"
    assert pl.datum == "08.06.2026"
    assert len(pl.positions) == 2

    p1 = pl.positions[0]
    assert p1.pos == 1
    assert p1.supplier_article_code == "6060"
    assert p1.qty == 1
    assert p1.bezeichnung == "CARPET EMERG. EXIT HATCH"
    assert p1.index == "D"
    assert p1.part_number == "VR11S1010016000"
    assert p1.part_number_norm == "111010016000"
    assert p1.ba_auftrag == "1024738"
    assert p1.po_pos == "5"
    assert p1.po_base == "4501119979"
    assert p1.ac_programme == "A350"
    assert p1.compartment == "CCRC"
    assert p1.msn == "830"
    assert p1.bed_config == "6"


def test_parse_missing_field_warns():
    text = "Nr. 999\n1 6060 1 STK\nCARPET X\nIhre Nr. VR11S1010016000\n"
    pl = parse_lieferschein_text(text)
    assert pl.positions and pl.positions[0].ba_auftrag is None
    assert any("auftrag" in w.lower() or "bestelldaten" in w.lower() for w in pl.warnings)


def test_bezeichnung_strips_right_column_note():
    # pdftotext -layout can merge a right-column note onto the Bezeichnung line.
    text = (
        "Nr. 1\nDatum 01.01.2026\n"
        "11 6060 1 STK\n"
        "SEC. LINING STAIRHOUSE 04                         Freigabe durch AV\n"
        "Ihre Nr. VR11S1020078000\nAuftrag Nr. 1024738 / 11\n"
        "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett\n"
    )
    pl = parse_lieferschein_text(text)
    assert pl.positions[0].bezeichnung == "SEC. LINING STAIRHOUSE 04"


def test_zero_positions_warns():
    pl = parse_lieferschein_text("LIEFERSCHEIN\nNr. 1\n")
    assert pl.positions == []
    assert pl.warnings


def test_duplicate_lieferschein_deduped():
    # Derselbe Lieferschein zweimal in einer PDF → Positionen nur einmal.
    text = FIX.read_text(encoding="utf-8")
    doubled = text + "\n\n" + text
    pl = parse_lieferschein_text(doubled)
    assert len(pl.positions) == 2  # nicht 4
    assert any("doppelter lieferschein" in w.lower() for w in pl.warnings)
