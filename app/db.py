import os
import sqlite3
from contextlib import contextmanager

from app.config import BASE_DIR, DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS upload_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    row_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER,
    date TEXT NOT NULL,
    description_raw TEXT NOT NULL,
    description_clean TEXT NOT NULL,
    amount REAL NOT NULL,
    type TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (batch_id) REFERENCES upload_batches(id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_batch ON transactions(batch_id);
"""


def ensure_instance_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def init_db():
    ensure_instance_dir()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
    seed_if_empty()


def _category_map(conn):
    rows = conn.execute("SELECT id, name FROM categories").fetchall()
    return {name: row_id for row_id, name in rows}


def seed_if_empty():
    with sqlite3.connect(DB_PATH) as conn:
        n = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if n > 0:
            return

        categories = [
            "Salary / Income",
            "Rent",
            "Food",
            "Travel",
            "Shopping",
            "Bills & Utilities",
            "Entertainment",
            "Healthcare",
            "Insurance",
            "Savings / Transfers",
            "Investments / Interest",
            "Other",
        ]
        conn.executemany(
            "INSERT INTO categories (name) VALUES (?)",
            [(c,) for c in categories],
        )
        cm = _category_map(conn)

        def cid(name):
            return cm[name]

        # Higher priority = evaluated first (more specific phrases first).
        rule_rows = [
            ("INTEREST CREDIT", cid("Investments / Interest"), 200),
            ("AMAZON PRIME", cid("Entertainment"), 190),
            ("AMAZON INDIA", cid("Shopping"), 185),
            ("AMAZON PAY BILL", cid("Bills & Utilities"), 180),
            ("UBER TRIP", cid("Travel"), 175),
            ("UBER EATS", cid("Food"), 170),
            ("OLA CAB", cid("Travel"), 165),
            ("OLA AUTO", cid("Travel"), 160),
            ("OLA BIKE", cid("Travel"), 155),
            ("SALARY", cid("Salary / Income"), 150),
            ("BONUS", cid("Salary / Income"), 145),
            ("RENT PAYMENT", cid("Rent"), 140),
            ("SWIGGY", cid("Food"), 135),
            ("ZOMATO", cid("Food"), 130),
            ("DOMINOS", cid("Food"), 125),
            ("STARBUCKS", cid("Food"), 120),
            ("GROCERY STORE", cid("Food"), 115),
            ("BIG BAZAAR", cid("Food"), 114),
            ("INSTAMART", cid("Food"), 113),
            ("FLIPKART GROCERY", cid("Food"), 112),
            ("FLIPKART", cid("Shopping"), 110),
            ("ELECTRICITY BILL", cid("Bills & Utilities"), 105),
            ("WATER BILL", cid("Bills & Utilities"), 100),
            ("MOBILE RECHARGE", cid("Bills & Utilities"), 95),
            ("NETFLIX", cid("Entertainment"), 90),
            ("SPOTIFY", cid("Entertainment"), 85),
            ("BOOKMYSHOW", cid("Entertainment"), 80),
            ("APOLLO PHARMACY", cid("Healthcare"), 75),
            ("MEDPLUS", cid("Healthcare"), 70),
            ("HOSPITAL", cid("Healthcare"), 65),
            ("LAB TEST", cid("Healthcare"), 60),
            ("MEDICAL STORE", cid("Healthcare"), 55),
            ("LIC INSURANCE", cid("Insurance"), 50),
            ("TRANSFER TO SAVINGS", cid("Savings / Transfers"), 45),
            ("TRANSFER FROM FRIEND", cid("Savings / Transfers"), 44),
            ("TRANSFER FROM CLIENT", cid("Savings / Transfers"), 43),
            ("TRANSFER TO WALLET", cid("Savings / Transfers"), 42),
        ]
        conn.executemany(
            "INSERT INTO rules (keyword, category_id, priority) VALUES (?, ?, ?)",
            rule_rows,
        )
        conn.commit()


@contextmanager
def get_connection():
    ensure_instance_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=8000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
