from app.db import get_connection
from datetime import date


def _batch_clause(batch_id):
    if batch_id is None:
        return "", ()
    return " AND t.batch_id = ?", (batch_id,)


def summary(batch_id: int | None = None) -> dict:
    if batch_id is None:
        return {"total_income": 0.0, "total_expense": 0.0, "net_balance": 0.0}
    where_extra, params = _batch_clause(batch_id)
    sql_income = f"""
        SELECT COALESCE(SUM(t.amount), 0) AS s
        FROM transactions t
        WHERE t.type = 'credit' {where_extra}
    """
    sql_expense = f"""
        SELECT COALESCE(SUM(ABS(t.amount)), 0) AS s
        FROM transactions t
        WHERE t.type = 'debit' {where_extra}
    """
    with get_connection() as conn:
        income = conn.execute(sql_income, params).fetchone()["s"]
        expense = conn.execute(sql_expense, params).fetchone()["s"]
    net = float(income) - float(expense)
    return {
        "total_income": float(income),
        "total_expense": float(expense),
        "net_balance": net,
    }


def category_summary(batch_id: int | None = None, txn_type: str | None = None) -> list[dict]:
    if batch_id is None:
        return []
    where = []
    params: list = []
    if batch_id is not None:
        where.append("t.batch_id = ?")
        params.append(batch_id)
    if txn_type in ("credit", "debit"):
        where.append("t.type = ?")
        params.append(txn_type)

    wh = " AND ".join(where) if where else "1=1"
    sql = f"""
        SELECT c.name AS category,
               SUM(CASE WHEN t.type = 'debit' THEN ABS(t.amount) ELSE t.amount END) AS amount
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE {wh}
        GROUP BY c.name
        ORDER BY amount DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{"category": r["category"], "amount": float(r["amount"])} for r in rows]


def top_spending_category(batch_id: int | None = None) -> dict | None:
    if batch_id is None:
        return None
    cats = category_summary(batch_id=batch_id, txn_type="debit")
    if not cats:
        return None
    top = max(cats, key=lambda x: x["amount"])
    return {"category": top["category"], "amount": top["amount"]}


def monthly_trend(batch_id: int | None = None, year: int | None = None) -> list[dict]:
    if batch_id is None:
        return []
    where = ["t.type = 'debit'"]
    params: list = []
    if batch_id is not None:
        where.append("t.batch_id = ?")
        params.append(batch_id)
    if year is not None:
        where.append("strftime('%Y', t.date) = ?")
        params.append(str(year))
    wh = " AND ".join(where)
    sql = f"""
        SELECT strftime('%Y-%m', t.date) AS month,
               SUM(ABS(t.amount)) AS amount
        FROM transactions t
        WHERE {wh}
        GROUP BY month
        ORDER BY month ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{"month": r["month"], "amount": float(r["amount"])} for r in rows]


def weekly_trend(batch_id: int | None, week_start: date, week_end: date) -> list[dict]:
    if batch_id is None:
        return []
    sql = """
        SELECT t.date AS day, SUM(ABS(t.amount)) AS amount
        FROM transactions t
        WHERE t.batch_id = ?
          AND t.type = 'debit'
          AND t.date >= ?
          AND t.date <= ?
        GROUP BY t.date
        ORDER BY t.date ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (batch_id, week_start.isoformat(), week_end.isoformat())).fetchall()
    return [{"day": r["day"], "amount": float(r["amount"])} for r in rows]
