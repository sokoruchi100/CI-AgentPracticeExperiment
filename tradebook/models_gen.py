# @@GENERATED@@
from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    id: str
    cash: int


@dataclass(frozen=True)
class Counter:
    name: str
    value: int


@dataclass(frozen=True)
class Event:
    id: int
    name: str
    fields: str
    emitted_at: str


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str


@dataclass(frozen=True)
class Lot:
    id: int
    account_id: str
    symbol: str
    qty_remaining: int
    cost_per_share: int
    opened_at: str


@dataclass(frozen=True)
class Order:
    id: int
    account_id: str
    symbol: str
    side: str
    qty: int
    status: int
    created_at: str


@dataclass(frozen=True)
class Trade:
    id: int
    order_id: int
    qty: int
    price: int
    realized: int
    executed_at: str


TABLES = {
    'accounts': ('id', 'cash',),
    'counters': ('name', 'value',),
    'events': ('id', 'name', 'fields', 'emitted_at',),
    'instruments': ('symbol', 'name',),
    'lots': ('id', 'account_id', 'symbol', 'qty_remaining', 'cost_per_share', 'opened_at',),
    'orders': ('id', 'account_id', 'symbol', 'side', 'qty', 'status', 'created_at',),
    'trades': ('id', 'order_id', 'qty', 'price', 'realized', 'executed_at',),
}

MODELS = {
    'accounts': Account,
    'counters': Counter,
    'events': Event,
    'instruments': Instrument,
    'lots': Lot,
    'orders': Order,
    'trades': Trade,
}

DDL = (
    'CREATE TABLE accounts (id TEXT PRIMARY KEY, cash INTEGER NOT NULL)',
    'CREATE TABLE counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL)',
    'CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, fields TEXT NOT NULL, emitted_at TEXT NOT NULL)',
    'CREATE TABLE instruments (symbol TEXT PRIMARY KEY, name TEXT NOT NULL)',
    'CREATE TABLE lots (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, symbol TEXT NOT NULL, qty_remaining INTEGER NOT NULL, cost_per_share INTEGER NOT NULL, opened_at TEXT NOT NULL)',
    'CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, qty INTEGER NOT NULL, status INTEGER NOT NULL, created_at TEXT NOT NULL)',
    'CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, qty INTEGER NOT NULL, price INTEGER NOT NULL, realized INTEGER NOT NULL, executed_at TEXT NOT NULL)',
)
