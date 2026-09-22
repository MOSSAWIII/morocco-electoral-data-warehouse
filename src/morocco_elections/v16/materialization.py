"""Materialize publication metadata that used to live only in Python/JSON context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.v16.publication import PublicationContext


CONTEXT_TABLES = {
    "coverage_universe": "coverage_universes",
    "coverage_universe_member": "coverage_universe_members",
}


def _replace_rows(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    columns = [row[0] for row in connection.execute(f'DESCRIBE "{table}"').fetchall()]
    connection.execute(f'DELETE FROM "{table}"')
    if not rows:
        return
    selected = [column for column in columns if any(column in row for row in rows)]
    quoted = ", ".join(f'"{column}"' for column in selected)
    placeholders = ", ".join("?" for _ in selected)
    connection.executemany(
        f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
        [[row.get(column) for column in selected] for row in rows],
    )


def materialize_publication_inputs(database: Path, context: PublicationContext) -> dict[str, int]:
    """Replace derived coverage tables in one transaction and return their row counts."""
    connection = duckdb.connect(str(database))
    try:
        connection.execute("BEGIN TRANSACTION")
        for table, dataset in CONTEXT_TABLES.items():
            _replace_rows(connection, table, list(context.datasets.get(dataset, ())))
        _replace_rows(connection, "release_coverage_matrix", context.coverage_matrix)
        connection.execute("COMMIT")
        return {
            table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            for table in (*CONTEXT_TABLES, "release_coverage_matrix")
        }
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
