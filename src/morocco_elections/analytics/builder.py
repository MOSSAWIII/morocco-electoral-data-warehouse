from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

import duckdb

from morocco_elections.analytics import ANALYTICS_SCHEMA_VERSION
from morocco_elections.analytics.column_contracts import COLUMN_CONTRACTS
from morocco_elections.analytics.contracts import MART_CONTRACTS, SQL_DIRECTORY
from morocco_elections.analytics.provenance import manifest_identity, sha256
from morocco_elections.analytics.upstream_contract import validate_upstream_database
from morocco_elections.analytics.validator import validate_analytics_database


MART_SPECS = {name: (contract.grain, contract.key) for name, contract in MART_CONTRACTS.items()}


class AnalyticsBuildError(RuntimeError):
    pass


def _create_catalogs(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE analytics_table_catalog (
          table_name VARCHAR PRIMARY KEY, sql_file VARCHAR NOT NULL, dependencies VARCHAR NOT NULL,
          grain VARCHAR NOT NULL, key_columns VARCHAR NOT NULL
        )
    """)
    connection.executemany(
        "INSERT INTO analytics_table_catalog VALUES (?, ?, ?, ?, ?)",
        [(name, item.sql_file, ",".join(item.dependencies), item.grain, ",".join(item.key)) for name, item in MART_CONTRACTS.items()],
    )
    connection.execute("""
        CREATE TABLE analytics_column_catalog (
          table_name VARCHAR NOT NULL, column_name VARCHAR NOT NULL, data_type VARCHAR NOT NULL,
          unit VARCHAR NOT NULL, meaning VARCHAR NOT NULL, nullable BOOLEAN NOT NULL,
          calculation VARCHAR NOT NULL, status_column VARCHAR, source VARCHAR NOT NULL, limitation VARCHAR,
          PRIMARY KEY (table_name, column_name)
        )
    """)
    rows = []
    for table, columns in COLUMN_CONTRACTS.items():
        types = {row[0]: row[1] for row in connection.execute(f"DESCRIBE {table}").fetchall()}
        for name, item in columns.items():
            rows.append((table, name, types[name], item.unit, item.meaning, item.nullable, item.calculation,
                         item.status_column, item.source, item.limitation))
    connection.executemany("INSERT INTO analytics_column_catalog VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    connection.execute("""
        CREATE TABLE analytics_join_contracts (
          left_table VARCHAR NOT NULL, right_table VARCHAR NOT NULL, join_keys VARCHAR NOT NULL,
          cardinality VARCHAR NOT NULL, rationale VARCHAR NOT NULL,
          PRIMARY KEY (left_table, right_table, join_keys)
        )
    """)
    connection.execute("""
        INSERT INTO analytics_join_contracts VALUES
          ('mart_contest_results', 'mart_contest_competitiveness', 'contest_id,election_id,ballot_type',
           'MANY_TO_ONE', 'Competition has exactly one row per contest, election and ballot')
    """)


def build_analytics_database(source: Path, output: Path, *, replace: bool = False) -> dict[str, object]:
    source, output = source.resolve(), output.resolve()
    validate_upstream_database(source)
    if output.exists() and not replace:
        raise FileExistsError(f"analytics database already exists: {output}; pass --replace")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.{uuid4().hex}.building"
    source_sha256 = sha256(source)
    release_id, manifest_sha256 = manifest_identity(source)
    build_identity = hashlib.sha256(
        f"{ANALYTICS_SCHEMA_VERSION}:{source_sha256}:{manifest_sha256}".encode()
    ).hexdigest()
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(str(temporary))
        quoted_source = str(source).replace("'", "''")
        connection.execute(f"ATTACH '{quoted_source}' AS canonical (READ_ONLY)")
        for name, contract in MART_CONTRACTS.items():
            connection.execute((SQL_DIRECTORY / contract.sql_file).read_text(encoding="utf-8"))
            key_sql = ", ".join(contract.key)
            null_rule = " OR ".join(f"{column} IS NULL" for column in contract.key)
            null_count = connection.execute(f"SELECT count(*) FROM {name} WHERE {null_rule}").fetchone()[0]
            if null_count:
                raise AnalyticsBuildError(f"table={name}; key={','.join(contract.key)}; rule=KEY_NOT_NULL; observed={null_count}")
            invalid = connection.execute(
                f"SELECT count(*) FROM (SELECT {key_sql} FROM {name} GROUP BY ALL HAVING count(*) > 1)"
            ).fetchone()[0]
            if invalid:
                raise AnalyticsBuildError(f"table={name}; key={','.join(contract.key)}; rule=KEY_UNIQUE; observed={invalid}")
        _create_catalogs(connection)
        connection.execute("""
            CREATE TABLE analytics_build_metadata (
              build_id VARCHAR PRIMARY KEY, analytics_schema_version INTEGER NOT NULL,
              source_database_name VARCHAR NOT NULL, source_database_sha256 VARCHAR NOT NULL,
              canonical_snapshot_id VARCHAR, source_manifest_sha256 VARCHAR,
              canonical_access_mode VARCHAR NOT NULL
            )
        """)
        connection.execute(
            "INSERT INTO analytics_build_metadata VALUES (?, ?, ?, ?, ?, ?, 'READ_ONLY')",
            [build_identity, ANALYTICS_SCHEMA_VERSION, source.name, source_sha256, release_id, manifest_sha256],
        )
        connection.execute("DETACH canonical")
        connection.execute("CHECKPOINT")
        connection.close()
        connection = None
        report = validate_analytics_database(temporary)
        if report["status"] != "PASS":
            raise AnalyticsBuildError(f"analytics validation failed: {report['failures']}")
        if sha256(source) != source_sha256:
            raise AnalyticsBuildError("canonical source SHA-256 changed during the read-only build")
        os.replace(temporary, output)
    finally:
        if connection is not None:
            connection.close()
        if temporary.exists():
            temporary.unlink()
    return {
        "status": "BUILT", "database": str(output), "build_id": build_identity,
        "source_database_sha256": source_sha256, "source_manifest_sha256": manifest_sha256,
        "marts": list(MART_CONTRACTS),
    }
