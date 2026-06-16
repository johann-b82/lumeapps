"""8D report parser (v1.49).

Reads the Windows-1252, tab-separated 8D.txt dump used by the Quality
dashboard. Each row is one 8D report (audit finding or complaint).

Two source columns drive the KPI:
    * "Art"     — audit-type code (BH AUD, EX AUD, IN AUD, KU AUD,
                  empty for Reklamationen). Stored verbatim.
    * "Artikel" — long text; "Audit Major Level 1" → level=1,
                  "Audit Minor Level 2" → level=2, else None.

Rows where "gelöscht" == "J" are dropped at parse time (the source
flags soft-deleted reports there). Rows missing "Nr." or "Datum" are
reported as errors and skipped.

The router decides which `art` codes count as audits — the parser stays
pure and ingests everything so the future complaints branch can read
from the same table.
"""
from __future__ import annotations

import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd


def _parse_decimal(val: str) -> Decimal | None:
    """Parse a German-formatted numeric cell to Decimal.

    Accepts both German format (1.234,56) and plain (1234.56). Returns
    None on empty / unparseable input — the rate calc treats None as
    "unknown quantity, exclude from the sum".
    """
    s = (val or "").strip()
    if not s:
        return None
    # Heuristic: if both '.' and ',' present, '.' is thousands and ',' is decimal.
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

# "Audit Major Level 1" / "Audit Minor Level 2" — match by descriptor +
# explicit level token so trailing whitespace, casing tweaks or stray
# punctuation in the source ("Audit Major Level 1 ") still classify.
_LEVEL_MAJOR_RE = re.compile(r"\bMajor\b.*\bLevel\s*1\b", re.IGNORECASE)
_LEVEL_MINOR_RE = re.compile(r"\bMinor\b.*\bLevel\s*2\b", re.IGNORECASE)

_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")


def _clean(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _parse_date(val: str) -> date | None:
    m = _DATE_RE.match(val)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None


def _classify_level(artikel: str) -> int | None:
    """Map the "Artikel" column to a level integer (1 / 2) or None."""
    if not artikel:
        return None
    if _LEVEL_MAJOR_RE.search(artikel):
        return 1
    if _LEVEL_MINOR_RE.search(artikel):
        return 2
    return None


def parse_quality_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a Windows-1252 tab-separated 8D dump.

    Returns ``(rows, errors)``. Each row dict matches QualityRecord
    column names (minus ``id`` / ``upload_batch_id``) and is ready for
    bulk insert.
    """
    # The source file is Windows-1252 (German umlauts: ü = 0xFC, ß = 0xDF).
    # We still try utf-8 first so a future re-export in a sane encoding
    # works without a code change.
    df = None
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

    # Normalise headers — strip surrounding whitespace, but keep the
    # German spelling so we can look up "Nr." / "Datum" / etc. verbatim.
    df.columns = [str(c).strip() for c in df.columns]

    required = ("Nr.", "Datum", "Artikel", "Art")
    missing = [c for c in required if c not in df.columns]
    if missing:
        return [], [{
            "row": 0,
            "column": ",".join(missing),
            "message": f"Required column(s) missing: {', '.join(missing)}",
        }]

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_report_nrs: set[str] = set()

    for idx, raw in df.iterrows():
        row_num = int(idx) + 2  # 1-indexed + header offset
        report_nr = _clean(raw.get("Nr.", ""))

        # Skip soft-deleted rows from the source. The column may be
        # absent on older exports; default to "" (= keep) in that case.
        deleted_flag = _clean(raw.get("gelöscht", "")).upper()
        if deleted_flag == "J":
            continue

        if not report_nr:
            errors.append({
                "row": row_num,
                "column": "Nr.",
                "message": "missing report number",
            })
            continue

        # In-file deduplication: keep the first occurrence, treat
        # subsequent ones as soft errors (UNIQUE constraint would also
        # catch them, but a clean error is friendlier than a 500).
        if report_nr in seen_report_nrs:
            errors.append({
                "row": row_num,
                "column": "Nr.",
                "message": f"duplicate report number {report_nr!r} in file",
            })
            continue
        seen_report_nrs.add(report_nr)

        report_date = _parse_date(_clean(raw.get("Datum", "")))
        if report_date is None:
            errors.append({
                "row": row_num,
                "column": "Datum",
                "message": f"unparseable date {_clean(raw.get('Datum', ''))!r}",
            })
            continue

        art = _clean(raw.get("Art", "")) or None
        level = _classify_level(_clean(raw.get("Artikel", "")))

        rows.append({
            "report_nr": report_nr,
            "report_date": report_date,
            "art": art,
            "level": level,
            "issuer": _clean(raw.get("Aussteller", "")) or None,
            "customer_name": _clean(raw.get("Adressen", "")) or None,
            "customer_id": _clean(raw.get("Adress Nr.", "")) or None,
            "designation": _clean(raw.get("Bezeichnung", "")) or None,
            "status_code": _clean(raw.get("Status", "")) or None,
            "problem_description": _clean(raw.get("Problembeschreibung", "")) or None,
            "root_cause": _clean(raw.get("Ursache", "")) or None,
            # v1.59: Mengen (Spalten K + L). Both columns are optional in
            # older 8D exports; missing = NULL = excluded from the
            # complaint-rate sum (the rate ignores rows without a number).
            "quantity": _parse_decimal(_clean(raw.get("Menge", ""))),
            "accepted_quantity": _parse_decimal(
                _clean(raw.get("akzeptierte Menge", ""))
            ),
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors
