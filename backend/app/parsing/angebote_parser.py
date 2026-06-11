"""Angebote (sales-offer) parser.

Reads the ``AswKpf_ANG.txt`` ERP export — 18 columns, tab-separated,
Latin-1 (German umlauts: ``Ge\xe4ndert``, ``eigene W\xe4hrung``). No
``="…"`` quoting, unlike the AswKpf_AUF (Aufträge) sibling file.

Six columns are mapped to the ``Offer`` model; the rest are kept in
``raw`` for traceability:

  Vorgang Nr.    -> vorgang_nr   (PK; required)
  Datum          -> datum        (DD.MM.YYYY; required)
  Adr Nr.        -> adr_nr
  Name 1         -> name
  Ort            -> ort
  Erfasst durch  -> erfasser
  Wert           -> wert_eur     (German decimal; required)

Returns ``(valid_rows, errors)``. Caller fills in ``upload_batch_id``
and ``imported_at`` before insert.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd


# Column-letter map (kept for documentation alongside header strings).
# A=Typ B=Vorgang Nr. C=Datum D=Adr Nr. E=Name 1 F=Name 2 G=Name 3
# H=Ort I=Erfasst durch J=Geändert durch K=Anz Pos L=AA M=Typ 2
# N=Rab Aktion O=Wert P=eigene Währung Q=Ges.Wert FW R=WAHR
COL_VORGANG_NR = "Vorgang Nr."
COL_DATUM = "Datum"
COL_ADR_NR = "Adr Nr."
COL_NAME = "Name 1"
COL_ORT = "Ort"
COL_ERFASSER = "Erfasst durch"
COL_WERT = "Wert"


def _parse_german_date(raw: str) -> date | None:
    s = raw.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_german_decimal(raw: str) -> Decimal | None:
    """German format: ``.`` thousands separator, ``,`` decimal point.

    Real samples are mostly plain integers (``84000``) but some carry
    decimals (``322611,16``). Thousands separators have not been
    observed in the field but the normalisation tolerates them.
    """
    s = raw.strip()
    if not s:
        return None
    normalized = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_angebote_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse the AswKpf_ANG offer dump."""
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
        return ([], [{
            "row": 0,
            "field": "file",
            "message": "Unable to decode file (tried utf-8, latin-1)",
        }])

    df.columns = [c.strip() for c in df.columns]

    required = [COL_VORGANG_NR, COL_DATUM, COL_WERT]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return ([], [{
            "row": 0,
            "field": "header",
            "message": f"Missing required column(s): {', '.join(missing)}",
        }])

    valid_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()

    for idx, raw_row in df.iterrows():
        row_num = int(idx) + 2  # 1-indexed + header offset
        row = {k: ("" if v is None else str(v)).strip() for k, v in raw_row.to_dict().items()}

        vorgang_nr = row.get(COL_VORGANG_NR, "")
        datum_raw = row.get(COL_DATUM, "")
        wert_raw = row.get(COL_WERT, "")

        # Skip fully blank trailing lines (the export tends to pad).
        if not any(v for v in (vorgang_nr, datum_raw, wert_raw)):
            continue

        if not vorgang_nr:
            errors.append({
                "row": row_num,
                "field": COL_VORGANG_NR,
                "message": "missing Vorgang Nr.",
            })
            continue

        # Last-wins on duplicate Vorgang Nr. — matches the DB upsert.
        if vorgang_nr in seen:
            valid_rows = [r for r in valid_rows if r["vorgang_nr"] != vorgang_nr]
        seen.add(vorgang_nr)

        d = _parse_german_date(datum_raw)
        if d is None:
            errors.append({
                "row": row_num,
                "field": COL_DATUM,
                "message": f"unparseable or empty Datum '{datum_raw}'",
            })
            continue

        wert = _parse_german_decimal(wert_raw)
        if wert is None:
            errors.append({
                "row": row_num,
                "field": COL_WERT,
                "message": f"unparseable or empty Wert '{wert_raw}'",
            })
            continue

        valid_rows.append({
            "vorgang_nr": vorgang_nr,
            "datum": d,
            "erfasser": (row.get(COL_ERFASSER) or None),
            "wert_eur": wert,
            "adr_nr": (row.get(COL_ADR_NR) or None),
            "name": (row.get(COL_NAME) or None),
            "ort": (row.get(COL_ORT) or None),
            "raw": {k: v for k, v in row.items() if v},
        })

    return valid_rows, errors
