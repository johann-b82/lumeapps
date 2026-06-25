from app.models import AtrDelivery, AtrDeliveryItem
from app.database import Base


def test_delivery_tables_registered():
    assert "atr_delivery" in Base.metadata.tables
    assert "atr_delivery_item" in Base.metadata.tables


def test_delivery_item_fk_and_columns():
    cols = {c.name for c in AtrDeliveryItem.__table__.columns}
    assert {"delivery_id", "part_number_norm", "matched_part_id", "weight_kg",
            "po_pos", "match_status", "row_order"} <= cols
    fks = {list(fk.column.table.name for fk in c.foreign_keys)[0]
           for c in AtrDeliveryItem.__table__.columns if c.foreign_keys}
    assert "atr_delivery" in fks


def test_delivery_has_generated_byte_columns():
    cols = {c.name for c in AtrDelivery.__table__.columns}
    assert {"atr_xlsx", "atr_pdf", "label_docx", "status"} <= cols
