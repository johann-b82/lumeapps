"""AswKpf_WE.txt parser (Wareneingang / material prices, v1.63).

Finance-scoped parser for the Materialkostenquote price lookup. Tab-separated,
cp1252 export with one row per goods-receipt position. Layout:
    * Header row — the canonical column names.
    * Data rows — one WE position each.

Only the columns the price lookup needs are typed; the full row is kept under
``raw``. Mapping:
    * "Vorgang Nr." / "Pos" / "UPos" -> vorgang_nr / pos / upos  (business key)
    * "Typ"                          -> typ
    * "Datum"                        -> datum     (the "newest date" selector)
    * "Artnr"                        -> artnr     (join key to movements)
    * "Bezeichnung 1"                -> article_name
    * "Menge" / "ME"                -> menge / unit
    * "Preis"                        -> preis      (raw price, may be per 100/1000)
    * "Pos Wert"                     -> pos_wert   (effective unit price = / menge)

NB: the source carries two "Datum" columns (WE date + Bestelldatum); pandas
de-duplicates the second to "Datum.1", so ``raw.get("Datum")`` is the WE date.

The parser stays pure and returns ``(rows, errors)``. Within-file duplicate
``(vorgang_nr, pos, upos)`` tuples are reported and skipped.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("Vorgang Nr.", "Pos", "Artnr")


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


def parse_material_prices_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse an AswKpf_WE export. Returns ``(rows, errors)``."""
    text = contents.decode("cp1252", errors="replace")
    lines = text.splitlines()

    header_idx = 0
    for i, line in enumerate(lines[:5]):
        if "Vorgang Nr." in line and "Artnr" in line:
            header_idx = i
            break

    body = "\n".join(lines[header_idx:])
    try:
        df = pd.read_csv(
            io.StringIO(body),
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:  # pragma: no cover — malformed input
        return [], [{"row": 0, "column": "", "message": f"unreadable: {exc}"}]

    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return (
            [],
            [{
                "row": 0,
                "column": ",".join(missing),
                "message": f"Required column(s) missing: {', '.join(missing)}",
            }],
        )

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()

    for idx, raw in df.iterrows():
        row_num = int(idx) + 1 + header_idx + 1  # header offset + 1-indexed

        vorgang_nr = _clean(raw.get("Vorgang Nr.", ""))
        if not vorgang_nr:
            errors.append({
                "row": row_num,
                "column": "Vorgang Nr.",
                "message": "missing Vorgang Nr.",
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

        artnr = _clean(raw.get("Artnr", ""))
        if not artnr:
            errors.append({
                "row": row_num,
                "column": "Artnr",
                "message": "missing Artnr",
            })
            continue

        key = (vorgang_nr, pos, upos)
        if key in seen:
            errors.append({
                "row": row_num,
                "column": "Vorgang Nr.",
                "message": (
                    f"duplicate (vorgang_nr={vorgang_nr}, pos={pos}, "
                    f"upos={upos}) in file"
                ),
            })
            continue
        seen.add(key)

        rows.append({
            "vorgang_nr": vorgang_nr,
            "pos": pos,
            "upos": upos,
            "typ": _clean(raw.get("Typ", "")) or None,
            "datum": _parse_date(raw.get("Datum", "")),
            "artnr": artnr,
            "article_name": _clean(raw.get("Bezeichnung 1", "")) or None,
            "menge": _parse_decimal(raw.get("Menge", "")),
            "unit": _clean(raw.get("ME", "")) or None,
            "preis": _parse_decimal(raw.get("Preis", "")),
            "pos_wert": _parse_decimal(raw.get("Pos Wert", "")),
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors
