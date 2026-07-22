"""Unit tests for ATR po_pos normalization."""
import pytest

from app.services.atr_format import normalize_po_pos


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", "010"),
        ("12", "120"),
        ("5", "050"),
        ("50", "500"),
        ("500", "500"),      # already 3 digits -> idempotent
        ("050", "050"),      # idempotent
        (" 50 ", "500"),
        ("0", "000"),
        ("", ""),
        (None, None),
        ("A12", "A12"),
        ("1234", "1234"),
        ("12/3", "12/3"),
    ],
)
def test_normalize_po_pos(value, expected):
    assert normalize_po_pos(value) == expected
