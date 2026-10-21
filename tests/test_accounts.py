import json

import pytest

from tradebook import events, ids
from tradebook.money import USDollar, parse_usd
from tradebook.services import accounts


def test_seeded_accounts_exist():
    assert accounts.get("A00001").cash == parse_usd("100000").unit
    assert accounts.get("A00003").cash == parse_usd("5000.50").unit


def test_open_account_emits_opening_event():
    account = accounts.open_account()
    assert ids.validate_account_id(account.id)
    assert account.cash == 0
    recorded = events.for_account(account.id)
    assert len(recorded) == 1
    assert recorded[0].name[10] == "O"
    assert json.loads(recorded[0].fields) == {"account_id": account.id}


def test_deposit_adds_cash_and_emits_event():
    account = accounts.open_account()
    updated = accounts.deposit(account.id, parse_usd("250.75"))
    assert updated.cash == 250750000
    deposit_event = events.for_account(account.id)[-1]
    assert deposit_event.name[10] == "D"
    assert json.loads(deposit_event.fields) == {"account_id": account.id, "amount": 250750000}


def test_deposit_must_be_positive():
    with pytest.raises(ValueError):
        accounts.deposit("A00001", USDollar(0))


def test_missing_account():
    with pytest.raises(accounts.AccountNotFound):
        accounts.get("A99999")


def test_seed_events_are_valid():
    for account_id in ("A00001", "A00002", "A00003"):
        names = [event.name for event in events.for_account(account_id)]
        assert [name[10] for name in names] == ["O", "D"]
        assert all(ids.validate(name) for name in names)
