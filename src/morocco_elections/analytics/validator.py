from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.analytics.column_contracts import COLUMN_CONTRACTS
from morocco_elections.analytics.contracts import IDENTITY_STATUSES, MART_CONTRACTS, METRIC_STATUSES


RATIO_COLUMNS = {
    "mart_contest_results": ("vote_share_ratio", "seat_share_ratio", "previous_vote_share_ratio"),
    "mart_contest_competitiveness": ("hhi", "victory_margin_ratio", "concentration_ratio"),
    "mart_party_performance": ("mean_vote_share_ratio",),
    "mart_geography_profile": ("mean_hhi", "mean_victory_margin_ratio"),
    "mart_parliamentary_activity": ("published_response_date_ratio",),
}


def _failure(table: str, key: str, rule: str, observed: object | None = None) -> dict[str, str]:
    item = {"table": table, "key": key, "rule": rule}
    if observed is not None:
        item["observed"] = str(observed)
    return item


def validate_connection(connection: duckdb.DuckDBPyConnection) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    for table, contract in MART_CONTRACTS.items():
        key = ",".join(contract.key)
        if table not in tables:
            failures.append(_failure(table, key, "TABLE_REQUIRED"))
            continue
        columns = {row[0] for row in connection.execute(f"DESCRIBE {table}").fetchall()}
        expected_columns = set(COLUMN_CONTRACTS[table])
        if columns != expected_columns:
            failures.append(_failure(table, key, "COLUMN_CONTRACT", sorted(columns ^ expected_columns)))
        key_sql = ", ".join(contract.key)
        null_rule = " OR ".join(f"{column} IS NULL" for column in contract.key)
        null_count = connection.execute(f"SELECT count(*) FROM {table} WHERE {null_rule}").fetchone()[0]
        if null_count:
            failures.append(_failure(table, key, "KEY_NOT_NULL", null_count))
        duplicate_count = connection.execute(
            f"SELECT count(*) FROM (SELECT {key_sql} FROM {table} GROUP BY ALL HAVING count(*) > 1)"
        ).fetchone()[0]
        if duplicate_count:
            failures.append(_failure(table, key, "KEY_UNIQUE", duplicate_count))
        for column in RATIO_COLUMNS[table]:
            invalid = connection.execute(
                f"SELECT count(*) FROM {table} WHERE {column} IS NOT NULL AND ({column} < 0 OR {column} > 1)"
            ).fetchone()[0]
            if invalid:
                failures.append(_failure(table, key, f"RATIO_0_1:{column}", invalid))
        metric_status_columns = sorted(
            name for name in columns if name == "metric_status" or name.endswith("_metric_status")
        )
        for status_column in metric_status_columns:
            placeholders = ",".join("?" for _ in METRIC_STATUSES)
            invalid_statuses = connection.execute(
                f"SELECT count(*) FROM {table} WHERE {status_column} IS NULL "
                f"OR {status_column} NOT IN ({placeholders})",
                sorted(METRIC_STATUSES),
            ).fetchone()[0]
            if invalid_statuses:
                failures.append(_failure(
                    table, key, f"METRIC_STATUS_VOCABULARY:{status_column}", invalid_statuses,
                ))
            reason_column = f"{status_column}_reason"
            unexplained = connection.execute(
                f"SELECT count(*) FROM {table} WHERE {status_column} IN ('LIMITED', 'NOT_AVAILABLE') "
                f"AND nullif(trim({reason_column}), '') IS NULL"
            ).fetchone()[0]
            if unexplained:
                failures.append(_failure(
                    table, key, f"LIMITATION_REASON_REQUIRED:{status_column}", unexplained,
                ))
        for column in sorted(name for name in columns if name == "identity_status" or name.endswith("_identity_status")):
            identity_placeholders = ",".join("?" for _ in IDENTITY_STATUSES)
            invalid_identities = connection.execute(
                f"SELECT count(*) FROM {table} WHERE {column} IS NULL OR {column} NOT IN ({identity_placeholders})",
                sorted(IDENTITY_STATUSES),
            ).fetchone()[0]
            if invalid_identities:
                failures.append(_failure(table, key, f"IDENTITY_STATUS_VOCABULARY:{column}", invalid_identities))
        if "longitudinal_compatibility_status" in columns:
            proven_without_evidence = connection.execute(
                f"SELECT count(*) FROM {table} WHERE longitudinal_compatibility_status <> 'UNKNOWN'"
            ).fetchone()[0]
            if proven_without_evidence:
                failures.append(_failure(table, key, "LONGITUDINAL_DEFAULT_UNKNOWN", proven_without_evidence))
        if "geography_longitudinal_compatibility_status" in columns:
            invalid_geo_compatibility = connection.execute(
                f"SELECT count(*) FROM {table} WHERE geography_longitudinal_compatibility_status "
                "NOT IN ('COMPATIBLE', 'NOT_COMPATIBLE')"
            ).fetchone()[0]
            if invalid_geo_compatibility:
                failures.append(_failure(
                    table, key, "GEOGRAPHY_LONGITUDINAL_COMPATIBILITY_VOCABULARY", invalid_geo_compatibility,
                ))

    required_catalogs = {"analytics_table_catalog", "analytics_column_catalog", "analytics_join_contracts", "analytics_build_metadata"}
    for table in sorted(required_catalogs - tables):
        failures.append(_failure(table, "*", "TABLE_REQUIRED"))
    if required_catalogs <= tables:
        expected = sum(len(columns) for columns in COLUMN_CONTRACTS.values())
        actual = connection.execute("SELECT count(*) FROM analytics_column_catalog").fetchone()[0]
        if actual != expected:
            failures.append(_failure("analytics_column_catalog", "table_name,column_name", "COMPLETE", actual))
        invalid_catalog_rows = connection.execute("""
            SELECT count(*)
            FROM analytics_column_catalog c
            LEFT JOIN information_schema.columns i
              ON i.table_schema='main' AND i.table_name=c.table_name AND i.column_name=c.column_name
            WHERE i.column_name IS NULL OR i.data_type <> c.data_type
               OR nullif(trim(c.unit), '') IS NULL OR c.unit LIKE 'generic%'
               OR nullif(trim(c.meaning), '') IS NULL OR c.meaning = replace(c.column_name, '_', ' ')
               OR nullif(trim(c.calculation), '') IS NULL OR nullif(trim(c.source), '') IS NULL
        """).fetchone()[0]
        if invalid_catalog_rows:
            failures.append(_failure("analytics_column_catalog", "table_name,column_name", "EXPLICIT_COLUMN_CONTRACT", invalid_catalog_rows))
        join_contract_count = connection.execute("""
            SELECT count(*) FROM analytics_join_contracts
            WHERE left_table='mart_contest_results'
              AND right_table='mart_contest_competitiveness'
              AND join_keys='contest_id,election_id,ballot_type'
              AND cardinality='MANY_TO_ONE'
        """).fetchone()[0]
        if join_contract_count != 1:
            failures.append(_failure("analytics_join_contracts", "left_table,right_table,join_keys", "DECLARED_MANY_TO_ONE", join_contract_count))
        metadata_count = connection.execute(
            "SELECT count(*) FROM analytics_build_metadata WHERE canonical_access_mode='READ_ONLY' "
            "AND source_database_name NOT LIKE '%/%' AND source_database_name NOT LIKE '%\\\\%'"
        ).fetchone()[0]
        if metadata_count != 1:
            failures.append(_failure("analytics_build_metadata", "build_id", "READ_ONLY_PORTABLE_PROVENANCE", metadata_count))
        duplicate_join_targets = connection.execute("""
            SELECT count(*) FROM (
              SELECT contest_id, election_id, ballot_type
              FROM mart_contest_competitiveness GROUP BY ALL HAVING count(*) > 1
            )
        """).fetchone()[0]
        if duplicate_join_targets:
            failures.append(_failure(
                "mart_contest_competitiveness", "contest_id,election_id,ballot_type",
                "DECLARED_MANY_TO_ONE_JOIN_TARGET_UNIQUE", duplicate_join_targets,
            ))
    return failures


def validate_analytics_database(database: Path) -> dict[str, Any]:
    database = database.resolve()
    if not database.is_file():
        return {"status": "FAIL", "database": str(database), "failures": [_failure("analytics_database", "path", "DATABASE_REQUIRED")]}
    connection = duckdb.connect(str(database), read_only=True)
    try:
        failures = validate_connection(connection)
    finally:
        connection.close()
    return {"status": "PASS" if not failures else "FAIL", "database": str(database), "failures": failures}
