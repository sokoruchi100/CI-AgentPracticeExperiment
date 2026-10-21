from dataclasses import dataclass

from tradebook import lots, money
from tradebook.locking import hold
from tradebook.money import Share, USDollar
from tradebook.services import accounts, orders


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: Share
    average_cost: USDollar


@dataclass(frozen=True)
class Summary:
    account_id: str
    cash: USDollar
    positions: list
    realized: USDollar


def show(account_id):
    with hold(account_id):
        cash = accounts.cash(account_id)
        positions = [
            Position(symbol, qty, money.average_cost(basis, qty))
            for symbol, qty, basis in lots.positions(account_id)
        ]
        realized = USDollar(0)
        for order in orders.for_account(account_id):
            filled = orders.trade(account_id, order.id)
            if filled is not None:
                realized = realized + USDollar(filled.realized)
    return Summary(account_id, cash, positions, realized)
