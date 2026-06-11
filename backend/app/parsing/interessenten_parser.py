"""Interessenten (prospect master-data) parser.

Reads the ``dev_excel_INT.txt`` ERP export — 88 columns, tab-separated,
Latin-1 encoded. The file has TWO header lines:

  Line 1: title row ("Adressen\tInteressenten\t…")
  Line 2: the real column headers (Adress-Nr., Anrede Brief, …, Datum Save)
  Line 3+: data rows

Only three columns are persisted: ``Adress-Nr.`` (col A), ``Name 1``
(col D), ``Datum Save`` (col CG). Other columns are kept in ``raw`` as
a dict for traceability, since the file is a moving master-data
snapshot and we may want to widen the schema later without re-uploading.

Returns ``(valid_rows, errors)``. Caller fills in ``upload_batch_id``
and ``imported_at`` before insert.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

import pandas as pd


# Excel column → 0-indexed offset.
# Adress-Nr. = A = 0
# Name 1     = D = 3
# Datum Save = CG = 84
_COL_ADRESS_NR = "Adress-Nr."
_COL_NAME_1 = "Name 1"
_COL_DATUM_SAVE = "Datum Save"


def _parse_german_date(raw: str) -> date | None:
    s = raw.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        return None


def parse_interessenten_file(
    contents: bytes, filename: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse the Adressen/Interessenten dump.

    Returns rows ready for insert into ``interessenten`` (``upload_batch_id``
    and ``imported_at`` to be set by the caller).
    """
    # Line 1 is a "Adressen | Interessenten" title row — skip it. The
    # real header lives on line 2 (header=1 in 0-indexed pandas).
    for encoding in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(
                io.BytesIO(contents),
                sep="\t",
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
                header=1,
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

    # Strip whitespace from header names so ``Adress-Nr.`` etc. match.
    df.columns = [c.strip() for c in df.columns]

    required = [_COL_ADRESS_NR, _COL_NAME_1, _COL_DATUM_SAVE]
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
        # +3 = +1 for the title row we skipped + +1 for the header + +1
        # for 1-indexed humans.
        row_num = int(idx) + 3
        row = {k: ("" if v is None else str(v)).strip() for k, v in raw_row.to_dict().items()}

        adress_nr = row.get(_COL_ADRESS_NR, "")
        name = row.get(_COL_NAME_1, "")
        datum_save_raw = row.get(_COL_DATUM_SAVE, "")

        # Skip fully blank trailing lines (the export pads with empties).
        if not any(v for v in (adress_nr, name, datum_save_raw)):
            continue

        if not adress_nr:
            errors.append({
                "row": row_num,
                "field": _COL_ADRESS_NR,
                "message": "missing Adress-Nr.",
            })
            continue

        # The ERP dump occasionally contains the same Adress-Nr. on two
        # rows (e.g. after an in-flight edit). Last-wins on the parsed
        # side matches PostgreSQL ON CONFLICT DO UPDATE on insert.
        if adress_nr in seen:
            # Drop the earlier row from valid_rows.
            valid_rows = [r for r in valid_rows if r["adress_nr"] != adress_nr]
        seen.add(adress_nr)

        d = _parse_german_date(datum_save_raw)
        if d is None:
            errors.append({
                "row": row_num,
                "field": _COL_DATUM_SAVE,
                "message": f"unparseable or empty Datum Save '{datum_save_raw}'",
            })
            continue

        valid_rows.append({
            "adress_nr": adress_nr,
            "name": name or None,
            "datum_save": d,
            "raw": {k: v for k, v in row.items() if v},
        })

    return valid_rows, errors
