"""ERP tab-delimited file parser with German locale handling.

Reads tab-delimited ERP export files that use:
- ="..." quoting on string fields
- German number format (. as thousands sep, , as decimal)
- DD.MM.YYYY dates
- Windows line endings (CRLF)

Returns (valid_rows, errors) where:
- valid_rows: list of dicts ready for DB insert (upload_batch_id set to None by default)
- errors: list of dicts with row, column, message keys
"""

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.parsing.column_mapping import (
    DATE_COLUMNS,
    DECIMAL_COLUMNS,
    GERMAN_TO_ENGLISH,
    INTEGER_COLUMNS,
    REQUIRED_COLUMNS,
)

EXPECTED_COLUMN_COUNT = 38


def strip_eq_quotes(value: str) -> str:
    """Strip the ="..." quoting wrapper from ERP export cell values.

    If value starts with =" and ends with ", return the inner string.
    Otherwise return the value unchanged.
    """
    if isinstance(value, str) and value.startswith('="') and value.endswith('"'):
        return value[2:-1]
    return value


def parse_german_decimal(raw: str) -> Decimal | None:
    """Parse a German-formatted decimal string to Decimal.

    German format: . as thousands separator, , as decimal separator.
    E.g., "2.230,43" -> Decimal("2230.43")

    Returns None if the string is empty or cannot be parsed.
    """
    stripped = raw.strip()
    if not stripped:
        return None
    # Remove thousands separator (.) then replace decimal comma (,) with period
    normalized = stripped.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_german_date(raw: str) -> date | None:
    """Parse a German DD.MM.YYYY date string to a Python date.

    Returns None if the string is empty or cannot be parsed.
    """
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        return datetime.strptime(stripped, "%d.%m.%Y").date()
    except ValueError:
        return None


def validate_row(row_num: int, row: dict[str, str]) -> list[dict]:
    """Validate a single row dict and return a list of validation errors.

    Per D-12, validates:
    1. Column count is validated at the DataFrame level in parse_erp_file — not per row.
    2. Unparseable date values in DATE_COLUMNS.
    3. Unparseable German decimal values in DECIMAL_COLUMNS.
    4. Missing or empty order_number (REQUIRED_COLUMNS).

    Args:
        row_num: 1-indexed row number (accounting for header: idx + 2)
        row: dict mapping English column names to raw string values

    Returns:
        List of error dicts, each with keys: row, column, message
    """
    errors: list[dict] = []

    # Check 2: Unparseable dates
    for col in DATE_COLUMNS:
        value = row.get(col, "")
        if value and parse_german_date(value) is None:
            errors.append({
                "row": row_num,
                "column": col,
                "message": f"unparseable date '{value}'",
            })

    # Check 3: Unparseable German decimals
    for col in DECIMAL_COLUMNS:
        value = row.get(col, "")
        if value and parse_german_decimal(value) is None:
            errors.append({
                "row": row_num,
                "column": col,
                "message": f"unparseable decimal '{value}'",
            })

    # Check 4: Required columns must be non-empty
    for col in REQUIRED_COLUMNS:
        value = row.get(col, "")
        if not value or not value.strip():
            errors.append({
                "row": row_num,
                "column": col,
                "message": "missing or empty order number",
            })

    return errors


def row_to_dict(row: dict[str, str]) -> dict:
    """Convert a validated row dict to a DB-ready dict with proper Python types.

    - Date columns are converted to Python date objects (or None if empty)
    - Decimal columns are converted to Decimal (or None if empty)
    - All other columns are stripped strings
    - upload_batch_id is set to None (caller sets the actual value)
    """
    result: dict = {"upload_batch_id": None}

    for col, raw in row.items():
        if col in DATE_COLUMNS:
            result[col] = parse_german_date(raw)
        elif col in DECIMAL_COLUMNS:
            result[col] = parse_german_decimal(raw)
        elif col in INTEGER_COLUMNS:
            stripped = raw.strip() if isinstance(raw, str) else raw
            try:
                result[col] = int(stripped) if stripped else None
            except (ValueError, TypeError):
                result[col] = None
        else:
            result[col] = raw.strip() if isinstance(raw, str) else raw

    return result


def parse_erp_file(
    contents: bytes, filename: str
) -> tuple[list[dict], list[dict]]:
    """Parse raw bytes of a tab-delimited ERP export file.

    Steps:
    1. Read with pandas using tab delimiter, all columns as str, no NA inference
    2. Strip ="..." from all cells using df.map (pandas 3.x)
    3. Validate column count matches expected 38
    4. Rename columns from German to English using GERMAN_TO_ENGLISH mapping
    5. Iterate rows: validate each, collect errors, build valid_rows list

    Args:
        contents: Raw file bytes (typically from FastAPI UploadFile.read())
        filename: Original filename (used for error context, not parsing logic)

    Returns:
        Tuple of (valid_rows, errors):
        - valid_rows: List of DB-ready dicts (upload_batch_id=None)
        - errors: List of error dicts with row, column, message keys
    """
    # Step 1: Read tab-delimited, all strings, no NA inference
    # ERP exports use Latin-1 encoding (German umlauts like ü = 0xFC)
    # Try utf-8 first, fall back to latin-1
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
        return ([], [{"row": 0, "column": "", "message": "Unable to decode file (tried utf-8, latin-1)"}])

    # Step 2: Strip ="..." quoting wrapper from all cells (pandas 3.x: use .map)
    df = df.map(strip_eq_quotes)

    # Step 3: Validate column count before renaming
    if len(df.columns) != EXPECTED_COLUMN_COUNT:
        return (
            [],
            [{
                "row": 0,
                "column": "",
                "message": (
                    f"Expected {EXPECTED_COLUMN_COUNT} columns, "
                    f"got {len(df.columns)}"
                ),
            }],
        )

    # Strip ="..." from column headers too (they also use this pattern)
    df.columns = [strip_eq_quotes(col) for col in df.columns]

    # Step 4: Rename columns German -> English
    # Build reverse mapping for any unmapped headers (keep as-is with warning)
    rename_map = {}
    for german_col in df.columns:
        english_col = GERMAN_TO_ENGLISH.get(german_col)
        if english_col is not None:
            rename_map[german_col] = english_col
    df = df.rename(columns=rename_map)

    # Step 5: Iterate rows, validate, collect errors and valid rows
    valid_rows: list[dict] = []
    errors: list[dict] = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed + header offset
        row_dict = row.to_dict()

        row_errors = validate_row(row_num, row_dict)
        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows.append(row_to_dict(row_dict))

    return valid_rows, errors
