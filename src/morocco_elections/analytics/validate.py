from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.analytics.build import MART_SPECS


RATIO_COLUMNS = {
    "mart_contest_results": ("vote_share_ratio", "seat_share_ratio", "previous_vote_share_ratio"),
    "mart_contest_competitiveness": ("hhi", "victory_margin_ratio", "concentration_ratio"),
    "mart_party_performance": ("mean_vote_share_ratio",),
    "mart_geography_profile": ("mean_hhi", "mean_victory_margin_ratio"),
    "mart_parliamentary_activity": ("published_response_date_ratio",),
}


def validate_analytics_database(database: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    if not database.is_file():
        return {
            "status": "FAIL", "database": str(database.resolve()),
            "failures": [{"table": "analytics_database", "key": "path", "rule": "DATABASE_REQUIRED"}],
        }
    connection = duckdb.connect(str(database.resolve()), read_only=True)
    try:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        for table, (_, keys) in MART_SPECS.items():
            if table not in tables:
                failures.append({"table": table, "key": ",".join(keys), "rule": "TABLE_REQUIRED"})
                continue
            key_sql = ", ".join(keys)
            null_rule = " OR ".join(f"{key} IS NULL" for key in keys)
            if connection.execute(f"SELECT count(*) FROM {table} WHERE {null_rule}").fetchone()[0]:
                failures.append({"table": table, "key": key_sql, "rule": "KEY_NOT_NULL"})
            total = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            distinct = connection.execute(f"SELECT count(*) FROM (SELECT DISTINCT {key_sql} FROM {table})").fetchone()[0]
            if total != distinct:
                failures.append({"table": table, "key": key_sql, "rule": "KEY_UNIQUE"})
            for column in RATIO_COLUMNS[table]:
                invalid = connection.execute(
                    f"SELECT count(*) FROM {table} WHERE {column} IS NOT NULL AND ({column} < 0 OR {column} > 1)"
                ).fetchone()[0]
                if invalid:
                    failures.append({"table": table, "key": key_sql, "rule": f"RATIO_0_1:{column}"})
            unexplained = connection.execute(
                f"SELECT count(*) FROM {table} WHERE metric_status IN ('LIMITED', 'NOT_AVAILABLE') "
                "AND metric_status_reason IS NULL"
            ).fetchone()[0]
            if unexplained:
                failures.append({"table": table, "key": key_sql, "rule": "LIMITATION_REASON_REQUIRED"})
        if "mart_contest_results" in tables:
            count = connection.execute("SELECT count(*) FROM mart_contest_results").fetchone()[0]
            if count != 32937:
                failures.append({"table": "mart_contest_results", "key": "analytical_result_id", "rule": "EXPECTED_32937_RESULTS"})
        if "mart_contest_competitiveness" in tables:
            count = connection.execute(
                "SELECT count(*) FROM mart_contest_competitiveness WHERE metric_status='AVAILABLE'"
            ).fetchone()[0]
            if count != 3073:
                failures.append({"table": "mart_contest_competitiveness", "key": "contest_id", "rule": "EXPECTED_3073_ADMISSIBLE"})
        metadata = connection.execute("SELECT count(*) FROM analytics_build_metadata WHERE canonical_access_mode='READ_ONLY'").fetchone()[0]
        if metadata != 1:
            failures.append({"table": "analytics_build_metadata", "key": "build_id", "rule": "READ_ONLY_PROVENANCE_REQUIRED"})
        duplicate_join_targets = connection.execute("""
            SELECT count(*) FROM (
              SELECT contest_id, election_id, ballot_type
              FROM mart_contest_competitiveness
              GROUP BY ALL HAVING count(*) > 1
            )
        """).fetchone()[0]
        if duplicate_join_targets:
            failures.append({
                "table": "mart_contest_competitiveness", "key": "contest_id,election_id,ballot_type",
                "rule": "DECLARED_MANY_TO_ONE_JOIN_TARGET_UNIQUE",
            })
    finally:
        connection.close()
    return {"status": "PASS" if not failures else "FAIL", "database": str(database.resolve()), "failures": failures}
