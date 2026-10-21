from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"
TARGET = ROOT / "tradebook" / "models_gen.py"
BANNER = "# @@GENERATED@@"
PY_TYPES = {"int": "int", "str": "str"}
SQL_TYPES = {"int": "INTEGER", "str": "TEXT"}


def load_schemas():
    return [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(SCHEMA_DIR.glob("*.yaml"))
    ]


def column_sql(column):
    sql = f"{column['name']} {SQL_TYPES[column['type']]}"
    primary = column.get("primary")
    if primary == "auto":
        return sql + " PRIMARY KEY AUTOINCREMENT"
    if primary:
        return sql + " PRIMARY KEY"
    return sql + " NOT NULL"


def render():
    schemas = load_schemas()
    lines = [BANNER, "from dataclasses import dataclass", ""]
    for schema in schemas:
        lines += ["", "@dataclass(frozen=True)", f"class {schema['model']}:"]
        lines += [
            f"    {column['name']}: {PY_TYPES[column['type']]}"
            for column in schema["columns"]
        ]
        lines.append("")
    lines += ["", "TABLES = {"]
    for schema in schemas:
        names = ", ".join(repr(column["name"]) for column in schema["columns"])
        lines.append(f"    {schema['table']!r}: ({names},),")
    lines += ["}", "", "MODELS = {"]
    for schema in schemas:
        lines.append(f"    {schema['table']!r}: {schema['model']},")
    lines += ["}", "", "DDL = ("]
    for schema in schemas:
        columns = ", ".join(column_sql(column) for column in schema["columns"])
        lines.append(f"    {'CREATE TABLE ' + schema['table'] + ' (' + columns + ')'!r},")
    lines.append(")")
    return "\n".join(lines) + "\n"


def main():
    TARGET.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {TARGET.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
