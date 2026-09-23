from __future__ import annotations

from pathlib import Path

import pytest

from morocco_elections.warehouse.contracts import PROPOSED_TABLE_CONTRACTS, TABLE_CONTRACTS, VOCABULARIES
from morocco_elections.warehouse.build import _normalize_seed_identifiers, build_development_database
from morocco_elections.warehouse.coverage import DIMENSIONS, UNKNOWN, coverage_report, validate_universes
from morocco_elections.warehouse.history import validate_result_geographies
from morocco_elections.warehouse.schema import create_schema, schema_inventory
from morocco_elections.warehouse.validation import WarehouseValidationError, validate_or_raise, validate_rows, validate_semantic_consistency
from morocco_elections.warehouse.versions import applicable_revision, validate_revisions


def test_contract_separates_published_tables_from_schema_proposals() -> None:
    assert {
        "coverage_universe", "fact_result_reconciliation", "bridge_contest_legal_regime",
        "coverage_universe_member", "publication_gate_result",
        "dim_legal_regime", "bridge_election_legal_regime", "publication_file", "release_coverage_matrix",
    } <= TABLE_CONTRACTS.keys()
    assert {
        "dim_contest_type", "dim_seat_category", "fact_candidacy_list", "fact_candidate",
        "fact_seat_allocation", "dim_party_version", "bridge_party_lineage",
        "bridge_person_party_affiliation", "dim_geo_version", "bridge_geo_lineage",
        "fact_legal_decision", "fact_result_revision", "fact_metric_validation",
    } == PROPOSED_TABLE_CONTRACTS.keys()
    assert TABLE_CONTRACTS.keys().isdisjoint(PROPOSED_TABLE_CONTRACTS)
    assert all(vocabulary.version == "1.0.0" and vocabulary.definitions for vocabulary in VOCABULARIES.values())


def test_all_contract_tables_materialize_with_database_constraints() -> None:
    import duckdb

    connection = duckdb.connect(":memory:")
    create_schema(connection)
    assert {row["table_name"] for row in schema_inventory(connection)} == set(TABLE_CONTRACTS)
    connection.close()


def test_warehouse_build_is_additive_and_refuses_overwrite(tmp_path: Path) -> None:
    import duckdb

    seed = tmp_path / "historical-seed.duckdb"
    connection = duckdb.connect(str(seed))
    connection.execute("CREATE TABLE dim_election(election_id VARCHAR PRIMARY KEY)")
    connection.execute("INSERT INTO dim_election VALUES ('E1')")
    connection.close()
    output = tmp_path / "warehouse.duckdb"
    report = build_development_database(seed, output)
    assert report["copied_historical_tables"] == 1
    assert report["created_canonical_tables"] == len(TABLE_CONTRACTS)
    connection = duckdb.connect(str(output), read_only=True)
    assert connection.execute("SELECT * FROM dim_election").fetchall() == [("E1",)]
    tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    assert tables >= set(TABLE_CONTRACTS)
    assert tables.isdisjoint(PROPOSED_TABLE_CONTRACTS)
    connection.close()
    with pytest.raises(FileExistsError):
        build_development_database(seed, output)


def test_seed_identifier_normalization_is_release_agnostic() -> None:
    import duckdb

    connection = duckdb.connect(":memory:")
    connection.execute("CREATE TABLE parent (entity_id VARCHAR PRIMARY KEY)")
    connection.execute("CREATE TABLE child (child_id VARCHAR, entity_id VARCHAR)")
    connection.execute("INSERT INTO parent VALUES ('ENTITY_V27_3_A')")
    connection.execute("INSERT INTO child VALUES ('CHILD_V27_B', 'ENTITY_V27_3_A')")

    changed = _normalize_seed_identifiers(connection)

    assert changed == 3
    assert connection.execute("SELECT * FROM parent").fetchall() == [("ENTITY_A",)]
    assert connection.execute("SELECT * FROM child").fetchall() == [("CHILD_B", "ENTITY_A")]
    connection.close()


def test_semantic_mutations_produce_all_explicit_errors() -> None:
    contests = [{"contest_id": "C1", "election_id": "E1", "geo_id": "G1", "region_geo_id": "R1"}]
    elections = [{"election_id": "E1", "election_date": "2021-09-08"}]
    geos = [{"geo_id": "G1", "parent_geo_id": "R1"}]
    good = [{"result_id": "X", "contest_id": "C1", "election_id": "E1", "geo_id": "G1", "year": 2021}]
    assert validate_semantic_consistency(good, contests, elections, geos) == []
    bad = [{"result_id": "X", "contest_id": "C1", "election_id": "E2", "geo_id": "G2", "year": 2015}]
    codes = {issue.code for issue in validate_semantic_consistency(bad, contests, elections, geos)}
    assert {"FACT_CONTEST_ELECTION_MISMATCH", "FACT_CONTEST_GEO_MISMATCH", "UNKNOWN_ELECTION", "UNKNOWN_GEOGRAPHY"} <= codes
    wrong_year = [{**good[0], "year": 2015}]
    assert "FACT_ELECTION_YEAR_MISMATCH" in {i.code for i in validate_semantic_consistency(wrong_year, contests, elections, geos)}
    wrong_parent = [{"geo_id": "G1", "parent_geo_id": "R2"}]
    assert "REGIONAL_PARENT_MISMATCH" in {i.code for i in validate_semantic_consistency(good, contests, elections, wrong_parent)}


def test_errors_are_raiseable_and_vocabulary_is_closed() -> None:
    issues = validate_rows("fact_result_revision", [{"revision_id": "R", "result_status": "MADE_UP"}])
    assert {"REQUIRED_FIELD_MISSING", "CONTROLLED_VOCABULARY_VIOLATION"} <= {issue.code for issue in issues}
    try:
        validate_or_raise(issues)
    except WarehouseValidationError as exc:
        assert "CONTROLLED_VOCABULARY_VIOLATION" in str(exc)
    else:
        raise AssertionError("explicit validation error expected")


def _universe(dimension: str, denominator: int = 1) -> dict:
    return {
        "universe_id": f"U-{dimension}", "election_id": "E1", "coverage_dimension": dimension,
        "universe_type": "OFFICIAL_RECORDS", "denominator": denominator, "source_id": "S1",
        "source_url": "https://official.example/universe", "acquired_at": "2026-09-14",
        "verification_status": "VERIFIED", "is_external": True,
        "member_extraction_method": "JSON_UNIVERSES_OBJECT",
    }


def test_six_coverages_are_separate_and_unknown_without_official_denominator() -> None:
    observations = [{"coverage_dimension": "ACQUIRED", "observation_id": "A"}, {"coverage_dimension": "OFFICIAL", "observation_id": "C1"}]
    members = [{"universe_id": "U-OFFICIAL", "expected_id": "C1", "source_id": "S1"}]
    result = coverage_report(observations, [_universe("OFFICIAL")], members)
    assert tuple(row["coverage_dimension"] for row in result) == DIMENSIONS
    assert next(row for row in result if row["coverage_dimension"] == "OFFICIAL")["status"] == "COMPLETE"
    assert next(row for row in result if row["coverage_dimension"] == "TERRITORIAL")["status"] == UNKNOWN


def test_self_referential_or_unverified_universe_cannot_claim_completeness() -> None:
    bad = {**_universe("OFFICIAL"), "is_external": False}
    assert "SELF_REFERENTIAL_UNIVERSE_FORBIDDEN" in {issue.code for issue in validate_universes([bad])}
    observations = [{"coverage_dimension": "OFFICIAL", "observation_id": "C1"}]
    members = [{"universe_id": "U-OFFICIAL", "expected_id": "C1", "source_id": "S1"}]
    assert coverage_report(observations, [bad], members)[1]["status"] == UNKNOWN


def test_equal_counts_with_different_identifiers_are_never_complete() -> None:
    observations = [{"coverage_dimension": "OFFICIAL", "contest_id": "UNEXPECTED"}]
    members = [{"universe_id": "U-OFFICIAL", "expected_id": "EXPECTED", "source_id": "S1"}]
    report = coverage_report(observations, [_universe("OFFICIAL")], members)[1]
    assert report["status"] == "PARTIAL"
    assert report["covered_ids"] == []
    assert report["missing_ids"] == ["EXPECTED"]
    assert report["unexpected_ids"] == ["UNEXPECTED"]


def test_non_comparable_and_unidentified_observations_are_classified() -> None:
    observations = [
        {"coverage_dimension": "OFFICIAL", "contest_id": "C1", "comparability_status": "NOT_COMPARABLE"},
        {"coverage_dimension": "OFFICIAL"},
    ]
    members = [{"universe_id": "U-OFFICIAL", "expected_id": "C1", "source_id": "S1"}]
    report = coverage_report(observations, [_universe("OFFICIAL")], members)[1]
    assert report["status"] == "EMPTY"
    assert report["non_comparable_ids"] == ["C1"]
    assert report["unidentified_observations"] == 1


def test_coverage_dispositions_are_mutually_exclusive() -> None:
    observations = [
        {"coverage_dimension": "OFFICIAL", "contest_id": "COVERED"},
        {"coverage_dimension": "OFFICIAL", "contest_id": "FORBIDDEN", "redistribution_forbidden": True},
        {"coverage_dimension": "OFFICIAL", "contest_id": "NONCOMP", "comparability_status": "NOT_COMPARABLE"},
        {"coverage_dimension": "OFFICIAL", "contest_id": "EXTRA", "redistribution_forbidden": True},
    ]
    members = [
        {"universe_id": "U-OFFICIAL", "expected_id": expected_id, "source_id": "S1"}
        for expected_id in ("COVERED", "FORBIDDEN", "NONCOMP", "MISSING")
    ]
    report = coverage_report(observations, [_universe("OFFICIAL", denominator=4)], members)[1]
    assert report["covered_ids"] == ["COVERED"]
    assert report["redistribution_forbidden_ids"] == ["FORBIDDEN"]
    assert report["non_comparable_ids"] == ["NONCOMP"]
    assert report["missing_ids"] == ["MISSING"]
    assert report["unexpected_ids"] == ["EXTRA"]


def test_coverage_universes_are_scoped_by_election_without_identifier_collisions() -> None:
    first = _universe("OFFICIAL")
    second = {**first, "universe_id": "U2-OFFICIAL", "election_id": "E2"}
    members = [
        {"universe_id": "U-OFFICIAL", "expected_id": "SAME", "source_id": "S1"},
        {"universe_id": "U2-OFFICIAL", "expected_id": "SAME", "source_id": "S1"},
    ]
    observations = [
        {"coverage_dimension": "OFFICIAL", "election_id": "E1", "observation_id": "SAME"},
        {"coverage_dimension": "OFFICIAL", "election_id": "E2", "observation_id": "SAME"},
    ]
    report = coverage_report(observations, [first, second], members)[1]
    assert report["status"] == "COMPLETE"
    assert report["denominator"] == 2
    assert report["covered_ids"] == ["E1::SAME", "E2::SAME"]
    ambiguous = coverage_report([{"coverage_dimension": "OFFICIAL", "observation_id": "SAME"}], [first, second], members)[1]
    assert ambiguous["status"] == "EMPTY"
    assert ambiguous["unidentified_observations"] == 1
    duplicate = {**second, "election_id": "E1"}
    assert "DUPLICATE_UNIVERSE_SCOPE" in {issue.code for issue in validate_universes([first, duplicate])}


def test_result_versions_are_retained_and_selected_deterministically() -> None:
    rows = [
        {"revision_id": "R1", "result_id": "X", "contest_id": "C", "election_id": "E", "geo_id": "G", "geo_version_id": "GV", "result_status": "FINAL", "valid_from": "2021-09-10", "valid_to": "2022-01-01", "source_id": "S1", "published_at": "2021-09-10", "known_at": "2021-09-10", "verification_method": "STRUCTURED_SOURCE_CLAIM", "verification_status": "VERIFIED"},
        {"revision_id": "R2", "result_id": "X", "contest_id": "C", "election_id": "E", "geo_id": "G", "geo_version_id": "GV", "result_status": "RECTIFIED", "valid_from": "2022-01-02", "source_id": "S2", "published_at": "2022-01-03", "known_at": "2022-01-03", "verification_method": "STRUCTURED_SOURCE_CLAIM", "verification_status": "VERIFIED", "supersedes_revision_id": "R1", "decision_id": "D1"},
    ]
    assert validate_revisions(rows) == []
    assert applicable_revision(rows, "X", "2021-12-01")["revision_id"] == "R1"
    assert applicable_revision(rows, "X", "2022-02-01")["revision_id"] == "R2"
    assert len(rows) == 2


def test_revision_chain_rejects_open_or_overlapping_predecessor_validity() -> None:
    base = {"revision_id": "R1", "result_id": "X", "contest_id": "C", "election_id": "E", "geo_id": "G", "geo_version_id": "GV", "result_status": "FINAL", "valid_from": "2021-09-10", "source_id": "S", "published_at": "2021-09-10", "known_at": "2021-09-10"}
    child = {**base, "revision_id": "R2", "result_status": "RECTIFIED", "valid_from": "2021-09-12", "published_at": "2021-09-12", "known_at": "2021-09-12", "supersedes_revision_id": "R1", "decision_id": "D"}
    assert "SUPERSEDED_REVISION_STILL_OPEN" in {issue.code for issue in validate_revisions([base, child])}
    overlapping = [{**base, "valid_to": "2021-09-12"}, child]
    assert "OVERLAPPING_RESULT_REVISIONS" in {issue.code for issue in validate_revisions(overlapping)}


def test_revision_chain_rejects_two_simultaneously_applicable_roots() -> None:
    base = {
        "result_id": "X", "contest_id": "C", "election_id": "E", "geo_id": "G",
        "geo_version_id": "GV", "result_status": "PROVISIONAL", "valid_from": "2021-09-10",
        "source_id": "S", "known_at": "2021-09-11",
        "verification_method": "STRUCTURED_SOURCE_CLAIM", "verification_status": "VERIFIED",
    }
    rows = [{**base, "revision_id": "R1"}, {**base, "revision_id": "R2"}]
    codes = {issue.code for issue in validate_revisions(rows)}
    assert {"MULTIPLE_REVISION_ROOTS", "OVERLAPPING_RESULT_REVISIONS"} <= codes


def test_annulment_requires_retained_predecessor_and_decision() -> None:
    row = {"revision_id": "R2", "result_id": "X", "contest_id": "C", "election_id": "E", "geo_id": "G", "geo_version_id": "GV", "result_status": "ANNULLED", "valid_from": "2022-01-02", "source_id": "S", "published_at": "2022-01-03", "known_at": "2022-01-03"}
    assert {"MISSING_SUPERSEDED_REVISION", "ANNULMENT_DECISION_REQUIRED"} <= {i.code for i in validate_revisions([row])}


def test_rectification_requires_retained_predecessor() -> None:
    row = {
        "revision_id": "R2", "result_id": "X", "contest_id": "C", "election_id": "E",
        "geo_id": "G", "geo_version_id": "GV", "result_status": "RECTIFIED",
        "valid_from": "2022-01-02", "source_id": "S", "known_at": "2022-01-03",
        "verification_method": "STRUCTURED_SOURCE_CLAIM", "verification_status": "VERIFIED",
    }
    assert "MISSING_SUPERSEDED_REVISION" in {issue.code for issue in validate_revisions([row])}


def test_revision_chains_reject_cycles_cross_result_links_and_forbidden_transitions() -> None:
    base = {"contest_id": "C", "election_id": "E", "geo_id": "G", "geo_version_id": "GV", "valid_from": "2021-09-10", "source_id": "S", "published_at": "2021-09-10", "known_at": "2021-09-10"}
    rows = [
        {**base, "revision_id": "R1", "result_id": "X", "result_status": "FINAL", "supersedes_revision_id": "R2"},
        {**base, "revision_id": "R2", "result_id": "X", "result_status": "POLL_CLOSED", "supersedes_revision_id": "R1"},
    ]
    codes = {issue.code for issue in validate_revisions(rows)}
    assert {"CYCLIC_REVISION_CHAIN", "INVALID_RESULT_STATUS_TRANSITION"} <= codes
    cross_result = [
        {**base, "revision_id": "R1", "result_id": "X", "result_status": "PROVISIONAL"},
        {**base, "revision_id": "R2", "result_id": "Y", "result_status": "FINAL", "supersedes_revision_id": "R1"},
    ]
    assert "CROSS_RESULT_REVISION_CHAIN" in {issue.code for issue in validate_revisions(cross_result)}


def test_applicable_revision_excludes_future_publication_or_knowledge() -> None:
    rows = [
        {"revision_id": "R1", "result_id": "X", "contest_id": "C", "election_id": "E", "geo_id": "G", "geo_version_id": "GV", "result_status": "FINAL", "valid_from": "2021-09-10", "source_id": "S", "published_at": "2021-09-10", "known_at": "2021-09-10"},
        {"revision_id": "R2", "result_id": "X", "contest_id": "C", "election_id": "E", "geo_id": "G", "geo_version_id": "GV", "result_status": "RECTIFIED", "valid_from": "2021-09-10", "source_id": "S", "published_at": "2022-01-01", "known_at": "2022-01-02", "supersedes_revision_id": "R1", "decision_id": "D"},
    ]
    assert applicable_revision(rows, "X", "2021-12-31")["revision_id"] == "R1"
    assert applicable_revision(rows, "X", "2022-01-01")["revision_id"] == "R1"
    assert applicable_revision(rows, "X", "2022-01-02")["revision_id"] == "R2"


def test_result_geography_version_must_match_identity_and_election_date() -> None:
    revision = {"revision_id": "R", "election_id": "E", "geo_id": "G", "geo_version_id": "GV"}
    versions = [{"geo_version_id": "GV", "geo_id": "G", "valid_from": "2020-01-01", "valid_to": "2022-12-31"}]
    elections = [{"election_id": "E", "election_date": "2021-09-08"}]
    assert validate_result_geographies([revision], versions, elections) == []
    wrong_identity = [{**versions[0], "geo_id": "OTHER"}]
    assert "RESULT_GEO_VERSION_MISMATCH" in {issue.code for issue in validate_result_geographies([revision], wrong_identity, elections)}
    wrong_date = [{**versions[0], "valid_from": "2022-01-01"}]
    assert "GEO_VERSION_NOT_APPLICABLE" in {issue.code for issue in validate_result_geographies([revision], wrong_date, elections)}
