from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import duckdb
import pytest

from morocco_elections.warehouse.publication import PublicationContext, _metrics, sha256_file
from morocco_elections.warehouse.reconciliation import (
    RECONCILIATION_CHECKS,
    _verified_manifest_sources,
    derive_reconciliation_matrix,
)


ROOT = Path(__file__).resolve().parents[2]
DATABASE = Path(os.environ.get("WAREHOUSE_TEST_PACKAGE", ROOT / "data/exports/open/warehouse")) / "morocco_elections.duckdb"
pytestmark = pytest.mark.skipif(not DATABASE.is_file(), reason="local canonical package required")


def _rows(database: Path, table: str) -> list[dict]:
    connection = duckdb.connect(str(database), read_only=True)
    try:
        cursor = connection.execute(f'SELECT * FROM "{table}"')
        fields = [item[0] for item in cursor.description]
        return [dict(zip(fields, values, strict=True)) for values in cursor.fetchall()]
    finally:
        connection.close()


def _context(database: Path, rows: list[dict]) -> PublicationContext:
    return PublicationContext(
        release_id="TEST-SNAPSHOT",
        as_of_date="2026-09-21",
        files=[{"relative_path": database.name, "sha256": sha256_file(database)}],
        coverage_matrix=[],
        datasets={"reconciliations": rows},
        checks={},
        package_root=database.parent,
        package_database_path=database.name,
        evidence_root=ROOT,
    )


def test_complete_reconciliation_matrix_is_honest_and_exhaustive() -> None:
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        expected, report = derive_reconciliation_matrix(connection, ROOT)
    finally:
        connection.close()
    materialized = _rows(DATABASE, "fact_result_reconciliation")
    assert materialized == expected
    assert report["covered_contests"] == 3715
    assert report["expected_checks"] == report["produced_reconciliations"] == 14860
    assert report["status_distribution"] == {"NOT_COMPUTABLE": 14860}
    assert report["contests_without_status"] == report["duplicate_statuses"] == 0
    assert report["official_values_without_source"] == 0
    assert report["non_reproducible_recomputed_values"] == report["unresolved_differences"] == 0
    assert report["mobilization_field_coverage"] == {
        "registered_voters": 187, "voters": 0, "valid_votes": 82, "invalid_votes": 0,
        "blank_votes": 0, "turnout_rate": 639, "contest_seats": 547,
    }
    assert report["combined_aggregate_field_coverage"]["records"] == 3715
    assert report["combined_aggregate_field_coverage"]["turnout_rate"] == 3715
    assert report["external_universe_coverage"] == {
        "party_or_list_universes": 0, "seat_allocation_universes": 0,
    }
    assert all(row["detail_vs_aggregate_status"].startswith("NOT_APPLICABLE") for row in report["contest_type_matrix"])
    assert all(row["conditional_analytics_status"].startswith("NOT_APPLICABLE") for row in report["contest_type_matrix"])
    assert all(row["calculation_method"] and row["evidence_id"] and row["official_source_id"] for row in materialized)
    assert all(row["recomputed_value"] is None for row in materialized)
    assert all(json.loads(row["missing_components"]) for row in materialized)
    assert {row["metric"] for row in materialized} == set(RECONCILIATION_CHECKS)
    assert _metrics(_context(DATABASE, materialized)).status == "PASS"


def test_reconciliation_matrix_mutations_fail_closed() -> None:
    rows = _rows(DATABASE, "fact_result_reconciliation")
    party_index = next(index for index, row in enumerate(rows) if row["metric"] == "party_votes_vs_valid_votes")
    missing_official_index = next(index for index, row in enumerate(rows) if row["official_value"] is None)
    mutations: list[list[dict]] = []
    mutations.append(copy.deepcopy(rows[1:]))  # deleted status and omitted contest/check pair
    duplicate = copy.deepcopy(rows)
    duplicate.append(copy.deepcopy(duplicate[0]))
    mutations.append(duplicate)
    for field, value in (
        ("official_value", 1),
        ("recomputed_value", 1),
        ("tolerance", 1),
        ("source_id", "MUTATED"),
        ("not_computable_reason", "UNSUPPORTED_METRIC"),
    ):
        mutation = copy.deepcopy(rows)
        mutation[party_index][field] = value
        mutations.append(mutation)
    missing_to_zero = copy.deepcopy(rows)
    missing_to_zero[missing_official_index]["official_value"] = 0
    mutations.append(missing_to_zero)
    false_pass = copy.deepcopy(rows)
    false_pass[party_index].update({
        "validation_status": "PASS", "recomputed_value": false_pass[party_index]["official_value"],
        "difference": 0.0, "not_computable_reason": None, "explanation": None,
    })
    mutations.append(false_pass)
    self_referential = copy.deepcopy(false_pass)
    self_referential[party_index]["external_universe_id"] = "OBSERVED_ROWS_AS_UNIVERSE"
    mutations.append(self_referential)
    non_applicable = copy.deepcopy(rows)
    non_applicable.append({
        **copy.deepcopy(rows[0]),
        "reconciliation_id": f"{rows[0]['contest_id']}:hhi",
        "metric": "hhi",
    })
    mutations.append(non_applicable)
    omitted_contest = [row for row in copy.deepcopy(rows) if row["contest_id"] != rows[0]["contest_id"]]
    mutations.append(omitted_contest)
    for mutation in mutations:
        assert _metrics(_context(DATABASE, mutation)).status == "FAIL"


def test_gate_rereads_duckdb_and_rejects_coordinated_table_context_mutation(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    shutil.copy2(DATABASE, database)
    connection = duckdb.connect(str(database))
    try:
        relation_id = connection.execute(
            "SELECT reconciliation_id FROM fact_result_reconciliation ORDER BY reconciliation_id LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            "UPDATE fact_result_reconciliation SET official_value=0 WHERE reconciliation_id=?",
            [relation_id],
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    coordinated_rows = _rows(database, "fact_result_reconciliation")
    gate = _metrics(_context(database, coordinated_rows))
    assert gate.status == "FAIL"
    assert relation_id in gate.affected_records
    assert "source-derived reconciliation" in gate.justification


def test_reconciliation_source_hash_mutation_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"pinned")
    metadata = tmp_path / "metadata/warehouse"
    metadata.mkdir(parents=True)
    (metadata / "source_registry.json").write_text(json.dumps({"sources": [{
        "source_id": "S", "aliases": [], "raw_path": "source.bin", "bytes": 6,
        "sha256": hashlib.sha256(b"pinned").hexdigest(),
    }]}), encoding="utf-8")
    assert _verified_manifest_sources(tmp_path, {"S"})["S"]["source_id"] == "S"
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source bytes differ"):
        _verified_manifest_sources(tmp_path, {"S"})
