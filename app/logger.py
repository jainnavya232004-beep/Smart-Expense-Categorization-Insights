import logging
import os
from logging.handlers import RotatingFileHandler

from app.config import BASE_DIR

LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate handlers when app is reloaded.
    if any(getattr(h, "_smart_expense_handler", False) for h in root.handlers):
        return

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3)
    file_handler.setFormatter(fmt)
    file_handler._smart_expense_handler = True

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    stream_handler._smart_expense_handler = True

    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
