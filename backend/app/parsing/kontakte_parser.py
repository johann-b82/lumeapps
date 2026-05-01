"""Kontakte (sales contact log) parser.

Reads the ISO-8859-1, tab-separated, ``="…"``-quoted dump from the
source ERP. Returns a list of dicts ready for ``SalesContact`` insert
plus a list of validation errors (rows skipped because of unparseable
date or empty ``Wer``).

This intentionally does NOT do alias resolution (token → personio
employee). That happens at the router layer so the parser stays pure
and testable.
"""
from __future__ import annotations

import io
import re
from datetime import date
from typing import Any

import pandas as pd

_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_QUOTE_RE = re.compile(r'^="?(.*?)"?$')


def _unquote(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    m = _QUOTE_RE.match(s)
    return (m.group(1) if m else s).strip()


def _parse_date(val: str) -> date | None:
    m = _DATE_RE.match(val)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None


def parse_kontakte_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a Kontakte tab-separated dump.

    Returns ``(rows, errors)`` where each entry in ``rows`` already has
    the canonical SalesContact field names. ``raw`` carries the original
    row keyed by header so we can re-derive fields later without re-
    uploading.
    """
    try:
        df = pd.read_csv(
            io.BytesIO(contents),
            sep="\t",
            encoding="iso-8859-1",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:  # pragma: no cover — surfaces malformed inputs
        return [], [{"row": 0, "field": "file", "message": f"unreadable: {exc}"}]

    df.columns = [_unquote(c) for c in df.columns]

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for idx, raw in df.iterrows():
        wer = _unquote(raw.get("Wer", "")).upper()
        d = _parse_date(_unquote(raw.get("Datum", "")))
        if d is None or not wer:
            errors.append({
                "row": int(idx) + 2,
                "field": "Datum/Wer",
                "message": "missing or unparseable",
            })
            continue
        sta_raw = _unquote(raw.get("Sta", ""))
        try:
            sta = int(sta_raw) if sta_raw else 0
        except ValueError:
            sta = 0
        if sta not in (0, 1):
            sta = 0
        rows.append({
            "contact_date": d,
            "employee_token": wer,
            "contact_type": _unquote(raw.get("Typ", "")) or None,
            "customer_group": _unquote(raw.get("Gruppe", "")) or None,
            "status": sta,
            "customer_name": _unquote(raw.get("Name", "")) or None,
            "comment": _unquote(raw.get("Kommentar", "")) or None,
            "external_id": _unquote(raw.get("VrgID", "")) or None,
            "raw": {k: _unquote(v) for k, v in raw.items()},
        })
    return rows, errors
