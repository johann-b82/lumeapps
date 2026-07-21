"""Shared ATR value formatting helpers."""
from __future__ import annotations


def normalize_po_pos(value: str | None) -> str | None:
    """Pad a purely numeric PO position to 3 digits with leading zeros.

    ``"5" -> "005"``, ``"50" -> "050"``. Empty, non-numeric, or already
    longer-than-3-digit values are returned unchanged.
    """
    if value is None:
        return None
    stripped = value.strip()
    if stripped.isdigit() and len(stripped) <= 3:
        return stripped.zfill(3)
    return value
