"""Materialize publication metadata that used to live only in Python/JSON context."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.warehouse.publication import PublicationContext


CONTEXT_TABLES = {
    "coverage_universe": "coverage_universes",
    "coverage_universe_member": "coverage_universe_members",
}

PROOF_TABLES = frozenset({"publication_file", "publication_review", "publication_gate_result"})


def warehouse_content_fingerprint(database: Path) -> tuple[str, int]:
    """Digest substantive schemas and rows without self-referential proof tables."""
    connection = duckdb.connect(str(database), read_only=True)
    digest = hashlib.sha256()
    logical_bytes = 0
    try:
        tables = sorted(
            row[0] for row in connection.execute("SHOW TABLES").fetchall()
            if row[0] not in PROOF_TABLES
        )
        for table in tables:
            description = connection.execute(f'DESCRIBE "{table}"').fetchall()
            rows = connection.execute(f'SELECT * FROM "{table}"').fetchall()
            payload = {
                "table": table,
                "columns": [(row[0], row[1], row[2]) for row in description],
                "rows": sorted(
                    json.dumps(row, default=str, ensure_ascii=False, separators=(",", ":"))
                    for row in rows
                ),
            }
            encoded = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            digest.update(encoded)
            digest.update(b"\n")
            logical_bytes += len(encoded) + 1
    finally:
        connection.close()
    return digest.hexdigest(), logical_bytes


def warehouse_content_sha256(database: Path) -> str:
    return warehouse_content_fingerprint(database)[0]


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


def materialize_publication_proofs(
    database: Path,
    *,
    files: Sequence[Mapping[str, Any]],
    reviews: Mapping[str, Sequence[Mapping[str, Any]]],
    gate_results: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Persist the stable, logical publication index and its review decisions."""
    review_rows: list[dict[str, Any]] = []
    release_by_path = {str(row["relative_path"]): str(row["release_id"]) for row in files}
    for key, review_type in (
        ("license_reviews", "LICENSE"),
        ("privacy_reviews", "PRIVACY"),
        ("claim_reviews", "CLAIM_CLASS"),
    ):
        for review in reviews.get(key, ()):
            relative = str(review["relative_path"])
            review_rows.append({
                **review,
                "release_id": release_by_path[relative],
                "review_type": review_type,
                "decision": review.get("decision") or review.get("claim_class"),
                "notes": review.get("finding") or review.get("uncertainty_disclosure"),
            })
    connection = duckdb.connect(str(database))
    try:
        connection.execute("BEGIN TRANSACTION")
        _replace_rows(connection, "publication_file", files)
        _replace_rows(connection, "publication_review", review_rows)
        _replace_rows(connection, "publication_gate_result", gate_results)
        connection.execute("COMMIT")
        return {
            table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            for table in PROOF_TABLES
        }
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
