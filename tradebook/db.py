import sqlite3
from contextlib import closing
from pathlib import Path

from tradebook import config, models_gen


def _connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(table, names):
    known = models_gen.TABLES.get(table)
    if known is None:
        raise ValueError(f"Unknown table: {table}")
    for name in names:
        if name not in known:
            raise ValueError(f"Unknown column: {table}.{name}")
    return list(names)


def _where(table, where):
    if not where:
        return "", []
    columns = _columns(table, sorted(where))
    clause = " WHERE " + " AND ".join(f"{column} = ?" for column in columns)
    return clause, [where[column] for column in columns]


def _write(sql, params):
    with closing(_connect()) as conn:
        with conn:
            cursor = conn.execute(sql, params)
        return cursor


def add(table, **values):
    columns = _columns(table, list(values))
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    return _write(sql, [values[column] for column in columns]).lastrowid


def update(table, where, **values):
    columns = _columns(table, list(values))
    clause, params = _where(table, where)
    assignments = ", ".join(f"{column} = ?" for column in columns)
    sql = f"UPDATE {table} SET {assignments}{clause}"
    return _write(sql, [values[column] for column in columns] + params).rowcount


def delete(table, where):
    clause, params = _where(table, where)
    return _write(f"DELETE FROM {table}{clause}", params).rowcount


def read(table, where=None, order_by=()):
    clause, params = _where(table, where)
    order = ", ".join(_columns(table, list(order_by))) or "rowid"
    with closing(_connect()) as conn:
        rows = conn.execute(f"SELECT * FROM {table}{clause} ORDER BY {order}", params)
        return [dict(row) for row in rows.fetchall()]


def bump(counter):
    sql = "UPDATE counters SET value = value + 1 WHERE name = ? RETURNING value - 1"
    with closing(_connect()) as conn:
        with conn:
            row = conn.execute(sql, (counter,)).fetchone()
    if row is None:
        raise RuntimeError("Database not initialized")
    return row[0]


def create_schema():
    with closing(_connect()) as conn:
        with conn:
            for statement in models_gen.DDL:
                conn.execute(statement)


def require_initialized():
    path = Path(config.DB_PATH)
    if not path.is_file():
        raise RuntimeError("Database not initialized")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
    except sqlite3.Error:
        count = 0
    if count == 0:
        raise RuntimeError("Database not initialized")
