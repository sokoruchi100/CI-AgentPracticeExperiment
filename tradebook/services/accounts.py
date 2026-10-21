from tradebook import db, events, ids
from tradebook.locking import hold
from tradebook.models_gen import Account
from tradebook.money import USDollar


class AccountNotFound(LookupError):
    pass


def open_account():
    account_id = ids.new_account_id()
    with hold(account_id):
        db.add("accounts", id=account_id, cash=0)
        events.emit(ids.event_name(account_id, "O"), account_id=account_id)
    return Account(id=account_id, cash=0)


def get(account_id):
    with hold(account_id):
        rows = db.read("accounts", {"id": account_id})
    if not rows:
        raise AccountNotFound(f"Account not found: {account_id}")
    return Account(**rows[0])


def cash(account_id):
    return USDollar(get(account_id).cash)


def _set_cash(account_id, amount):
    if amount.unit < 0:
        raise ValueError("Cash cannot be negative")
    with hold(account_id):
        db.update("accounts", {"id": account_id}, cash=amount.unit)
    return Account(id=account_id, cash=amount.unit)


def deposit(account_id, amount):
    if amount.unit <= 0:
        raise ValueError("Deposit must be positive")
    with hold(account_id):
        account = _set_cash(account_id, cash(account_id) + amount)
        events.emit(
            ids.event_name(account_id, "D"),
            account_id=account_id,
            amount=amount.unit,
        )
    return account


def debit(account_id, amount):
    with hold(account_id):
        return _set_cash(account_id, cash(account_id) - amount)


def credit(account_id, amount):
    with hold(account_id):
        return _set_cash(account_id, cash(account_id) + amount)
