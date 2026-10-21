from tradebook import lots, transitions
from tradebook.money import parse_shares, parse_usd
from tradebook.services import orders, portfolio


def buy(clock, prices, when, qty, price):
    clock.set(when)
    prices["ACME"] = parse_usd(price)
    return orders.place_market("A00001", transitions.BUY, "ACME", parse_shares(qty))


def sell(prices, qty, price):
    prices["ACME"] = parse_usd(price)
    return orders.place_market("A00001", transitions.SELL, "ACME", parse_shares(qty))


def remaining():
    return {lot.id: lot.qty_remaining for lot in lots.open_lots("A00001", "ACME")}


def test_largest_lot_then_earliest_then_lowest_id(clock, prices):
    buy(clock, prices, "2026-03-02T15:00:02.000000Z", "5", "10")
    buy(clock, prices, "2026-03-02T15:00:03.000000Z", "8", "12")
    buy(clock, prices, "2026-03-02T15:00:01.000000Z", "8", "11")
    first, second, third = sorted(remaining())
    order = sell(prices, "10", "15")
    assert remaining() == {first: 5000000, second: 6000000}
    assert orders.trade("A00001", order.id).realized == parse_usd("38").unit


def test_ties_on_time_go_to_lowest_id(clock, prices):
    buy(clock, prices, "2026-03-02T15:00:00.000000Z", "3", "10")
    buy(clock, prices, "2026-03-02T15:00:00.000000Z", "3", "20")
    first, second = sorted(remaining())
    order = sell(prices, "2", "20")
    assert remaining() == {first: 1000000, second: 3000000}
    assert orders.trade("A00001", order.id).realized == parse_usd("20").unit


def test_ranking_uses_remaining_quantity_at_match_time(clock, prices):
    buy(clock, prices, "2026-03-02T15:00:01.000000Z", "10", "10")
    buy(clock, prices, "2026-03-02T15:00:02.000000Z", "6", "10")
    first, second = sorted(remaining())
    sell(prices, "5", "10")
    assert remaining() == {first: 5000000, second: 6000000}
    sell(prices, "5", "10")
    assert remaining() == {first: 5000000, second: 1000000}


def test_partly_used_lot_keeps_cost_and_time(clock, prices):
    buy(clock, prices, "2026-03-02T15:00:01.000000Z", "4", "10")
    clock.set("2026-03-02T16:00:00.000000Z")
    sell(prices, "1", "10")
    (lot,) = lots.open_lots("A00001", "ACME")
    assert lot.cost_per_share == parse_usd("10").unit
    assert lot.opened_at == "2026-03-02T15:00:01.000000Z"


def test_portfolio_shows_positions_average_cost_and_realized(clock, prices):
    buy(clock, prices, "2026-03-02T15:00:02.000000Z", "5", "10")
    buy(clock, prices, "2026-03-02T15:00:03.000000Z", "8", "12")
    buy(clock, prices, "2026-03-02T15:00:01.000000Z", "8", "11")
    sell(prices, "10", "15")
    summary = portfolio.show("A00001")
    (position,) = summary.positions
    assert position.symbol == "ACME"
    assert position.qty == parse_shares("11")
    assert position.average_cost.unit == 11090900
    assert summary.realized == parse_usd("38")


def test_empty_portfolio():
    summary = portfolio.show("A00002")
    assert summary.positions == []
    assert summary.realized == parse_usd("0")
    assert summary.cash == parse_usd("25000")
