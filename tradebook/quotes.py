import json

from tradebook import config
from tradebook.money import USDollar


class UnknownSymbol(LookupError):
    pass


_cache = {}


def _reject_float(text):
    raise ValueError(f"Quote fixture values must be integers: {text}")


def _load():
    key = str(config.QUOTES_PATH)
    if key not in _cache:
        with open(config.QUOTES_PATH, encoding="utf-8") as handle:
            data = json.load(handle, parse_float=_reject_float)
        table = {}
        for item in data["instruments"]:
            price = item["price"]
            if type(price) is not int or price <= 0:
                raise ValueError(f"Invalid quote for {item['symbol']}")
            table[item["symbol"]] = (item["name"], price)
        _cache[key] = table
    return _cache[key]


def instruments():
    return [(symbol, name) for symbol, (name, _) in sorted(_load().items())]


def current(symbol):
    table = _load()
    if symbol not in table:
        raise UnknownSymbol(f"Unknown symbol: {symbol}")
    return USDollar(table[symbol][1])
