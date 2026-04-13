import io
from datetime import datetime

import pandas as pd

from app.db import get_connection
from app.services.categorizer import categorize, get_other_category_id, load_rules
from app.services.text import clean_description, normalize_type

REQUIRED = {"date", "description", "amount", "type"}
DEFAULT_DATE = "1970-01-01"
DEFAULT_DESCRIPTION = "UNKNOWN TRANSACTION"
DEFAULT_AMOUNT = 0.0


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    colmap = {c.lower().strip(): c for c in df.columns}
    rename = {}
    for need in REQUIRED:
        if need in colmap:
            rename[colmap[need]] = need
    out = df.rename(columns=rename)
    # Ensure required columns always exist; missing columns are auto-created.
    for need in REQUIRED:
        if need not in out.columns:
            out[need] = pd.NA
    return out[list(REQUIRED)]


def parse_csv_bytes(raw: bytes) -> pd.DataFrame:
    if not raw:
        raise ValueError("Empty file")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise ValueError(f"Invalid CSV: {e}") from e
    return _normalize_columns(df)


def parse_csv_path(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return _normalize_columns(df)


def _parse_date(val):
    if pd.isna(val):
        raise ValueError("Empty date")
    if isinstance(val, datetime):
        return val.date().isoformat()
    s = str(val).strip()
    try:
        return datetime.fromisoformat(s[:10]).date().isoformat()
    except ValueError as e:
        raise ValueError(f"Bad date: {val!r}") from e


def _parse_amount(val):
    if pd.isna(val):
        raise ValueError("Empty amount")
    try:
        return float(val)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Bad amount: {val!r}") from e


def _safe_date(val):
    try:
        return _parse_date(val), None
    except Exception:
        return DEFAULT_DATE, "date"


def _safe_amount(val):
    try:
        return _parse_amount(val), None
    except Exception:
        return DEFAULT_AMOUNT, "amount"


def _safe_type(val, amount: float):
    try:
        return normalize_type(val), None
    except Exception:
        # Safe inference rule: negative amounts are debits, non-negative are credits.
        inferred = "debit" if float(amount) < 0 else "credit"
        return inferred, "type"


def build_transaction_rows(df: pd.DataFrame, rules, other_id: int):
    rows = []
    auto_filled = []
    for df_index, row in df.iterrows():
        line_num = int(df_index) + 2
        changed = []

        d, date_fix = _safe_date(row["date"])
        if date_fix:
            changed.append(date_fix)

        amt, amount_fix = _safe_amount(row["amount"])
        if amount_fix:
            changed.append(amount_fix)

        typ, type_fix = _safe_type(row["type"], amt)
        if type_fix:
            changed.append(type_fix)

        raw_desc = row["description"]
        if pd.isna(raw_desc):
            desc_raw = DEFAULT_DESCRIPTION
            changed.append("description")
        else:
            desc_raw = str(raw_desc).strip() or DEFAULT_DESCRIPTION
            if desc_raw == DEFAULT_DESCRIPTION:
                changed.append("description")

        desc_clean = clean_description(desc_raw)
        cat_id = categorize(desc_clean, rules, other_id)
        rows.append((d, desc_raw, desc_clean, amt, typ, cat_id))

        if changed:
            auto_filled.append(
                {
                    "row": line_num,
                    "filled_fields": sorted(set(changed)),
                    "note": "Auto-filled invalid/missing values with safe defaults",
                }
            )
    return rows, auto_filled


def bulk_insert_transactions(batch_id: int, rows: list[tuple]) -> int:
    if not rows:
        return 0
    sql = """
    INSERT INTO transactions
    (batch_id, date, description_raw, description_clean, amount, type, category_id)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        conn.executemany(sql, [(batch_id, *r) for r in rows])
        conn.commit()
    return len(rows)


def process_upload(file_bytes: bytes, filename: str) -> dict:
    df = parse_csv_bytes(file_bytes)
    if df.empty:
        raise ValueError("CSV has no data rows")

    rules = load_rules()
    other_id = get_other_category_id()
    rows, auto_filled = build_transaction_rows(df, rules, other_id)

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO upload_batches (filename, row_count) VALUES (?, ?)",
            (filename or "upload.csv", len(rows)),
        )
        batch_id = cur.lastrowid
        conn.commit()

    inserted = bulk_insert_transactions(batch_id, rows)

    return {
        "batch_id": batch_id,
        "inserted": inserted,
        "skipped_errors": [],
        "auto_filled_rows": auto_filled,
    }
