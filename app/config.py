import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
CHARTS_DIR = os.path.join(STATIC_DIR, "charts")
DB_PATH = os.path.join(BASE_DIR, "instance", "expense.db")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
