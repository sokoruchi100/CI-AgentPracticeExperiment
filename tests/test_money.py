import pytest

from tradebook import money
from tradebook.money import Share, USDollar


@pytest.mark.parametrize(
    "value, expected",
    [(150, 200), (-150, -100), (149, 100), (-151, -200), (0, 0), (250, 300), (12345678, 12345700)],
)
def test_round_units(value, expected):
    assert money.round_units(value) == expected


def test_cost_multiplies_then_divides_then_rounds():
    price = USDollar(333333)
    qty = Share(1500000)
    assert money.cost(price, qty) == USDollar(500000)


def test_average_cost_is_rounded():
    total = USDollar(122000000)
    qty = Share(11000000)
    assert money.average_cost(total, qty) == USDollar(11090900)


def test_parse_and_format_dollars():
    assert money.parse_usd("12.5") == USDollar(12500000)
    assert money.parse_usd("0.0001") == USDollar(100)
    assert money.format_usd(USDollar(12500000)) == "12.5000"
    assert money.format_usd(USDollar(-1500000)) == "-1.5000"


def test_parse_shares():
    assert money.parse_shares("3") == Share(3000000)
    assert money.format_shares(Share(250000)) == "0.2500"


@pytest.mark.parametrize("text", ["1.23456", "-1", "abc", "1e3", ""])
def test_parse_rejects_bad_input(text):
    with pytest.raises(ValueError):
        money.parse_usd(text)


def test_non_integer_amounts_are_rejected():
    with pytest.raises(TypeError):
        USDollar(1.5)
    with pytest.raises(ValueError):
        Share(-1)
