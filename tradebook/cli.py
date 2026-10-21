import argparse
import sys

from tradebook import db, money, transitions
from tradebook.locking import LockTimeout
from tradebook.money import Share, USDollar
from tradebook.services import accounts, orders, portfolio


def _account_lines(account):
    return [f"{account.id} cash {money.format_usd(USDollar(account.cash))}"]


def _order_lines(account_id, order):
    line = (
        f"order {order.id} {transitions.NAMES[order.status]} {order.side} "
        f"{order.symbol} {money.format_shares(Share(order.qty))}"
    )
    filled = orders.trade(account_id, order.id)
    if filled is not None:
        line += f" @ {money.format_usd(USDollar(filled.price))}"
    return [line]


def _portfolio_lines(summary):
    lines = [f"account {summary.account_id}", f"cash {money.format_usd(summary.cash)}"]
    for position in summary.positions:
        lines.append(
            f"position {position.symbol} {money.format_shares(position.qty)} "
            f"avg {money.format_usd(position.average_cost)}"
        )
    lines.append(f"realized {money.format_usd(summary.realized)}")
    return lines


def build_parser():
    parser = argparse.ArgumentParser(prog="tradebook")
    groups = parser.add_subparsers(dest="group", required=True)

    account = groups.add_parser("account").add_subparsers(dest="action", required=True)
    account.add_parser("open")
    deposit = account.add_parser("deposit")
    deposit.add_argument("account_id")
    deposit.add_argument("amount")
    account.add_parser("show").add_argument("account_id")

    order = groups.add_parser("order").add_subparsers(dest="action", required=True)
    place = order.add_parser("place")
    place.add_argument("account_id")
    place.add_argument("side", choices=transitions.SIDES)
    place.add_argument("symbol")
    place.add_argument("qty")
    show = order.add_parser("show")
    show.add_argument("account_id")
    show.add_argument("order_id", type=int)

    holdings = groups.add_parser("portfolio").add_subparsers(dest="action", required=True)
    holdings.add_parser("show").add_argument("account_id")
    return parser


def run(args):
    command = (args.group, args.action)
    if command == ("account", "open"):
        return _account_lines(accounts.open_account())
    if command == ("account", "deposit"):
        return _account_lines(accounts.deposit(args.account_id, money.parse_usd(args.amount)))
    if command == ("account", "show"):
        return _account_lines(accounts.get(args.account_id))
    if command == ("order", "place"):
        qty = money.parse_shares(args.qty)
        placed = orders.place_market(args.account_id, args.side, args.symbol, qty)
        return _order_lines(args.account_id, placed)
    if command == ("order", "show"):
        return _order_lines(args.account_id, orders.get(args.account_id, args.order_id))
    return _portfolio_lines(portfolio.show(args.account_id))


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        db.require_initialized()
        for line in run(args):
            print(line)
    except (RuntimeError, ValueError, LookupError, transitions.InvalidTransition, LockTimeout) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
