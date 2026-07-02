from decimal import Decimal

from app.schemas import AtrPartCreate, AtrImportPreview


def test_part_create_defaults():
    p = AtrPartCreate(part_number="VR11S 1010 016 000")
    assert p.qty == 1
    assert p.default_weight_kg is None


def test_import_preview_shape():
    pv = AtrImportPreview(
        source_filename="x.xlsx", header={}, parts=[],
        new_count=0, updated_count=0, unchanged_count=0, warnings=[],
    )
    assert pv.new_count == 0
    # Decimal accepted where present
    AtrPartCreate(part_number="X", default_weight_kg=Decimal("1.2"))
