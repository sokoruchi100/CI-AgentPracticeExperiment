import json
import shutil

import pytest

from tradebook import config, money

SEEDED_DB = config.DB_PATH
BASE_QUOTES = config.QUOTES_PATH


class Clock:
    def __init__(self):
        self.value = "2026-04-01T15:00:00.000000Z"

    def __call__(self):
        return self.value

    def set(self, value):
        self.value = value


class Market:
    def __init__(self, folder, monkeypatch):
        self.folder = folder
        self.monkeypatch = monkeypatch
        self.data = json.loads(BASE_QUOTES.read_text(encoding="utf-8"))
        self.version = 0

    def set(self, symbol, dollars):
        for item in self.data["instruments"]:
            if item["symbol"] == symbol:
                item["price"] = money.parse_usd(dollars).unit
        self.version += 1
        path = self.folder / f"quotes_{self.version}.json"
        path.write_text(json.dumps(self.data), encoding="utf-8")
        self.monkeypatch.setattr(config, "QUOTES_PATH", path)


@pytest.fixture(autouse=True)
def clock(tmp_path, monkeypatch):
    target = tmp_path / "tradebook.db"
    shutil.copyfile(SEEDED_DB, target)
    monkeypatch.setattr(config, "DB_PATH", target)
    monkeypatch.setattr(config, "QUOTES_PATH", BASE_QUOTES)
    fixed = Clock()
    monkeypatch.setattr(config, "now", fixed)
    return fixed


@pytest.fixture
def market(tmp_path, monkeypatch):
    return Market(tmp_path, monkeypatch)
