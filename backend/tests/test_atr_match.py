# backend/tests/test_atr_match.py
import pytest

from app.services.atr_lieferschein import parse_lieferschein_text
from app.services.atr_match import match_positions
from tests._auth import ADMIN_UUID, mint  # noqa: F401 (ensures _auth importable)


async def _seed_part(client):
    # create a catalog part for VR11S1010016000 via the Phase A endpoint
    await client.post("/api/atr/parts",
                      headers={"Authorization": f"Bearer {mint(ADMIN_UUID)}"},
                      json={"part_number": "VR11S 1010 016 000",
                            "part_name": "CARPET EMERGENCY EXIT HATCH",
                            "drawing_number_issue": "VR11S 1010-10/D",
                            "default_weight_kg": "0.413", "category": "CARPET",
                            "po_pos": "050"})


async def test_match_and_unmatched(client):
    await _seed_part(client)
    text = (
        "Nr. 20189798\nDatum 08.06.2026\n"
        "1 6060 1 STK\nCARPET EMERG. EXIT HATCH\nBauteil-Index: D\n"
        "Ihre Nr. VR11S1010016000\nAuftrag Nr. 1024738 / 5\n"
        "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett\n"
        "2 9999 1 STK\nUNKNOWN PART\nIhre Nr. VR11S9999999999\n"
        "Auftrag Nr. 1024738 / 9\nBestelldaten 4501119979/A350/CCRC/MSN830/6-Bett\n"
    )
    parsed = parse_lieferschein_text(text)
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        md = await match_positions(db, parsed, "LS.pdf")
    assert md.compartment == "CCRC" and md.bed_config == "6"
    assert md.set_title == "SET 6 BED CCRC"
    assert md.po_number == "4501119979"
    matched = [i for i in md.items if i.match_status == "matched"]
    unmatched = [i for i in md.items if i.match_status == "unmatched"]
    assert len(matched) == 1 and len(unmatched) == 1
    m = matched[0]
    assert m.part_name == "CARPET EMERGENCY EXIT HATCH"
    assert m.drawing_number_issue == "VR11S 1010-10/D"
    assert str(m.weight_kg) == "0.413"
    assert m.po_pos == "050"
