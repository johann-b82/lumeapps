from app.schemas import AtrDeliveryRead, AtrDeliveryItemUpdate


def test_item_update_partial():
    u = AtrDeliveryItemUpdate(weight_kg="1.25")
    assert u.po_pos is None


def test_delivery_read_has_items_field():
    assert "items" in AtrDeliveryRead.model_fields
