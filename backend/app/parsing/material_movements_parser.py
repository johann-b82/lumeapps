"""AswLagBew.txt parser (Lagerbewegung / material movements, v1.63).

Tab-separated, cp1252 export with one row per stock movement. Layout:
    * Header row — the canonical column names.
    * Data rows — one movement each.

Only the columns the Materialkostenquote needs are typed; the full row is
kept under ``raw``. Mapping:
    * "Artikelnr"      -> artikelnr        (join key to material_prices.artnr)
    * "Bezeichnung 1"  -> article_name
    * "BuchDatum"      -> buch_datum       (drives the window + replace range)
    * "Bewegungsmenge" -> bewegungsmenge   (signed; M negative, SM positive)
    * "BuchTyp"        -> buchtyp          (M / SM filtered by the aggregation)
    * "Kommentar"      -> kommentar

The parser stays pure and returns ``(rows, errors)``; the router decides how
to commit (replace-by-date-range). Rows without an Artikelnr or an
unparseable BuchDatum are reported as errors and skipped.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("Artikelnr", "BuchDatum", "Bewegungsmenge", "BuchTyp")

# The ERP exports the Lagerbewegung under two different header layouts. The
# canonical (older) names are the REQUIRED_COLUMNS above; the newer export uses
# short names. We rename the new → canonical when the canonical is absent, so
# both files import unchanged. ``Bezeichnung`` → ``Bezeichnung 1`` likewise.
_COLUMN_ALIASES = {
    "Artikel": "Artikelnr",
    "Datum": "BuchDatum",
    "Menge": "Bewegungsmenge",
    "Typ": "BuchTyp",
    "Bezeichnung": "Bezeichnung 1",
}


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


def parse_material_movements_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse an AswLagBew export. Returns ``(rows, errors)``."""
    text = contents.decode("cp1252", errors="replace")
    lines = text.splitlines()

    header_idx = 0
    for i, line in enumerate(lines[:5]):
        cols = {c.strip() for c in line.split("\t")}
        has_article = "Artikelnr" in cols or "Artikel" in cols
        has_type = "BuchTyp" in cols or "Typ" in cols
        if has_article and has_type:
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
    # Normalise the newer short-header layout to the canonical column names.
    df = df.rename(
        columns={
            src: dst
            for src, dst in _COLUMN_ALIASES.items()
            if src in df.columns and dst not in df.columns
        }
    )

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

    for idx, raw in df.iterrows():
        row_num = int(idx) + 1 + header_idx + 1  # header offset + 1-indexed

        artikelnr = _clean(raw.get("Artikelnr", ""))
        if not artikelnr:
            errors.append({
                "row": row_num,
                "column": "Artikelnr",
                "message": "missing Artikelnr",
            })
            continue

        buch_datum = _parse_date(raw.get("BuchDatum", ""))
        if buch_datum is None:
            errors.append({
                "row": row_num,
                "column": "BuchDatum",
                "message": "missing or unparseable BuchDatum",
            })
            continue

        rows.append({
            "artikelnr": artikelnr,
            "article_name": _clean(raw.get("Bezeichnung 1", "")) or None,
            "buch_datum": buch_datum,
            "bewegungsmenge": _parse_decimal(raw.get("Bewegungsmenge", "")),
            "buchtyp": _clean(raw.get("BuchTyp", "")) or None,
            "kommentar": _clean(raw.get("Kommentar", "")) or None,
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors
