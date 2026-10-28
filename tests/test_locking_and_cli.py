import threading

import pytest

from tradebook import cli, config, quotes
from tradebook.locking import LockTimeout, hold


def test_hold_is_reentrant():
    with hold("A00001"):
        with hold("A00001"):
            pass


def test_hold_times_out_when_another_thread_holds(monkeypatch):
    monkeypatch.setattr(config, "LOCK_TIMEOUT_MS", 50)
    acquired = threading.Event()
    release = threading.Event()

    def holder():
        with hold("A00002"):
            acquired.set()
            release.wait(5)

    worker = threading.Thread(target=holder)
    worker.start()
    acquired.wait(5)
    try:
        with pytest.raises(LockTimeout, match="Lock timeout"):
            with hold("A00002"):
                pass
        with hold("A00001"):
            pass
    finally:
        release.set()
        worker.join()


def test_quote_fixture_is_integer_units():
    symbols = [symbol for symbol, _ in quotes.instruments()]
    assert len(symbols) == 50 and symbols == sorted(symbols)
    assert {"ACME", "BOLT", "CRUX", "DYNA"} <= set(symbols)
    assert quotes.current("ACME").unit == 12500000


def run(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    return code, out.strip().splitlines(), err.strip()


def test_cli_flow(capsys):
    code, out, _ = run(capsys, "account", "open")
    assert code == 0
    account_id = out[0].split()[0]
    assert run(capsys, "account", "deposit", account_id, "1000.25")[1] == [f"{account_id} cash 1000.2500"]
    code, out, _ = run(capsys, "order", "place", account_id, "buy", "ACME", "4")
    assert out == ["order 1 FILLED buy ACME 4.0000 @ 12.5000"]
    code, out, _ = run(capsys, "order", "place", account_id, "sell", "ACME", "1.5")
    assert out == ["order 2 FILLED sell ACME 1.5000 @ 12.5000"]
    assert run(capsys, "order", "show", account_id, "2")[1] == out
    assert run(capsys, "portfolio", "show", account_id)[1] == [
        f"account {account_id}",
        "cash 969.0000",
        "position ACME 2.5000 avg 12.5000",
        "realized 0.0000",
    ]


def test_cli_reports_errors(capsys):
    code, _, err = run(capsys, "account", "show", "A99999")
    assert code == 1
    assert err == "error: Account not found: A99999"
    code, _, err = run(capsys, "account", "deposit", "A00001", "1.5e3")
    assert code == 1
