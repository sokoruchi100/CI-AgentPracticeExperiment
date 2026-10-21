import re

from tradebook import db

ACCOUNT_PATTERN = re.compile(r"^A[0-9]{5}$")
EVENT_PATTERN = re.compile(r"^TR-(A[0-9]{5})-([BSDOR])([0-9]{5})([MATCHING])$")
ACTION_LETTERS = "BSDOR"
CHECK_LETTERS = "MATCHING"
EVENT_COUNTER = "event_number"
ACCOUNT_COUNTER = "account_number"
COUNTER_STARTS = {EVENT_COUNTER: 10000, ACCOUNT_COUNTER: 1}
MAX_NUMBER = 99999


def install_counters():
    for name, start in COUNTER_STARTS.items():
        db.add("counters", name=name, value=start)


def _digits(number):
    if not 0 <= number <= MAX_NUMBER:
        raise ValueError("ID number out of range")
    return f"{number:05d}"


def check_char(digits):
    if not re.fullmatch(r"[0-9]{5}", digits):
        raise ValueError("Check digits must be 5 digits")
    total = sum(position * int(digit) for position, digit in enumerate(digits, start=1))
    return CHECK_LETTERS[total % len(CHECK_LETTERS)]


def account_id(number):
    return "A" + _digits(number)


def new_account_id():
    return account_id(db.bump(ACCOUNT_COUNTER))


def validate_account_id(value):
    return isinstance(value, str) and ACCOUNT_PATTERN.fullmatch(value) is not None


def action_id(letter, number):
    if letter not in ACTION_LETTERS or len(letter) != 1:
        raise ValueError("Invalid action letter")
    return letter + _digits(number)


def next_event_number():
    return db.bump(EVENT_COUNTER)


def event_name(account, letter):
    if not validate_account_id(account):
        raise ValueError("Invalid account ID")
    action = action_id(letter, next_event_number())
    name = f"TR-{account}-{action}{check_char(action[1:])}"
    if not validate(name):
        raise ValueError("Invalid event name")
    return name


def validate(name):
    if not isinstance(name, str):
        return False
    match = EVENT_PATTERN.fullmatch(name)
    return match is not None and check_char(match.group(3)) == match.group(4)
