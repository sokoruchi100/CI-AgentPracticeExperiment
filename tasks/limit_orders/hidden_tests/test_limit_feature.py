import pytest

from tradebook import cli, lots, transitions
from tradebook.money import Share, parse_shares as sh, parse_usd as usd
from tradebook.services import accounts, orders


def test_marketable_buy_fills_at_quote_not_limit():
    before = accounts.cash("A00001")
    order = orders.place_limit("A00001", "buy", "ACME", sh("4"), usd("13"))
    assert order.status == transitions.FILLED
    assert order.limit_price == usd("13").unit
    assert orders.trade("A00001", order.id).price == usd("12.5").unit
    assert accounts.cash("A00001") == before - usd("50")
    assert lots.held("A00001", "ACME") == sh("4")


def test_buy_limit_equal_to_quote_fills():
    order = orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("12.5"))
    assert order.status == transitions.FILLED


def test_non_marketable_buy_rests_without_side_effects():
    before = accounts.cash("A00001")
    order = orders.place_limit("A00001", "buy", "ACME", sh("4"), usd("12"))
    assert order.status == transitions.NEW
    assert orders.trade("A00001", order.id) is None
    assert accounts.cash("A00001") == before
    assert lots.held("A00001", "ACME") == Share(0)
    stored = orders.get("A00001", order.id)
    assert stored.status == transitions.NEW
    assert stored.limit_price == usd("12").unit


def test_sell_limits_fill_or_rest():
    orders.place_market("A00001", "buy", "ACME", sh("10"))
    filled = orders.place_limit("A00001", "sell", "ACME", sh("4"), usd("12"))
    assert filled.status == transitions.FILLED
    assert orders.trade("A00001", filled.id).price == usd("12.5").unit
    resting = orders.place_limit("A00001", "sell", "ACME", sh("2"), usd("13"))
    assert resting.status == transitions.NEW
    assert lots.held("A00001", "ACME") == sh("6")


def test_sell_limit_equal_to_quote_fills():
    orders.place_market("A00001", "buy", "ACME", sh("1"))
    order = orders.place_limit("A00001", "sell", "ACME", sh("1"), usd("12.5"))
    assert order.status == transitions.FILLED


def test_sweep_fills_when_quote_moves(market):
    order = orders.place_limit("A00001", "buy", "ACME", sh("4"), usd("12"))
    assert orders.sweep("A00001") == []
    before = accounts.cash("A00001")
    market.set("ACME", "11.9")
    changed = orders.sweep("A00001")
    assert [o.id for o in changed] == [order.id]
    assert changed[0].status == transitions.FILLED
    assert orders.get("A00001", order.id).status == transitions.FILLED
    assert orders.trade("A00001", order.id).price == usd("11.9").unit
    assert accounts.cash("A00001") == before - usd("47.6")
    assert orders.sweep("A00001") == []


def test_sweep_runs_in_order_id_and_leaves_unmarketable_open(market):
    first = orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("12"))
    low = orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("11"))
    third = orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("11.8"))
    market.set("ACME", "11.8")
    changed = orders.sweep("A00001")
    assert [o.id for o in changed] == [first.id, third.id]
    assert all(o.status == transitions.FILLED for o in changed)
    assert orders.get("A00001", low.id).status == transitions.NEW


def test_sweep_rejects_buy_when_cash_is_short(market):
    first = orders.place_limit("A00003", "buy", "DYNA", sh("20"), usd("200"))
    second = orders.place_limit("A00003", "buy", "DYNA", sh("20"), usd("200"))
    assert first.status == second.status == transitions.NEW
    market.set("DYNA", "190")
    changed = orders.sweep("A00003")
    assert [(o.id, o.status) for o in changed] == [
        (first.id, transitions.FILLED),
        (second.id, transitions.REJECTED),
    ]
    assert accounts.cash("A00003") == usd("1200.5")


def test_sweep_rejects_sell_larger_than_holdings(market):
    orders.place_market("A00001", "buy", "ACME", sh("5"))
    resting = orders.place_limit("A00001", "sell", "ACME", sh("5"), usd("15"))
    orders.place_market("A00001", "sell", "ACME", sh("5"))
    market.set("ACME", "16")
    changed = orders.sweep("A00001")
    assert [(o.id, o.status) for o in changed] == [(resting.id, transitions.REJECTED)]


def test_sweep_only_touches_the_given_account(market):
    other = orders.place_limit("A00002", "buy", "ACME", sh("1"), usd("12"))
    market.set("ACME", "11")
    assert orders.sweep("A00001") == []
    assert orders.get("A00002", other.id).status == transitions.NEW
    assert [o.id for o in orders.sweep("A00002")] == [other.id]


def test_marketable_limit_buy_rejected_on_insufficient_cash():
    order = orders.place_limit("A00003", "buy", "DYNA", sh("100"), usd("300"))
    assert order.status == transitions.REJECTED
    assert orders.trade("A00003", order.id) is None


def test_market_orders_have_no_limit_price():
    order = orders.place_market("A00001", "buy", "ACME", sh("2"))
    assert order.status == transitions.FILLED
    assert order.limit_price is None
    assert orders.get("A00001", order.id).limit_price is None


def test_invalid_limit_orders_raise():
    with pytest.raises(ValueError):
        orders.place_limit("A00001", "buy", "ACME", Share(0), usd("12"))
    with pytest.raises(ValueError):
        orders.place_limit("A00001", "hold", "ACME", sh("1"), usd("12"))
    with pytest.raises(LookupError):
        orders.place_limit("A00001", "buy", "ZZZZ", sh("1"), usd("12"))
    with pytest.raises(LookupError):
        orders.place_limit("A99999", "buy", "ACME", sh("1"), usd("12"))


def cli_lines(capsys, *argv):
    code = cli.main(list(argv))
    out, _ = capsys.readouterr()
    return code, out.strip().splitlines()


def test_cli_limit_place_show_and_sweep(capsys, market):
    code, out = cli_lines(capsys, "order", "place", "A00001", "buy", "ACME", "4", "--limit", "12")
    assert code == 0
    order_id = out[0].split()[1]
    assert out == [f"order {order_id} NEW buy ACME 4.0000 limit 12.0000"]
    assert cli_lines(capsys, "order", "show", "A00001", order_id)[1] == out
    market.set("ACME", "11.5")
    code, out = cli_lines(capsys, "order", "sweep", "A00001")
    assert code == 0
    assert out == [f"order {order_id} FILLED buy ACME 4.0000 @ 11.5000 limit 12.0000"]
    assert cli_lines(capsys, "order", "sweep", "A00001") == (0, [])


def test_cli_market_order_line_unchanged(capsys):
    code, out = cli_lines(capsys, "order", "place", "A00001", "buy", "ACME", "1")
    assert code == 0
    order_id = out[0].split()[1]
    assert out == [f"order {order_id} FILLED buy ACME 1.0000 @ 12.5000"]
