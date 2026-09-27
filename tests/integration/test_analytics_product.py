from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb

from morocco_elections.analytics.build import MART_SPECS, build_analytics_database
from morocco_elections.analytics.validate import validate_analytics_database


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data/exports/open/warehouse/morocco_elections.duckdb"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_analytics_build_is_read_only_complete_and_logically_reproducible(tmp_path: Path) -> None:
    before = _sha256(CANONICAL)
    first, second = tmp_path / "first.duckdb", tmp_path / "second.duckdb"
    first_report = build_analytics_database(CANONICAL, first)
    second_report = build_analytics_database(CANONICAL, second)

    assert _sha256(CANONICAL) == before
    assert first_report["build_id"] == second_report["build_id"]
    assert validate_analytics_database(first)["status"] == "PASS"
    connection = duckdb.connect()
    try:
        connection.execute(f"ATTACH '{first.as_posix()}' AS first (READ_ONLY)")
        connection.execute(f"ATTACH '{second.as_posix()}' AS second (READ_ONLY)")
        for table in MART_SPECS:
            assert connection.execute(
                f"SELECT count(*) FROM ((SELECT * FROM first.{table}) EXCEPT ALL (SELECT * FROM second.{table}))"
            ).fetchone()[0] == 0
            assert connection.execute(
                f"SELECT count(*) FROM ((SELECT * FROM second.{table}) EXCEPT ALL (SELECT * FROM first.{table}))"
            ).fetchone()[0] == 0
    finally:
        connection.close()


def test_analytics_marts_and_demonstration_queries_execute(tmp_path: Path) -> None:
    database = tmp_path / "analytics.duckdb"
    build_analytics_database(CANONICAL, database)
    connection = duckdb.connect(str(database), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM mart_contest_results").fetchone()[0] == 32937
        assert connection.execute(
            "SELECT count(*) FROM mart_contest_competitiveness WHERE metric_status='AVAILABLE'"
        ).fetchone()[0] == 3073
        assert connection.execute(
            "SELECT count(*) FROM mart_contest_results WHERE distribution_status='SOURCE_INTERNAL_COMPLETE'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM mart_contest_results WHERE longitudinal_compatibility_status <> 'UNKNOWN'"
        ).fetchone()[0] == 0
        for query in sorted((ROOT / "examples/analytics").glob("*.sql")):
            connection.execute(query.read_text(encoding="utf-8")).fetchall()
    finally:
        connection.close()


def test_validation_failure_names_table_key_and_rule(tmp_path: Path) -> None:
    database = tmp_path / "analytics.duckdb"
    build_analytics_database(CANONICAL, database)
    connection = duckdb.connect(str(database))
    try:
        connection.execute("INSERT INTO mart_contest_competitiveness SELECT * FROM mart_contest_competitiveness LIMIT 1")
    finally:
        connection.close()
    report = validate_analytics_database(database)
    assert report["status"] == "FAIL"
    assert {
        "table": "mart_contest_competitiveness",
        "key": "contest_id",
        "rule": "KEY_UNIQUE",
    } in report["failures"]
