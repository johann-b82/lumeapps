"""Kontakte (sales contact log) parser.

Reads the ISO-8859-1, tab-separated dump from the source ERP. Supports
two header layouts:

  * **v1.41 (legacy, 8 cols)** — ``Datum / Wer / Typ / Gruppe / Sta /
    Name / Kommentar / VrgID``, cells optionally wrapped in ``="…"``
    quotes.
  * **v1.60+ (current, 16 cols)** — ``Datum / Zeit / W-Vorlage /
    Ansprechpartner / Art / Typ / St / Mitarbeiter / Name 1 / Ort /
    Erf. Datum / Erf. Benutzer / Textfeld / Typ / Vorgang Nr. / Wert``.
    Note the duplicate ``Typ`` header — the first one carries the
    contact type (ERS / ORT / ONL / EMAIL / TEL / …); the second one
    carries the ERP linkage type (ANG / RG / etc.) and is ignored.

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


def _dedupe_columns(cols: list[str]) -> list[str]:
    """Deduplicate column names by appending ``.N`` to repeats.

    The current Kontakte export has ``Typ`` twice (contact type +
    ERP-linkage type). pandas' ``read_csv`` would auto-dedupe in
    column-name space, but we re-assign ``df.columns`` after
    unquoting — so we own the dedupe step ourselves.
    """
    seen: dict[str, int] = {}
    out: list[str] = []
    for c in cols:
        if c in seen:
            seen[c] += 1
            out.append(f"{c}.{seen[c]}")
        else:
            seen[c] = 0
            out.append(c)
    return out


def _pick(raw: Any, *names: str) -> str:
    """Try each column name in order — return the first populated cell.

    Lets the parser handle both the legacy (``Wer / Sta / Kommentar``)
    and current (``Mitarbeiter / St / Textfeld``) header sets without
    branching at the call site.
    """
    for n in names:
        v = _unquote(raw.get(n, ""))
        if v:
            return v
    return ""


def parse_kontakte_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a Kontakte tab-separated dump.

    Returns ``(rows, errors)``; each entry in ``rows`` already carries
    the canonical ``SalesContact`` field names. ``raw`` keeps every
    original cell keyed by header so future fields can be re-derived
    without re-uploading.
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

    df.columns = _dedupe_columns([_unquote(c) for c in df.columns])

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for idx, raw in df.iterrows():
        # v1.60+ → "Mitarbeiter"; legacy v1.41 → "Wer". Uppercased so
        # downstream aggregation can group by a stable token.
        wer = _pick(raw, "Mitarbeiter", "Wer").upper()
        d = _parse_date(_pick(raw, "Datum"))
        if d is None or not wer:
            errors.append({
                "row": int(idx) + 2,
                "field": "Datum/Mitarbeiter",
                "message": "missing or unparseable",
            })
            continue
        sta_raw = _pick(raw, "St", "Sta")
        try:
            sta = int(sta_raw) if sta_raw else 0
        except ValueError:
            sta = 0
        if sta not in (0, 1):
            sta = 0
        rows.append({
            "contact_date": d,
            "employee_token": wer,
            # First "Typ" column carries the contact-type code
            # (ERS / ORT / ONL / EMAIL / TEL / …). The second "Typ"
            # is the ERP-linkage type and is dropped (kept in raw).
            "contact_type": _pick(raw, "Typ") or None,
            # v1.60+ has no "Gruppe" column — kept None on new files.
            # Legacy fixtures still set it.
            "customer_group": _pick(raw, "Gruppe") or None,
            "status": sta,
            "customer_name": _pick(raw, "Name 1", "Name") or None,
            "comment": _pick(raw, "Textfeld", "Kommentar") or None,
            "external_id": _pick(raw, "Vorgang Nr.", "VrgID") or None,
            "raw": {k: _unquote(v) for k, v in raw.items()},
        })
    return rows, errors
