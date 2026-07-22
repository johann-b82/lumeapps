"""Shared ATR value formatting helpers."""
from __future__ import annotations


def normalize_po_pos(value: str | None) -> str | None:
    """Format a purely numeric PO position: append a trailing zero, then
    left-pad with zeros to 3 digits.

    ``"1" -> "010"``, ``"12" -> "120"``, ``"5" -> "050"``. Values that are
    already 3 digits are returned unchanged so the function stays idempotent
    (it runs on schema I/O *and* at document build time). Empty, non-numeric,
    or longer-than-3-digit values are returned unchanged. Positions are 1–2
    digits in practice, so a 3-digit input is treated as already formatted.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped.isdigit():
        return value
    if len(stripped) == 3:
        return stripped
    if len(stripped) <= 2:
        return (stripped + "0").zfill(3)
    return value
