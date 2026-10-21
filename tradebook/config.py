import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "tradebook.db"
QUOTES_PATH = ROOT / "fixtures" / "quotes.json"
LOCK_TIMEOUT_MS = 1000


def require_test_env():
    if os.environ.get("EXPSET") != "True":
        raise RuntimeError("Configuration not ready for testing")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
