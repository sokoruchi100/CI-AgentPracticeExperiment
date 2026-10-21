import ast
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tradebook"
SEED = ROOT / "scripts" / "seed.py"
ACCOUNT_TABLES = {"accounts", "orders", "trades", "lots", "events"}
DB_FUNCS = {"add", "update", "delete", "read"}
LOT_FIELDS = {"qty_remaining", "opened_at"}
SQL_STATUS = re.compile(r"\bstatus\s*=", re.IGNORECASE)

failures = []


def fail(rule, path, node, message):
    location = path.relative_to(ROOT).as_posix()
    if node is not None:
        location += f":{node.lineno}"
    failures.append(f"[{rule}] {location}: {message}")


def parse(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node
    return tree


def source_files():
    return sorted(PKG.rglob("*.py")) + [SEED]


def is_db_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in DB_FUNCS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "db"
    )


def table_of(call):
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def is_hold(expr):
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    return (isinstance(func, ast.Name) and func.id == "hold") or (
        isinstance(func, ast.Attribute) and func.attr == "hold"
    )


def inside_hold(node):
    current = getattr(node, "parent", None)
    while current is not None:
        if isinstance(current, (ast.With, ast.AsyncWith)):
            if any(is_hold(item.context_expr) for item in current.items):
                return True
        current = getattr(current, "parent", None)
    return False


def is_int(node):
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return bool(node.elts) and all(is_int(elt) for elt in node.elts)
    return isinstance(node, ast.Constant) and type(node.value) is int


def mentions_status(node):
    if isinstance(node, ast.Name):
        return "status" in node.id
    if isinstance(node, ast.Attribute):
        return "status" in node.attr
    if isinstance(node, ast.Subscript):
        key = node.slice
        return isinstance(key, ast.Constant) and key.value == "status"
    return False


def check_generated():
    from scripts import gen_models

    target = gen_models.TARGET
    if not target.is_file() or target.read_text(encoding="utf-8") != gen_models.render():
        fail("generated-code", target, None, "models_gen.py is out of sync with schemas")


def check_floats(path, tree):
    if path.name in {"locking.py", "config.py"}:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (float, complex)):
            fail("integer-money", path, node, "float literal in a money or quantity path")
        elif isinstance(node, ast.Name) and node.id in {"float", "Decimal", "Fraction"}:
            fail("integer-money", path, node, f"{node.id} used in a money or quantity path")
        elif isinstance(node, ast.Attribute) and node.attr in {"Decimal", "Fraction"}:
            fail("integer-money", path, node, f"{node.attr} used in a money or quantity path")
        elif isinstance(node, (ast.BinOp, ast.AugAssign)) and isinstance(node.op, ast.Div):
            fail("integer-money", path, node, "true division in a money or quantity path")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(name.split(".")[0] in {"decimal", "fractions"} for name in names):
                fail("integer-money", path, node, "decimal or fractions imported")


def check_fixture():
    from tradebook import config

    def reject(text):
        raise ValueError(text)

    try:
        data = json.loads(config.QUOTES_PATH.read_text(encoding="utf-8"), parse_float=reject)
        bad = [item["symbol"] for item in data["instruments"] if type(item["price"]) is not int]
    except ValueError:
        bad = ["fixture"]
    if bad:
        fail("integer-money", config.QUOTES_PATH, None, "quote prices must be integer units")


def check_status(path, tree, assignments=True):
    if path.name in {"transitions.py", "models_gen.py"}:
        return
    for node in ast.walk(tree):
        if assignments:
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for target in targets:
                if isinstance(target, (ast.Attribute, ast.Subscript)) and mentions_status(target):
                    fail("status-transitions", path, node, "status assigned outside transitions.apply")
            if isinstance(node, ast.keyword) and node.arg == "status":
                fail("status-transitions", path, node.value, "status assigned outside transitions.apply")
            if isinstance(node, ast.Dict) and any(
                isinstance(key, ast.Constant) and key.value == "status" for key in node.keys
            ):
                fail("status-transitions", path, node, "status assigned outside transitions.apply")
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL_STATUS.search(node.value):
                fail("status-transitions", path, node, "status assigned outside transitions.apply")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "setattr"
                and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "status"
            ):
                fail("status-transitions", path, node, "status assigned outside transitions.apply")
        if isinstance(node, ast.Compare):
            operands = [node.left] + node.comparators
            if any(mentions_status(item) for item in operands) and any(is_int(item) for item in operands):
                fail("status-constants", path, node, "raw status number used instead of a named constant")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name == "apply" and len(node.args) > 1 and is_int(node.args[1]):
                fail("status-constants", path, node, "raw status number used instead of a named constant")
            for keyword in node.keywords:
                if keyword.arg in {"status", "new_status"} and is_int(keyword.value):
                    fail("status-constants", path, node, "raw status number used instead of a named constant")


def check_event_names(path, tree):
    if path.name == "ids.py":
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "TR-" in node.value:
            fail("event-names", path, node, "event name built outside ids.py")


def check_locks(path, tree):
    if path.name == "db.py":
        return
    for node in ast.walk(tree):
        if is_db_call(node):
            table = table_of(node)
            if (table is None or table in ACCOUNT_TABLES) and not inside_hold(node):
                fail("account-lock", path, node, f"db.{node.func.attr} on account data outside hold()")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == "db":
            fail("account-lock", path, node, "db functions must be called as db.<name>")
        elif isinstance(node, ast.Import) and any(alias.name == "sqlite3" for alias in node.names):
            fail("account-lock", path, node, "sqlite3 used outside db.py")


def check_lots(path, tree):
    if path.name in {"lots.py", "models_gen.py"}:
        return
    for node in ast.walk(tree):
        if is_db_call(node) and table_of(node) == "lots":
            fail("lot-matching", path, node, "lot data accessed outside lots.py")
        elif isinstance(node, ast.Attribute) and node.attr in LOT_FIELDS:
            fail("lot-matching", path, node, "lot data accessed outside lots.py")
        elif isinstance(node, ast.keyword) and node.arg in LOT_FIELDS:
            fail("lot-matching", path, node, "lot data accessed outside lots.py")
        elif isinstance(node, ast.Constant) and node.value in LOT_FIELDS:
            fail("lot-matching", path, node, "lot data accessed outside lots.py")


def check_scenario():
    from scripts.seed import init_database
    from tradebook import config, events, ids, quotes, transitions
    from tradebook.money import parse_shares, parse_usd
    from tradebook.services import accounts, orders

    original = config.DB_PATH
    with tempfile.TemporaryDirectory() as tmp:
        config.DB_PATH = Path(tmp) / "check.db"
        try:
            init_database()
            symbol = quotes.instruments()[0][0]
            account = accounts.open_account()
            accounts.deposit(account.id, parse_usd("1000"))
            results = [
                orders.place_market(account.id, transitions.BUY, symbol, parse_shares("2")),
                orders.place_market(account.id, transitions.SELL, symbol, parse_shares("1")),
                orders.place_market(account.id, transitions.BUY, symbol, parse_shares("1000000")),
            ]
            names = [event.name for event in events.for_account(account.id)]
        finally:
            config.DB_PATH = original
    expected = [transitions.FILLED, transitions.FILLED, transitions.REJECTED]
    if [order.status for order in results] != expected:
        fail("audit-events", SEED, None, "scenario orders did not end in the expected statuses")
    if len(names) != 5:
        fail("audit-events", SEED, None, f"scenario recorded {len(names)} events, expected 5")
    for name in names:
        if not ids.validate(name):
            fail("audit-events", SEED, None, f"invalid event name {name}")


def main():
    check_generated()
    check_fixture()
    for path in source_files():
        tree = parse(path)
        check_floats(path, tree)
        check_status(path, tree)
        check_event_names(path, tree)
        check_locks(path, tree)
        check_lots(path, tree)
    for path in sorted((ROOT / "tests").glob("*.py")):
        check_status(path, parse(path), assignments=False)
    if not failures:
        try:
            check_scenario()
        except Exception as exc:
            fail("audit-events", SEED, None, f"scenario failed: {exc}")
    for line in failures:
        print(line)
    if failures:
        print(f"check failed: {len(failures)} problem(s)")
        return 1
    print("check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
