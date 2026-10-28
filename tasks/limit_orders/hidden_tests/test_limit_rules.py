import dataclasses
import json
import threading

import pytest

from tradebook import cli, config, events, ids, lots, transitions
from tradebook.locking import LockTimeout, hold
from tradebook.money import parse_shares as sh, parse_usd as usd
from tradebook.services import orders, portfolio


def recorded(account_id):
    return [(event.name, json.loads(event.fields)) for event in events.for_account(account_id)]


def letter(name):
    return name.split("-")[2][0]


def test_resting_order_emits_no_event():
    before = recorded("A00001")
    orders.place_limit("A00001", "buy", "ACME", sh("4"), usd("12"))
    assert recorded("A00001") == before


def test_sweep_fill_emits_one_valid_buy_event(market):
    order = orders.place_limit("A00001", "buy", "ACME", sh("4"), usd("12"))
    before = len(recorded("A00001"))
    market.set("ACME", "11.9")
    orders.sweep("A00001")
    new = recorded("A00001")[before:]
    assert len(new) == 1
    name, fields = new[0]
    assert ids.validate(name) and letter(name) == "B"
    assert fields == {
        "account_id": "A00001", "order_id": order.id, "symbol": "ACME",
        "qty": 4000000, "price": 11900000,
    }


def test_sweep_rejection_emits_r_event(market):
    orders.place_limit("A00003", "buy", "DYNA", sh("20"), usd("200"))
    orders.place_limit("A00003", "buy", "DYNA", sh("20"), usd("200"))
    before = len(recorded("A00003"))
    market.set("DYNA", "190")
    orders.sweep("A00003")
    new = recorded("A00003")[before:]
    assert [letter(name) for name, _ in new] == ["B", "R"]
    assert all(ids.validate(name) for name, _ in new)
    assert all(isinstance(fields["price"], int) and isinstance(fields["qty"], int) for _, fields in new)


def test_marketable_limit_sell_emits_s_event():
    orders.place_market("A00001", "buy", "ACME", sh("2"))
    orders.place_limit("A00001", "sell", "ACME", sh("1"), usd("12"))
    name, fields = recorded("A00001")[-1]
    assert ids.validate(name) and letter(name) == "S"
    assert fields["price"] == usd("12.5").unit


def test_event_numbers_stay_sequential(market):
    orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("12"))
    orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("13"))
    market.set("ACME", "11")
    orders.sweep("A00001")
    names = [name for name, _ in recorded("A00001")]
    numbers = [int(name.split("-")[2][1:6]) for name in names]
    assert all(ids.validate(name) for name in names)
    assert numbers == sorted(numbers) and len(set(numbers)) == len(numbers)


def test_limit_sell_uses_lot_matching_and_realized_pnl(clock, market):
    clock.set("2026-04-01T15:00:01.000000Z")
    market.set("ACME", "10")
    orders.place_market("A00001", "buy", "ACME", sh("3"))
    clock.set("2026-04-01T15:00:02.000000Z")
    market.set("ACME", "12")
    orders.place_market("A00001", "buy", "ACME", sh("5"))
    resting = orders.place_limit("A00001", "sell", "ACME", sh("4"), usd("14"))
    assert resting.status == transitions.NEW
    market.set("ACME", "15")
    assert [o.status for o in orders.sweep("A00001")] == [transitions.FILLED]
    remaining = sorted((lot.qty_remaining, lot.cost_per_share) for lot in lots.open_lots("A00001", "ACME"))
    assert remaining == [(1000000, usd("12").unit), (3000000, usd("10").unit)]
    summary = portfolio.show("A00001")
    assert summary.realized == usd("12")
    assert summary.positions[0].average_cost == usd("10.5")


def test_status_table_unchanged():
    assert (transitions.NEW, transitions.FILLED, transitions.REJECTED) == (40, 90, 60)
    assert {k: set(v) for k, v in transitions.ALLOWED.items()} == {
        transitions.NEW: {transitions.FILLED, transitions.REJECTED},
        transitions.FILLED: set(),
        transitions.REJECTED: set(),
    }


def test_filled_limit_order_cannot_move_again():
    order = orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("13"))
    with pytest.raises(transitions.InvalidTransition, match="Transition not allowed"):
        transitions.apply(order, transitions.REJECTED, price=usd("1"))


def test_limit_price_is_integer_units():
    order = orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("12.3456"))
    stored = orders.get("A00001", order.id)
    assert type(stored.limit_price) is int
    assert stored.limit_price == 12345600


def test_cli_rejects_limit_with_more_than_four_decimals(capsys):
    assert cli.main(["order", "place", "A00001", "buy", "ACME", "1", "--limit", "12.34567"]) != 0
    capsys.readouterr()


def test_schema_and_generated_model_declare_limit_price():
    schemas = sorted((config.ROOT / "schemas").glob("*.yaml"))
    assert any("limit_price" in path.read_text(encoding="utf-8") for path in schemas)
    generated = (config.ROOT / "tradebook" / "models_gen.py").read_text(encoding="utf-8")
    assert "@@GENERATED@@" in generated.splitlines()[0]
    from tradebook import models_gen
    assert "limit_price" in {field.name for field in dataclasses.fields(models_gen.Order)}


def blocked(monkeypatch, account_id, action):
    monkeypatch.setattr(config, "LOCK_TIMEOUT_MS", 50)
    acquired, release = threading.Event(), threading.Event()

    def holder():
        with hold(account_id):
            acquired.set()
            release.wait(5)

    worker = threading.Thread(target=holder)
    worker.start()
    acquired.wait(5)
    try:
        with pytest.raises(LockTimeout):
            action()
    finally:
        release.set()
        worker.join()


def test_place_limit_respects_account_lock(monkeypatch):
    blocked(monkeypatch, "A00001", lambda: orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("12")))


def test_sweep_respects_account_lock(monkeypatch, market):
    orders.place_limit("A00001", "buy", "ACME", sh("1"), usd("12"))
    market.set("ACME", "11")
    blocked(monkeypatch, "A00001", lambda: orders.sweep("A00001"))
