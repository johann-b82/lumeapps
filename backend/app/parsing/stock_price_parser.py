"""AswLagBew price-list parser (Artikel-Preiskonditionen, v1.106).

Tab-separated, cp1252 export — one row per price condition. This is a price
list, **not** a stock-movement file: it carries the article number in
``Artikelnr3`` (the "L…" Lagerartikel number), the raw price in ``Wert`` and
the price base quantity in ``Preismenge``. The effective unit price is
``Wert / Preismenge`` (the raw ``Wert`` is per 100/1000 pieces).

Only the columns the Lager-Bewertung needs are kept:
    * "Artikelnr3"   -> artnr         (join key to material_movements.artikelnr)
    * "Wert"         -> raw price
    * "Preismenge"   -> price base qty (divisor)
    * "Preiseinheit" -> price_unit
    * "Bezeichnung 1"-> article_name

One price per article: the first row wins (staffel/duplicate rows are skipped).
The parser stays pure and returns ``(rows, errors)``.
"""
from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("Artikelnr3", "Wert", "Preismenge")


def _clean(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    return s


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


def parse_stock_price_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse an AswLagBew price list. Returns ``(rows, errors)``."""
    text = contents.decode("cp1252", errors="replace")
    lines = text.splitlines()

    header_idx = 0
    for i, line in enumerate(lines[:5]):
        if "Artikelnr3" in line and "Preismenge" in line:
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
    seen: set[str] = set()

    for idx, raw in df.iterrows():
        row_num = int(idx) + 1 + header_idx + 1  # header offset + 1-indexed

        artnr = _clean(raw.get("Artikelnr3", ""))
        if not artnr:
            # Many condition rows carry no L-article number — skip silently.
            continue
        if artnr in seen:
            continue  # first price per article wins (skip staffel duplicates)

        wert = _parse_decimal(raw.get("Wert", ""))
        preismenge = _parse_decimal(raw.get("Preismenge", ""))
        if wert is None:
            errors.append({
                "row": row_num,
                "column": "Wert",
                "message": f"missing/unparseable Wert for {artnr}",
            })
            continue
        if not preismenge or preismenge <= 0:
            preismenge = Decimal(1)

        seen.add(artnr)
        rows.append({
            "artnr": artnr,
            "unit_price": wert / preismenge,
            "price_unit": _clean(raw.get("Preiseinheit", "")) or None,
            "article_name": _clean(raw.get("Bezeichnung 1", "")) or None,
        })

    return rows, errors
