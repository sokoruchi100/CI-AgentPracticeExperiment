from dataclasses import replace

from tradebook import config, db, events, ids
from tradebook.locking import hold
from tradebook.models_gen import Order

NEW = 40
FILLED = 90
REJECTED = 60

ALLOWED = {
    NEW: frozenset({FILLED, REJECTED}),
    FILLED: frozenset(),
    REJECTED: frozenset(),
}

NAMES = {NEW: "NEW", FILLED: "FILLED", REJECTED: "REJECTED"}

BUY = "buy"
SELL = "sell"
SIDES = (BUY, SELL)


class InvalidTransition(Exception):
    pass


def open_order(account_id, symbol, side, qty):
    created_at = config.now()
    with hold(account_id):
        order_id = db.add(
            "orders",
            account_id=account_id,
            symbol=symbol,
            side=side,
            qty=qty.shunit,
            status=NEW,
            created_at=created_at,
        )
    return Order(
        id=order_id,
        account_id=account_id,
        symbol=symbol,
        side=side,
        qty=qty.shunit,
        status=NEW,
        created_at=created_at,
    )


def _event_letter(order, new_status):
    if new_status == REJECTED:
        return "R"
    return "B" if order.side == BUY else "S"


def apply(order, new_status, *, price):
    with hold(order.account_id):
        rows = db.read("orders", {"id": order.id})
        current = rows[0]["status"] if rows else None
        if new_status not in ALLOWED.get(current, frozenset()):
            raise InvalidTransition("Transition not allowed")
        db.update("orders", {"id": order.id}, status=new_status)
        events.emit(
            ids.event_name(order.account_id, _event_letter(order, new_status)),
            account_id=order.account_id,
            order_id=order.id,
            symbol=order.symbol,
            qty=order.qty,
            price=price.unit,
        )
    return replace(order, status=new_status)
