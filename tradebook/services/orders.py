from tradebook import config, db, lots, money, quotes, transitions
from tradebook.locking import hold
from tradebook.models_gen import Order, Trade
from tradebook.money import Share, USDollar
from tradebook.services import accounts


class OrderNotFound(LookupError):
    pass


def place_market(account_id, side, symbol, qty):
    if side not in transitions.SIDES:
        raise ValueError("Side must be buy or sell")
    if qty.shunit <= 0:
        raise ValueError("Quantity must be positive")
    price = quotes.current(symbol)
    with hold(account_id):
        accounts.get(account_id)
        order = transitions.open_order(account_id, symbol, side, qty)
        if side == transitions.BUY:
            return _buy(order, price)
        return _sell(order, price)


def _record_trade(order, price, realized):
    with hold(order.account_id):
        db.add(
            "trades",
            order_id=order.id,
            qty=order.qty,
            price=price.unit,
            realized=realized.unit,
            executed_at=config.now(),
        )


def _buy(order, price):
    qty = Share(order.qty)
    total = money.cost(price, qty)
    with hold(order.account_id):
        if total > accounts.cash(order.account_id):
            return transitions.apply(order, transitions.REJECTED, price=price)
        accounts.debit(order.account_id, total)
        lots.open_lot(order.account_id, order.symbol, qty, price)
        _record_trade(order, price, USDollar(0))
        return transitions.apply(order, transitions.FILLED, price=price)


def _sell(order, price):
    qty = Share(order.qty)
    with hold(order.account_id):
        if qty > lots.held(order.account_id, order.symbol):
            return transitions.apply(order, transitions.REJECTED, price=price)
        basis = lots.consume(order.account_id, order.symbol, qty)
        proceeds = money.cost(price, qty)
        accounts.credit(order.account_id, proceeds)
        _record_trade(order, price, proceeds - basis)
        return transitions.apply(order, transitions.FILLED, price=price)


def get(account_id, order_id):
    with hold(account_id):
        rows = db.read("orders", {"id": order_id, "account_id": account_id})
    if not rows:
        raise OrderNotFound(f"Order not found: {order_id}")
    return Order(**rows[0])


def for_account(account_id):
    with hold(account_id):
        rows = db.read("orders", {"account_id": account_id})
    return [Order(**row) for row in rows]


def trade(account_id, order_id):
    with hold(account_id):
        get(account_id, order_id)
        rows = db.read("trades", {"order_id": order_id})
    return Trade(**rows[0]) if rows else None
