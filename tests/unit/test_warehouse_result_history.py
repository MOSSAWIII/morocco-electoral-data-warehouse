from __future__ import annotations

from pathlib import Path

import duckdb

from morocco_elections.warehouse.result_history import build_result_history_diagnostic
from morocco_elections.warehouse.schema import ddl


def _history_connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    connection.execute(
        "CREATE TABLE dim_election (election_id VARCHAR, election_date DATE, "
        "official_results_date DATE, publication_date DATE, retrieval_date DATE)"
    )
    connection.execute("INSERT INTO dim_election VALUES ('E', '2021-09-08', NULL, NULL, NULL)")
    connection.execute(
        "CREATE TABLE dim_electoral_contest (contest_id VARCHAR, election_id VARCHAR)"
    )
    connection.execute("INSERT INTO dim_electoral_contest VALUES ('C1', 'E'), ('C2', 'E')")
    for table in ("fact_election_result", "fact_communal_election_result", "fact_electoral_mobilization"):
        connection.execute(f'CREATE TABLE "{table}" (election_id VARCHAR, source_id VARCHAR)')
    connection.execute("INSERT INTO fact_election_result VALUES ('E', 'S')")
    connection.execute(ddl("fact_result_revision"))
    connection.execute(
        "INSERT INTO fact_result_revision "
        "(revision_id, result_id, contest_id, election_id, geo_id, geo_version_id, result_status, "
        "valid_from, source_id, published_at, known_at, verification_method, verification_status) "
        "VALUES ('R1', 'X1', 'C1', 'E', 'G1', 'GV1', 'PROCLAIMED', '2021-09-09', 'S', "
        "'2021-09-09', '2021-09-10', 'STRUCTURED_SOURCE_CLAIM', 'VERIFIED')"
    )
    return connection


def test_result_history_diagnostic_keeps_partial_election_blocking(tmp_path: Path) -> None:
    connection = _history_connection()
    try:
        report = build_result_history_diagnostic(connection, tmp_path, "2026-09-21")
    finally:
        connection.close()

    inventory = report["inventory"][0]
    assert inventory["history_or_rectification_available"] is True
    assert inventory["official_status_provable"] is False
    assert inventory["source_declared_result_statuses"] == ["PROCLAIMED"]
    assert inventory["result_revision_count"] == 1
    assert inventory["verified_history_contest_count"] == 1
    assert report["gaps"] == [{
        "scope_type": "ELECTION",
        "scope_id": "E",
        "contest_count": 2,
        "verified_history_contest_count": 1,
        "missing_history_contest_count": 1,
        "source_ids_searched": ["S"],
        "required_source": "Competent-authority result publication or decision with explicit status and dates",
        "availability_status": "PARTIAL_OFFICIAL_STATUS_HISTORY",
        "publication_consequence": (
            "1 contest result(s) remain unqualified; no unsupported "
            "FINAL/PROCLAIMED/RECTIFIED/ANNULLED status may be published"
        ),
        "blocking_code": "OFFICIAL_RESULT_STATUS_NOT_PROVEN",
    }]


def test_result_history_diagnostic_clears_gap_only_after_every_contest_is_verified(tmp_path: Path) -> None:
    connection = _history_connection()
    try:
        connection.execute(
            "INSERT INTO fact_result_revision "
            "(revision_id, result_id, contest_id, election_id, geo_id, geo_version_id, result_status, "
            "valid_from, source_id, published_at, known_at, verification_method, verification_status) "
            "VALUES ('R2', 'X2', 'C2', 'E', 'G2', 'GV2', 'PROCLAIMED', '2021-09-09', 'S', "
            "'2021-09-09', '2021-09-10', 'STRUCTURED_SOURCE_CLAIM', 'VERIFIED')"
        )
        report = build_result_history_diagnostic(connection, tmp_path, "2026-09-21")
    finally:
        connection.close()

    inventory = report["inventory"][0]
    assert inventory["official_status_provable"] is True
    assert inventory["additional_official_source_required"] is False
    assert inventory["verified_history_contest_count"] == 2
    assert report["gaps"] == []
