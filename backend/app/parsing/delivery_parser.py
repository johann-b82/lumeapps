"""AswKpf_LS.xlsx Lieferschein parser (v1.58).

Reads the openpyxl-backed export with one row per delivery-note position.
Mapping highlights:
    * "Typ"           -> typ            (filter on 'LS' — the file may
                                         eventually carry other Vorgang-
                                         types we don't want to count)
    * "Vorgang Nr."   -> vorgang_nr     (Lieferschein-Nr, business key 1/3)
    * "Pos" / "UPos"  -> pos / upos     (business key 2/3, 3/3)
    * "Datum"         -> entry_date     (Erfassungsdatum)
    * "Lieferdatum"   -> delivery_date  (drives the complaint-rate bucket)
    * "Adr Nr."       -> customer_id
    * "Name 1"        -> customer_name
    * "Artnr"         -> article_number
    * "Bezeichnung 1" -> article_name
    * "Menge"         -> quantity
    * "ME"            -> unit
    * "Preis", "Pos Wert", "Fremdnr", "Auftrag" -> position-level extras

The parser stays pure and returns ``(rows, errors)``; the router decides
how to commit and how to upsert.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("Vorgang Nr.", "Pos", "Menge")


def _clean(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    # pandas reads NaN cells as the literal string 'nan' when dtype=str.
    if s.lower() == "nan":
        return ""
    return s


def _parse_int(val: str, default: int | None = None) -> int | None:
    s = _clean(val)
    if not s:
        return default
    try:
        # Excel often serialises ints as "1.0"; tolerate.
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _parse_decimal(val: str) -> Decimal | None:
    s = _clean(val)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_date(val: Any) -> date | None:
    """Cope with the multiple date shapes Excel + pandas emit.

    openpyxl with dtype=str renders date cells as ISO strings
    ("2026-01-06 00:00:00"). Pure-string cells also flow through unchanged.
    """
    s = _clean(val)
    if not s:
        return None
    # ISO with optional time component.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_delivery_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse an AswKpf_LS.xlsx file.

    Returns ``(rows, errors)``. Each row dict matches DeliveryRecord
    column names (minus ``id`` / ``upload_batch_id``) and is ready for
    the upsert path.
    """
    try:
        df = pd.read_excel(
            io.BytesIO(contents),
            dtype=str,
            engine="openpyxl",
            keep_default_na=False,
        )
    except Exception as exc:  # pragma: no cover — surfaces malformed inputs
        return [], [{"row": 0, "column": "", "message": f"unreadable: {exc}"}]

    # Normalise headers — strip whitespace but preserve casing.
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [], [{
            "row": 0,
            "column": ",".join(missing),
            "message": f"Required column(s) missing: {', '.join(missing)}",
        }]

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    # Composite-key dedup inside one file — defends against an export
    # that accidentally emitted the same (vorgang, pos, upos) twice.
    seen: set[tuple[str, int, int]] = set()

    for idx, raw in df.iterrows():
        row_num = int(idx) + 2  # 1-indexed + header offset

        typ = _clean(raw.get("Typ", ""))
        # The dashboard only counts Lieferschein rows. Other Typ values
        # (returns, samples, …) are silently dropped — no error so the
        # uploader doesn't get a wall of warnings on a mixed export.
        if typ and typ.upper() != "LS":
            continue

        vorgang_nr = _clean(raw.get("Vorgang Nr.", ""))
        if not vorgang_nr:
            errors.append({
                "row": row_num,
                "column": "Vorgang Nr.",
                "message": "missing Lieferschein number",
            })
            continue

        pos = _parse_int(raw.get("Pos", ""), default=None)
        if pos is None:
            errors.append({
                "row": row_num,
                "column": "Pos",
                "message": "missing or unparseable Pos",
            })
            continue
        upos = _parse_int(raw.get("UPos", ""), default=0) or 0

        key = (vorgang_nr, pos, upos)
        if key in seen:
            errors.append({
                "row": row_num,
                "column": "Vorgang Nr.",
                "message": (
                    f"duplicate (vorgang={vorgang_nr}, pos={pos}, upos={upos}) "
                    "in file"
                ),
            })
            continue
        seen.add(key)

        rows.append({
            "vorgang_nr": vorgang_nr,
            "pos": pos,
            "upos": upos,
            "typ": typ or None,
            "entry_date": _parse_date(raw.get("Datum", "")),
            "delivery_date": _parse_date(raw.get("Lieferdatum", "")),
            "customer_id": _clean(raw.get("Adr Nr.", "")) or None,
            "customer_name": _clean(raw.get("Name 1", "")) or None,
            "customer_city": _clean(raw.get("Ort", "")) or None,
            "article_number": _clean(raw.get("Artnr", "")) or None,
            "article_version": _clean(raw.get("Version", "")) or None,
            "article_name": _clean(raw.get("Bezeichnung 1", "")) or None,
            "quantity": _parse_decimal(raw.get("Menge", "")),
            "unit": _clean(raw.get("ME", "")) or None,
            "price": _parse_decimal(raw.get("Preis", "")),
            "position_value": _parse_decimal(raw.get("Pos Wert", "")),
            "external_order_nr": _clean(raw.get("Fremdnr", "")) or None,
            "order_nr": _clean(raw.get("Auftrag", "")) or None,
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors
