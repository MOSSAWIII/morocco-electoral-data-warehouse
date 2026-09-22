from __future__ import annotations

import hashlib
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import duckdb


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _canonical(value: Any) -> bytes:
    if value is None:
        return b"N;"
    if isinstance(value, bool):
        return b"B1;" if value else b"B0;"
    if isinstance(value, int):
        return f"I{value};".encode("ascii")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Une valeur flottante non finie ne peut pas être publiée")
        return f"F{value.hex()};".encode("ascii")
    if isinstance(value, (date, datetime)):
        return f"D{value.isoformat()};".encode("ascii")
    encoded = str(value).encode("utf-8")
    return f"S{len(encoded)}:".encode("ascii") + encoded + b";"


def digest_rows(rows: Iterable[tuple[Any, ...]]) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        digest.update(b"R")
        for value in row:
            digest.update(_canonical(value))
        digest.update(b"\n")
        count += 1
    return digest.hexdigest(), count


def digest_query(connection: duckdb.DuckDBPyConnection, query: str) -> tuple[str, int]:
    cursor = connection.execute(query)

    def batches() -> Iterable[tuple[Any, ...]]:
        while rows := cursor.fetchmany(10_000):
            yield from rows

    return digest_rows(batches())


def ordered_query(relation: str, contract: dict[str, Any]) -> str:
    columns = ", ".join(_quote(column["name"]) for column in contract["columns"])
    order = ", ".join(_quote(column) for column in contract["primary_key"])
    return f"SELECT {columns} FROM {relation} ORDER BY {order}"


def duckdb_digest(connection: duckdb.DuckDBPyConnection, contract: dict[str, Any]) -> tuple[str, int]:
    return digest_query(connection, ordered_query(_quote(contract["table_name"]), contract))


def parquet_digest(connection: duckdb.DuckDBPyConnection, path: Path, contract: dict[str, Any]) -> tuple[str, int]:
    relation = f"read_parquet({_sql_string(path.as_posix())})"
    return digest_query(connection, ordered_query(relation, contract))


def csv_digest(connection: duckdb.DuckDBPyConnection, path: Path, contract: dict[str, Any]) -> tuple[str, int]:
    definitions = ", ".join(
        f"{_sql_string(column['name'])}: {_sql_string(column['type'])}" for column in contract["columns"]
    )
    relation = (
        f"read_csv({_sql_string(path.as_posix())}, header=true, columns={{{definitions}}}, "
        "dateformat='%Y-%m-%d', nullstr='', allow_quoted_nulls=false, strict_mode=true)"
    )
    return digest_query(connection, ordered_query(relation, contract))
