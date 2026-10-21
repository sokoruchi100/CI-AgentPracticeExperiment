import json

from tradebook import config, db, ids
from tradebook.locking import hold
from tradebook.models_gen import Event


class InvalidEventName(ValueError):
    pass


def emit(name, **fields):
    if not ids.validate(name):
        raise InvalidEventName("Invalid event name")
    if "account_id" not in fields:
        raise ValueError("Events require an account_id")
    account_id = fields["account_id"]
    payload = json.dumps(fields, sort_keys=True)
    emitted_at = config.now()
    with hold(account_id):
        event_id = db.add("events", name=name, fields=payload, emitted_at=emitted_at)
    return Event(id=event_id, name=name, fields=payload, emitted_at=emitted_at)


def for_account(account_id):
    with hold(account_id):
        rows = db.read("events")
    return [
        Event(**row)
        for row in rows
        if json.loads(row["fields"]).get("account_id") == account_id
    ]
