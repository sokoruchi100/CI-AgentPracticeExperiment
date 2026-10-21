import re
from dataclasses import dataclass

UNITS_PER_USD = 1000000
SHUNITS_PER_SHARE = 1000000
DECIMAL_PLACES = 4

_DECIMAL = re.compile(r"([0-9]+)(?:\.([0-9]{1,4}))?")


def _require_int(value):
    if type(value) is not int:
        raise TypeError("Amounts must be integers")


def round_units(value):
    _require_int(value)
    return (value + 50) // 100 * 100


@dataclass(frozen=True, order=True)
class USDollar:
    unit: int

    def __post_init__(self):
        _require_int(self.unit)

    def __add__(self, other):
        return USDollar(self.unit + other.unit)

    def __sub__(self, other):
        return USDollar(self.unit - other.unit)


@dataclass(frozen=True, order=True)
class Share:
    shunit: int

    def __post_init__(self):
        _require_int(self.shunit)
        if self.shunit < 0:
            raise ValueError("Quantity cannot be negative")

    def __add__(self, other):
        return Share(self.shunit + other.shunit)

    def __sub__(self, other):
        return Share(self.shunit - other.shunit)


def cost(price, qty):
    return USDollar(round_units(price.unit * qty.shunit // SHUNITS_PER_SHARE))


def average_cost(total, qty):
    if qty.shunit == 0:
        return USDollar(0)
    return USDollar(round_units(total.unit * SHUNITS_PER_SHARE // qty.shunit))


def _parse(text, scale):
    match = _DECIMAL.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"Invalid amount: {text}")
    whole, fraction = match.group(1), match.group(2) or ""
    fraction_value = int(fraction.ljust(DECIMAL_PLACES, "0")) * (scale // 10**DECIMAL_PLACES)
    return round_units(int(whole) * scale + fraction_value)


def _format(value, scale):
    rounded = round_units(value)
    sign = "-" if rounded < 0 else ""
    whole, rest = divmod(abs(rounded), scale)
    fraction = rest // (scale // 10**DECIMAL_PLACES)
    return f"{sign}{whole}.{fraction:0{DECIMAL_PLACES}d}"


def parse_usd(text):
    return USDollar(_parse(text, UNITS_PER_USD))


def format_usd(amount):
    return _format(amount.unit, UNITS_PER_USD)


def parse_shares(text):
    return Share(_parse(text, SHUNITS_PER_SHARE))


def format_shares(qty):
    return _format(qty.shunit, SHUNITS_PER_SHARE)
