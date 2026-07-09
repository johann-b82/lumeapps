"""AswKpf_AUF (position-level) parser (v1.76).

Reads the tab-separated, Latin-1 ``AswKpf_AUF.txt`` export — one row per order
position. Same 21-column shape as the Lieferschein export minus the ``Auftrag`` /
``Pos.1`` back-references (here ``Vorgang Nr.`` *is* the order).

Mapping highlights:
    * "Typ"           -> typ            (filter on 'AUF')
    * "Vorgang Nr."   -> vorgang_nr     (order number, business key 1/3)
    * "Pos" / "UPos"  -> pos / upos     (business key 2/3, 3/3)
    * "Datum"         -> entry_date     (Erfassungsdatum)
    * "Lieferdatum"   -> lieferdatum    (Zieltermin — drives the Verzug KPI)
    * "Adr Nr."       -> customer_id
    * "Name 1"        -> customer_name
    * "Artnr"         -> article_number
    * "Bezeichnung 1" -> article_name
    * "Menge"         -> quantity
    * "Pos Typ 2"     -> pos_typ_2      (only classifier; reserved for a future
                                         Seriengeschäft filter)
    * "Preis", "Pos Wert", "Fremdnr"   -> position-level extras

Pure ``(rows, errors)`` return; the router owns the upsert.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("Vorgang Nr.", "Pos", "Lieferdatum")


def _clean(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    return s


def _parse_int(val: Any, default: int | None = None) -> int | None:
    s = _clean(val)
    if not s:
        return default
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _parse_decimal(val: Any) -> Decimal | None:
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
    s = _clean(val)
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_auftrag_positionen_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a position-level AswKpf_AUF.txt file.

    Returns ``(rows, errors)``. Each row dict matches AuftragPosition column
    names (minus ``id`` / ``upload_batch_id``) and is ready for the upsert.
    """
    for encoding in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(
                io.BytesIO(contents),
                sep="\t",
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
            break
        except UnicodeDecodeError:
            continue
    else:
        return [], [{
            "row": 0,
            "column": "file",
            "message": "Unable to decode file (tried utf-8, latin-1)",
        }]

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
    seen: set[tuple[str, int, int]] = set()

    for idx, raw in df.iterrows():
        row_num = int(idx) + 2  # 1-indexed + header offset

        typ = _clean(raw.get("Typ", ""))
        # Skip fully blank trailing lines (the export pads with empties).
        if not any(_clean(v) for v in raw.to_dict().values()):
            continue
        # Only order positions. Other Typ values are silently dropped.
        if typ and typ.upper() != "AUF":
            continue

        vorgang_nr = _clean(raw.get("Vorgang Nr.", ""))
        if not vorgang_nr:
            errors.append({
                "row": row_num,
                "column": "Vorgang Nr.",
                "message": "missing order number",
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
            "lieferdatum": _parse_date(raw.get("Lieferdatum", "")),
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
            "pos_typ_2": _clean(raw.get("Pos Typ 2", "")) or None,
            "external_order_nr": _clean(raw.get("Fremdnr", "")) or None,
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors
