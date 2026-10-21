import pytest

from tradebook import config, db, ids


@pytest.mark.parametrize(
    "digits, letter",
    [("33234", "G"), ("23417", "C"), ("63256", "H"), ("00000", "M"), ("10000", "A")],
)
def test_check_char(digits, letter):
    assert ids.check_char(digits) == letter


@pytest.mark.parametrize(
    "name",
    ["TR-A01290-B33234G", "TR-A01290-S23417C", "TR-A51509-D63256H"],
)
def test_validate_accepts_valid_names(name):
    assert ids.validate(name)


@pytest.mark.parametrize(
    "name",
    [
        "TR-A01290-B33234M",
        "TR-A0129-B33234G",
        "TR-A01290-X33234G",
        "TR-A01290-B33234G\n",
        "tr-A01290-B33234G",
        None,
    ],
)
def test_validate_rejects_invalid_names(name):
    assert not ids.validate(name)


def test_event_counter_starts_at_10000(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "fresh.db")
    db.create_schema()
    ids.install_counters()
    assert ids.next_event_number() == 10000
    assert ids.next_event_number() == 10001
    assert ids.new_account_id() == "A00001"


def test_event_name_uses_next_number():
    first = ids.event_name("A00001", "D")
    second = ids.event_name("A00001", "D")
    assert ids.validate(first) and ids.validate(second)
    assert int(second[11:16]) == int(first[11:16]) + 1


def test_event_name_rejects_bad_parts():
    with pytest.raises(ValueError):
        ids.event_name("B00001", "D")
    with pytest.raises(ValueError):
        ids.event_name("A00001", "X")
