"""AswKpf_WE Wareneingang parser (v1.67).

Reads the Windows-1252, tab-separated AswKpf_WE export — one row per
Wareneingang-Position. Mirrors :mod:`delivery_parser` (the
LS / Lieferschein twin), but the source is a .txt with cp1252 encoding
rather than an .xlsx workbook.

Mapping highlights:
    * "Typ"           -> typ            (filter on 'WE')
    * "Vorgang Nr."   -> vorgang_nr     (Wareneingang-Nr, business key 1/3)
    * "Pos" / "UPos"  -> pos / upos     (2/3, 3/3)
    * "Datum"         -> entry_date     (Erfassungsdatum)
    * "Lieferdatum"   -> receipt_date   (drives the complaint-rate bucket)
    * "Adr Nr."       -> supplier_id    (join key to SupplierClassification)
    * "Name 1"        -> supplier_name
    * "Artnr"         -> article_number
    * "Bezeichnung 1" -> article_name
    * "Menge"         -> quantity
    * "ME"            -> unit
    * "Bestellung"    -> order_nr
    * "Datum.1"       -> order_date     (pandas renames the second "Datum"
                                         column to disambiguate)
    * "WGR"           -> material_group (e.g. STOFF, METALL, LEDER)
    * "EK Konto"      -> purchase_account

The parser stays pure and returns ``(rows, errors)``; the router decides
how to commit + how to upsert.
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
    if s.lower() == "nan":
        return ""
    return s


def _parse_int(val: str, default: int | None = None) -> int | None:
    s = _clean(val)
    if not s:
        return default
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _parse_decimal(val: str) -> Decimal | None:
    s = _clean(val)
    if not s:
        return None
    # German format: '5,25' -> 5.25; '1.234,56' -> 1234.56
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
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_goods_receipt_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse an AswKpf_WE .txt file (tab-separated, cp1252).

    Returns ``(rows, errors)``. Each row dict matches GoodsReceiptRecord
    column names (minus ``id`` / ``upload_batch_id``) and is ready for
    the upsert path.
    """
    df = None
    # Cp1252 is the canonical encoding for this export (German umlauts
    # like 'ß'/'ü' in supplier names). We still try utf-8 first in case
    # a future re-export uses a sane encoding.
    for encoding in ("utf-8", "cp1252", "iso-8859-1"):
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
    if df is None:
        return [], [{
            "row": 0,
            "column": "",
            "message": "Unable to decode file (tried utf-8, cp1252, iso-8859-1)",
        }]

    # Normalise headers — strip whitespace but preserve casing. Pandas
    # auto-disambiguates duplicate column names with a ``.1`` suffix so
    # the second 'Datum' (= Bestelldatum) lands at 'Datum.1'.
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
        # The dashboard only counts Wareneingang rows. Other Typ values
        # (Bestellungen, Stornos, …) are silently dropped — no error so
        # a mixed export doesn't produce a wall of warnings.
        if typ and typ.upper() != "WE":
            continue

        vorgang_nr = _clean(raw.get("Vorgang Nr.", ""))
        if not vorgang_nr:
            errors.append({
                "row": row_num,
                "column": "Vorgang Nr.",
                "message": "missing Wareneingang number",
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
            "receipt_date": _parse_date(raw.get("Lieferdatum", "")),
            "supplier_id": _clean(raw.get("Adr Nr.", "")) or None,
            "supplier_name": _clean(raw.get("Name 1", "")) or None,
            "supplier_city": _clean(raw.get("Ort", "")) or None,
            "article_number": _clean(raw.get("Artnr", "")) or None,
            "article_version": _clean(raw.get("Version", "")) or None,
            "article_name": _clean(raw.get("Bezeichnung 1", "")) or None,
            "quantity": _parse_decimal(raw.get("Menge", "")),
            "unit": _clean(raw.get("ME", "")) or None,
            "price": _parse_decimal(raw.get("Preis", "")),
            "position_value": _parse_decimal(raw.get("Pos Wert", "")),
            "order_nr": _clean(raw.get("Bestellung", "")) or None,
            # pandas auto-disambiguates the duplicate "Datum" column with
            # a .1 suffix — the second one is the Bestelldatum.
            "order_date": _parse_date(raw.get("Datum.1", "")),
            "material_group": _clean(raw.get("WGR", "")) or None,
            "purchase_account": _clean(raw.get("EK Konto", "")) or None,
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors
