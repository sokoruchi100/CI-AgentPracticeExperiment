import os

from tradebook import config, db, ids, money, quotes
from tradebook.services import accounts

SEED_TIME = "2026-01-05T14:30:00.000000Z"
SEED_DEPOSITS = ("100000", "25000", "5000.50")


def init_database():
    db.create_schema()
    ids.install_counters()
    for symbol, name in quotes.instruments():
        db.add("instruments", symbol=symbol, name=name)


def main():
    target = config.DB_PATH
    staging = target.with_name(target.name + ".tmp")
    if staging.exists():
        staging.unlink()
    config.DB_PATH = staging
    config.now = lambda: SEED_TIME
    init_database()
    for amount in SEED_DEPOSITS:
        account = accounts.open_account()
        accounts.deposit(account.id, money.parse_usd(amount))
    os.replace(staging, target)
    print(f"seeded {target.name}")


if __name__ == "__main__":
    main()
