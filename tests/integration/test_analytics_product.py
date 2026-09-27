from __future__ import annotations

import hashlib
import os
from pathlib import Path

import duckdb
import pytest

from morocco_elections.analytics.builder import AnalyticsBuildError, build_analytics_database
from morocco_elections.analytics.acceptance import validate_acceptance_profile
from morocco_elections.analytics.contracts import MART_CONTRACTS
from morocco_elections.analytics.upstream_contract import UpstreamContractError, validate_upstream_database
from morocco_elections.analytics.validator import validate_analytics_database


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_logically_equal(first: Path, second: Path) -> None:
    connection = duckdb.connect()
    try:
        connection.execute(f"ATTACH '{first.as_posix()}' AS first (READ_ONLY)")
        connection.execute(f"ATTACH '{second.as_posix()}' AS second (READ_ONLY)")
        for table in MART_CONTRACTS:
            assert connection.execute(
                f"SELECT count(*) FROM ((SELECT * FROM first.{table}) EXCEPT ALL (SELECT * FROM second.{table}))"
            ).fetchone()[0] == 0
            assert connection.execute(
                f"SELECT count(*) FROM ((SELECT * FROM second.{table}) EXCEPT ALL (SELECT * FROM first.{table}))"
            ).fetchone()[0] == 0
    finally:
        connection.close()


def test_autonomous_build_is_read_only_complete_and_reproducible(canonical_database: Path, tmp_path: Path) -> None:
    before = sha256(canonical_database)
    first, second = tmp_path / "first.duckdb", tmp_path / "second.duckdb"
    first_report = build_analytics_database(canonical_database, first)
    second_report = build_analytics_database(canonical_database, second)
    assert sha256(canonical_database) == before
    assert first_report["build_id"] == second_report["build_id"]
    assert validate_analytics_database(first)["status"] == "PASS"
    assert_logically_equal(first, second)


def test_five_marts_and_six_demonstration_queries_execute(canonical_database: Path, tmp_path: Path) -> None:
    database = tmp_path / "analytics.duckdb"
    build_analytics_database(canonical_database, database)
    connection = duckdb.connect(str(database), read_only=True)
    try:
        assert set(MART_CONTRACTS) <= {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        queries = sorted((ROOT / "examples/analytics").glob("*.sql"))
        assert len(queries) == 6
        for query in queries:
            connection.execute(query.read_text(encoding="utf-8")).fetchall()
        assert connection.execute(
            "SELECT count(*) FROM mart_contest_results WHERE distribution_status='SOURCE_INTERNAL_COMPLETE'"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_structural_validator_rejects_key_ratio_status_and_reason_mutations(canonical_database: Path, tmp_path: Path) -> None:
    database = tmp_path / "analytics.duckdb"
    build_analytics_database(canonical_database, database)
    connection = duckdb.connect(str(database))
    try:
        connection.execute("INSERT INTO mart_contest_competitiveness SELECT * FROM mart_contest_competitiveness LIMIT 1")
        connection.execute(
            "UPDATE mart_contest_results SET vote_share_ratio=1.5, metric_status='LIMITED', metric_status_reason=NULL "
            "WHERE analytical_result_id='r1'"
        )
    finally:
        connection.close()
    rules = {item["rule"] for item in validate_analytics_database(database)["failures"]}
    assert "KEY_UNIQUE" in rules
    assert "RATIO_0_1:vote_share_ratio" in rules
    assert "LIMITATION_REASON_REQUIRED" in rules


def test_upstream_contract_rejects_undeclared_many_to_many(canonical_database: Path) -> None:
    connection = duckdb.connect(str(canonical_database))
    try:
        connection.execute("INSERT INTO analytics_contest_metrics SELECT * FROM analytics_contest_metrics LIMIT 1")
    finally:
        connection.close()
    with pytest.raises(UpstreamContractError, match=r"relation=analytics_contest_metrics.*rule=KEY_UNIQUE"):
        validate_upstream_database(canonical_database)


def test_failed_build_preserves_valid_destination_and_cleans_temporary_files(canonical_database: Path, tmp_path: Path) -> None:
    output = tmp_path / "analytics.duckdb"
    build_analytics_database(canonical_database, output)
    before = sha256(output)
    connection = duckdb.connect(str(canonical_database))
    try:
        connection.execute("UPDATE analytics_party_results SET vote_share_ratio=2 WHERE analytical_result_id='r1'")
    finally:
        connection.close()
    with pytest.raises(AnalyticsBuildError):
        build_analytics_database(canonical_database, output, replace=True)
    assert sha256(output) == before
    assert not list(tmp_path.glob("*.building"))


@pytest.mark.skipif(not os.environ.get("MOROCCO_ELECTIONS_CANONICAL_DB"), reason="real canonical snapshot not supplied")
def test_optional_real_snapshot(tmp_path: Path) -> None:
    source = Path(os.environ["MOROCCO_ELECTIONS_CANONICAL_DB"])
    before = sha256(source)
    output, second = tmp_path / "real-analytics.duckdb", tmp_path / "real-analytics-second.duckdb"
    build_analytics_database(source, output)
    build_analytics_database(source, second)
    assert sha256(source) == before
    assert validate_analytics_database(output)["status"] == "PASS"
    assert validate_acceptance_profile(output)["status"] == "PASS"
    assert_logically_equal(output, second)
    connection = duckdb.connect(str(output), read_only=True)
    try:
        for query in sorted((ROOT / "examples/analytics").glob("*.sql")):
            connection.execute(query.read_text(encoding="utf-8")).fetchall()
    finally:
        connection.close()
