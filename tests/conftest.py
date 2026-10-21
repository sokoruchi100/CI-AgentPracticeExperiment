import shutil

import pytest

from tradebook import config, db, quotes

config.require_test_env()
db.require_initialized()


class Clock:
    def __init__(self):
        self.value = "2026-03-02T15:00:00.000000Z"

    def __call__(self):
        return self.value

    def set(self, value):
        self.value = value


@pytest.fixture(autouse=True)
def clock(tmp_path, monkeypatch):
    target = tmp_path / "tradebook.db"
    shutil.copyfile(config.DB_PATH, target)
    monkeypatch.setattr(config, "DB_PATH", target)
    fixed = Clock()
    monkeypatch.setattr(config, "now", fixed)
    return fixed


@pytest.fixture
def prices(monkeypatch):
    table = {}
    original = quotes.current

    def current(symbol):
        if symbol in table:
            return table[symbol]
        return original(symbol)

    monkeypatch.setattr(quotes, "current", current)
    return table
