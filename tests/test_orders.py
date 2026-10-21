import json

import pytest

from tradebook import events, lots, quotes, transitions
from tradebook.money import Share, USDollar, parse_shares, parse_usd
from tradebook.services import accounts, orders


def test_buy_fills_debits_cash_and_opens_lot():
    before = accounts.cash("A00001")
    order = orders.place_market("A00001", transitions.BUY, "ACME", parse_shares("10"))
    assert order.status == transitions.FILLED
    assert accounts.cash("A00001") == before - parse_usd("125")
    assert lots.held("A00001", "ACME") == parse_shares("10")
    filled = orders.trade("A00001", order.id)
    assert filled.price == quotes.current("ACME").unit
    assert filled.qty == order.qty


def test_buy_emits_fill_event():
    order = orders.place_market("A00002", transitions.BUY, "BOLT", parse_shares("2"))
    event = events.for_account("A00002")[-1]
    assert event.name[10] == "B"
    assert json.loads(event.fields) == {
        "account_id": "A00002",
        "order_id": order.id,
        "symbol": "BOLT",
        "qty": 2000000,
        "price": 48250000,
    }


def test_buy_with_insufficient_cash_is_rejected():
    before = accounts.cash("A00003")
    order = orders.place_market("A00003", transitions.BUY, "DYNA", parse_shares("100"))
    assert order.status == transitions.REJECTED
    assert orders.get("A00003", order.id).status == transitions.REJECTED
    assert accounts.cash("A00003") == before
    assert orders.trade("A00003", order.id) is None
    assert events.for_account("A00003")[-1].name[10] == "R"


def test_sell_more_than_held_is_rejected():
    orders.place_market("A00001", transitions.BUY, "CRUX", parse_shares("1"))
    order = orders.place_market("A00001", transitions.SELL, "CRUX", parse_shares("2"))
    assert order.status == transitions.REJECTED
    assert lots.held("A00001", "CRUX") == parse_shares("1")


def test_sell_credits_proceeds_and_records_realized(prices):
    orders.place_market("A00001", transitions.BUY, "ACME", parse_shares("4"))
    prices["ACME"] = parse_usd("15")
    before = accounts.cash("A00001")
    order = orders.place_market("A00001", transitions.SELL, "ACME", parse_shares("3"))
    assert order.status == transitions.FILLED
    assert accounts.cash("A00001") == before + parse_usd("45")
    assert orders.trade("A00001", order.id).realized == parse_usd("7.5").unit
    assert events.for_account("A00001")[-1].name[10] == "S"


def test_invalid_order_input():
    with pytest.raises(ValueError):
        orders.place_market("A00001", "hold", "ACME", parse_shares("1"))
    with pytest.raises(ValueError):
        orders.place_market("A00001", transitions.BUY, "ACME", Share(0))
    with pytest.raises(quotes.UnknownSymbol):
        orders.place_market("A00001", transitions.BUY, "ZZZZ", parse_shares("1"))
    with pytest.raises(accounts.AccountNotFound):
        orders.place_market("A99999", transitions.BUY, "ACME", parse_shares("1"))


def test_filled_order_cannot_transition_again():
    order = orders.place_market("A00001", transitions.BUY, "ACME", parse_shares("1"))
    with pytest.raises(transitions.InvalidTransition, match="Transition not allowed"):
        transitions.apply(order, transitions.REJECTED, price=USDollar(1))


def test_rejected_order_cannot_fill():
    order = orders.place_market("A00003", transitions.BUY, "DYNA", parse_shares("100"))
    with pytest.raises(transitions.InvalidTransition, match="Transition not allowed"):
        transitions.apply(order, transitions.FILLED, price=USDollar(1))


def test_transition_table():
    assert transitions.ALLOWED[transitions.NEW] == {transitions.FILLED, transitions.REJECTED}
    assert not transitions.ALLOWED[transitions.FILLED]
    assert not transitions.ALLOWED[transitions.REJECTED]
