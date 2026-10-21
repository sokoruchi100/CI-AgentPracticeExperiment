from tradebook import config, db, money
from tradebook.locking import hold
from tradebook.models_gen import Lot
from tradebook.money import Share, USDollar


def open_lot(account_id, symbol, qty, cost_per_share):
    opened_at = config.now()
    with hold(account_id):
        lot_id = db.add(
            "lots",
            account_id=account_id,
            symbol=symbol,
            qty_remaining=qty.shunit,
            cost_per_share=cost_per_share.unit,
            opened_at=opened_at,
        )
    return Lot(
        id=lot_id,
        account_id=account_id,
        symbol=symbol,
        qty_remaining=qty.shunit,
        cost_per_share=cost_per_share.unit,
        opened_at=opened_at,
    )


def open_lots(account_id, symbol=None):
    where = {"account_id": account_id}
    if symbol is not None:
        where["symbol"] = symbol
    with hold(account_id):
        rows = db.read("lots", where)
    return [Lot(**row) for row in rows if row["qty_remaining"] > 0]


def held(account_id, symbol):
    return Share(sum(lot.qty_remaining for lot in open_lots(account_id, symbol)))


def _rank(lot):
    return (-lot.qty_remaining, lot.opened_at, lot.id)


def consume(account_id, symbol, qty):
    with hold(account_id):
        if held(account_id, symbol) < qty:
            raise ValueError("Insufficient holdings")
        needed = qty.shunit
        total = USDollar(0)
        while needed > 0:
            lot = min(open_lots(account_id, symbol), key=_rank)
            take = min(needed, lot.qty_remaining)
            total = total + money.cost(USDollar(lot.cost_per_share), Share(take))
            db.update("lots", {"id": lot.id}, qty_remaining=lot.qty_remaining - take)
            needed -= take
    return total


def positions(account_id):
    totals = {}
    for lot in open_lots(account_id):
        qty, basis = totals.get(lot.symbol, (Share(0), USDollar(0)))
        portion = money.cost(USDollar(lot.cost_per_share), Share(lot.qty_remaining))
        totals[lot.symbol] = (qty + Share(lot.qty_remaining), basis + portion)
    return [(symbol, qty, basis) for symbol, (qty, basis) in sorted(totals.items())]
