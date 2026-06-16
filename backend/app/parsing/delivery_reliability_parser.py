"""dev_excel_Liefertreue_Einkauf.txt parser (Einkauf / OTD, v1.60).

Tab-separated, cp1252 export with one row per supplier delivery position.
Layout:
    * Row 1 (optional) — "Auswertung: Liefertreue (von DD.MM.YYYY bis
      DD.MM.YYYY)". Parsed for the evaluation period; skipped otherwise.
    * Header row — the canonical column names.
    * Data rows — one delivery position each.

Column mapping (only the columns the OTD KPI needs are typed; the full row
is kept under ``raw``):
    * "Auftrag" / "Pos" / "UPos" -> auftrag / pos / upos  (business key)
    * "Kundennummer"             -> adr_nr               (supplier address no.)
    * "Kunde"                    -> supplier_name
    * "geliefert"                -> delivered_date       (drives the window)
    * "Lieferdatum"              -> target_date
    * "Verzug (Tage)"            -> verzug_tage           (signed; the OTD
                                                          on-time classifier)
    * "Menge" / "ME"            -> quantity / unit
    * "Artikel" / "Bezeichnung" -> article_number / article_name

The parser stays pure and returns ``(rows, errors, period)``; the router
decides how to commit and upsert. ``period`` is ``(von, bis)`` or ``None``.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("Auftrag", "Pos", "Verzug (Tage)")

# "von 01.01.2026 bis 30.04.2026" anywhere on the Auswertung title line.
_PERIOD_RE = re.compile(
    r"von\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+bis\s+(\d{1,2}\.\d{1,2}\.\d{4})"
)


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


def _parse_period(line: str) -> tuple[date, date] | None:
    m = _PERIOD_RE.search(line)
    if not m:
        return None
    von, bis = _parse_date(m.group(1)), _parse_date(m.group(2))
    if von and bis:
        return von, bis
    return None


def parse_delivery_reliability_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[date, date] | None]:
    """Parse a Liefertreue export. Returns ``(rows, errors, period)``."""
    text = contents.decode("cp1252", errors="replace")
    lines = text.splitlines()

    # Locate the header line (carries the known columns); any preceding line
    # may hold the Auswertung period.
    header_idx = 0
    for i, line in enumerate(lines[:5]):
        if "Auftrag" in line and "Verzug" in line:
            header_idx = i
            break

    period: tuple[date, date] | None = None
    for line in lines[:header_idx]:
        period = _parse_period(line) or period

    body = "\n".join(lines[header_idx:])
    try:
        df = pd.read_csv(
            io.StringIO(body),
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:  # pragma: no cover — malformed input
        return [], [{"row": 0, "column": "", "message": f"unreadable: {exc}"}], period

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
            period,
        )

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()

    for idx, raw in df.iterrows():
        row_num = int(idx) + 1 + header_idx + 1  # header offset + 1-indexed

        auftrag = _clean(raw.get("Auftrag", ""))
        if not auftrag:
            errors.append({
                "row": row_num,
                "column": "Auftrag",
                "message": "missing Auftrag number",
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

        key = (auftrag, pos, upos)
        if key in seen:
            errors.append({
                "row": row_num,
                "column": "Auftrag",
                "message": (
                    f"duplicate (auftrag={auftrag}, pos={pos}, upos={upos}) "
                    "in file"
                ),
            })
            continue
        seen.add(key)

        rows.append({
            "auftrag": auftrag,
            "pos": pos,
            "upos": upos,
            "adr_nr": _clean(raw.get("Kundennummer", "")) or None,
            "supplier_name": _clean(raw.get("Kunde", "")) or None,
            "delivered_date": _parse_date(raw.get("geliefert", "")),
            "target_date": _parse_date(raw.get("Lieferdatum", "")),
            "verzug_tage": _parse_int(raw.get("Verzug (Tage)", ""), default=None),
            "quantity": _parse_decimal(raw.get("Menge", "")),
            "unit": _clean(raw.get("ME", "")) or None,
            "article_number": _clean(raw.get("Artikel", "")) or None,
            "article_name": _clean(raw.get("Bezeichnung", "")) or None,
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors, period
