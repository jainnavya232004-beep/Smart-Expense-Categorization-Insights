from app.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.db import get_connection


def _clamp_limit(limit):
    if limit is None:
        return DEFAULT_PAGE_SIZE
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return max(1, min(n, MAX_PAGE_SIZE))


def _clamp_page(page):
    try:
        p = int(page) if page is not None else 1
    except (TypeError, ValueError):
        p = 1
    return max(1, p)


def list_transactions(
    page=None,
    limit=None,
    batch_id=None,
    category=None,
    txn_type=None,
    start_date=None,
    end_date=None,
):
    """Returns (items, total_count, page, limit_used). Defaults to latest batch when batch_id is omitted."""
    effective_batch = batch_id if batch_id is not None else latest_batch_id()
    if effective_batch is None:
        lim = _clamp_limit(limit)
        pg = _clamp_page(page)
        return [], 0, pg, lim

    where = ["1=1"]
    params: list = []
    if effective_batch is not None:
        where.append("t.batch_id = ?")
        params.append(int(effective_batch))
    if category:
        where.append("c.name = ?")
        params.append(category)
    if txn_type in ("credit", "debit"):
        where.append("t.type = ?")
        params.append(txn_type)
    if start_date:
        where.append("t.date >= ?")
        params.append(start_date)
    if end_date:
        where.append("t.date <= ?")
        params.append(end_date)

    wh = " AND ".join(where)
    count_sql = f"""
        SELECT COUNT(*) AS n
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE {wh}
    """
    lim = _clamp_limit(limit)
    pg = _clamp_page(page)
    offset = (pg - 1) * lim

    data_sql = f"""
        SELECT t.id, t.date, t.description_raw AS description, t.amount, t.type, c.name AS category
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE {wh}
        ORDER BY t.date ASC, t.id ASC
        LIMIT ? OFFSET ?
    """

    with get_connection() as conn:
        total = conn.execute(count_sql, params).fetchone()["n"]
        rows = conn.execute(data_sql, params + [lim, offset]).fetchall()

    items = [
        {
            "id": r["id"],
            "date": r["date"],
            "description": r["description"],
            "amount": float(r["amount"]),
            "type": r["type"],
            "category": r["category"],
        }
        for r in rows
    ]
    return items, int(total), pg, lim


def latest_batch_id() -> int | None:
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(id) AS m FROM upload_batches").fetchone()
    m = row["m"]
    return int(m) if m is not None else None


def export_rows(
    batch_id: int | None = None,
    txn_type: str | None = None,
    category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    where = ["1=1"]
    params: list = []
    if batch_id is not None:
        where.append("t.batch_id = ?")
        params.append(int(batch_id))
    if txn_type in ("credit", "debit"):
        where.append("t.type = ?")
        params.append(txn_type)
    if category:
        where.append("c.name = ?")
        params.append(category)
    if start_date:
        where.append("t.date >= ?")
        params.append(start_date)
    if end_date:
        where.append("t.date <= ?")
        params.append(end_date)
    where_clause = " AND ".join(where)
    sql = f"""
        SELECT t.date, t.description_raw AS description, t.amount, t.type, c.name AS category
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE {where_clause}
        ORDER BY t.date ASC, t.id ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
