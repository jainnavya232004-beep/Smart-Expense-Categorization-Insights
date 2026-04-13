from app.db import get_connection


def load_rules():
    """Rules ordered by priority descending so the first substring match is the most specific."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT keyword, category_id
            FROM rules
            ORDER BY priority DESC, LENGTH(keyword) DESC, keyword ASC
            """
        ).fetchall()
    return [(r["keyword"], r["category_id"]) for r in rows]


def get_other_category_id():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM categories WHERE name = ?",
            ("Other",),
        ).fetchone()
    if not row:
        raise RuntimeError("Category 'Other' missing from database seed")
    return row["id"]


def categorize(description_clean: str, rules, other_id: int) -> int:
    if not description_clean:
        return other_id
    for keyword, category_id in rules:
        if keyword.upper() in description_clean:
            return category_id
    return other_id
