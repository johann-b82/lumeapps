"""AswQs2151 Qualitätsprüfung parser (v1.79).

Reads the Windows-1252, tab-separated ``AswQs2151.txt`` export — one row
per Qualitätsprüfung booking (Datum / Zeit / Benutzer / FA / Artikel /
Bezeichnung / Buchungs-Menge / …). Mirrors :mod:`goods_receipt_parser`
for the encoding / decimal handling.

**Size classification** — the parser labels every row ``large`` or
``small`` at parse time so the aggregation layer stays a plain SUM. The
rule (agreed with the customer, 2026-07-13):

    KLEIN if bezeichnung matches Literature Pocket, Straps / Riemen,
    any Net / Netz variant, or Life-Vest / Stowage Pouch — OR the
    Produktgruppe belongs to the Diehl catalogue (any ``*_DIEHL``
    group, incl. LITPOC_DIEHL and KLEINT_DIEHL). Everything else —
    including all Curtains, Carpets, Seats, Flaps — is GROSS.

Werkzeug rows (``typ='WKZ'``) are dropped: they're tools, not products.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ("Datum", "Bezeichnung", "Buchungs-Menge")

# --- Size-class classifier --------------------------------------------------
#
# Case-insensitive substring matches. Order does not matter — any hit
# routes the row to ``small``.
_SMALL_KEYWORDS = (
    # Lit.Pock
    "LITERATURE POCKET",
    "LIT POCKET",
    # Straps
    "STRAP ",
    "STRAP,",
    "LEDERRIEMEN",
    # LVP (Life Vest Pouch / Aufbewahrungstasche)
    "STOWAGE POUCH",
    "AUFBEWAHRUNGSTASCHE",
)
# NET / NETZ — matched with a word boundary so plain "internet",
# "carpet-net…" etc. don't accidentally trigger the classifier.
# Includes "Leder mit Netztaschen" (Sitzbezug mit Netz) per customer
# ruling 2026-07-13: any "netz" hit counts as small.
_NET_RE = re.compile(r"(?i)(?:^|[^a-z])(net|netz)")


def classify_size(bezeichnung: str | None, produktgruppe: str | None) -> str:
    """Return 'small' or 'large' per the customer's classification rule."""
    bez = (bezeichnung or "").upper()
    pg = (produktgruppe or "").upper()

    # Any Diehl-catalogue Produktgruppe (LITPOC_DIEHL, KLEINT_DIEHL, …)
    # counts as small per customer ruling 2026-07-13.
    if "DIEHL" in pg:
        return "small"
    if any(k in bez for k in _SMALL_KEYWORDS):
        return "small"
    if _NET_RE.search(bez):
        return "small"
    return "large"


# --- Value cleaners (shared with other parsers, kept local to avoid a
#     circular import) ------------------------------------------------------

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


def _parse_time(val: Any) -> time | None:
    s = _clean(val)
    if not s:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def parse_inspection_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse an AswQs2151 .txt file (tab-separated, cp1252).

    Returns ``(rows, errors)``. Each row dict matches
    :class:`app.models.InspectionRecord` column names (minus ``id`` and
    ``upload_batch_id``) and includes the derived ``size_class``.
    """
    _ = filename  # accepted for symmetry with other parsers
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

    for idx, raw in df.iterrows():
        row_num = int(idx) + 2  # 1-indexed + header offset

        typ = _clean(raw.get("Typ", ""))
        # Werkzeug rows (WKZ) are not products — drop silently.
        if typ.upper() == "WKZ":
            continue

        pruef_datum = _parse_date(raw.get("Datum", ""))
        if pruef_datum is None:
            errors.append({
                "row": row_num,
                "column": "Datum",
                "message": "missing or unparseable Datum",
            })
            continue

        bezeichnung = _clean(raw.get("Bezeichnung", ""))
        produktgruppe = _clean(raw.get("Produktgruppe", ""))
        size_class = classify_size(bezeichnung, produktgruppe)

        rows.append({
            "pruef_datum": pruef_datum,
            "pruef_zeit": _parse_time(raw.get("Zeit", "")),
            "benutzer": _clean(raw.get("Benutzer", "")) or None,
            "fa": _clean(raw.get("FA", "")) or None,
            "artikel": _clean(raw.get("Artikel", "")) or None,
            "bezeichnung": bezeichnung or None,
            "buchungs_menge": _parse_decimal(raw.get("Buchungs-Menge", "")),
            "ausschuss_menge": _parse_decimal(raw.get("Ausschuss-Menge", "")),
            "produktgruppe": produktgruppe or None,
            "typ": typ or None,
            "size_class": size_class,
            # v1.81 — Kostenschlüssel; only "70000" rows drive the KPI,
            # but every value lands in the DB so we don't lose the raw
            # ERP context.
            "rsc": _clean(raw.get("RSC", "")) or None,
            "raw": {k: _clean(v) for k, v in raw.items()},
        })

    return rows, errors
