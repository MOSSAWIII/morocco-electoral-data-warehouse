from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from morocco_elections.warehouse.audit import audit_historical_seed
from morocco_elections.warehouse.build import build_development_database
from morocco_elections.warehouse.coverage import coverage_report
from morocco_elections.warehouse.councils import derive_comm2015_council_candidates
from morocco_elections.warehouse.demography import load_hcp_rgph2014_arrondissement_identifiers, load_hcp_rgph2014_territorial_universe
from morocco_elections.warehouse.demography import load_hcp_rgph2014_individuals
from morocco_elections.warehouse.evidence import derive_contest_legal_regime_links, validate_official_source_registry
from morocco_elections.warehouse.package import _table_catalog
from morocco_elections.warehouse.publication import PublicationContext, _bind_contract_tables, _semantic_facts, _verify_demographic_source_rows, sha256_file
from morocco_elections.warehouse.semantic import TABLE_GRAINS, VIEW_SEMANTICS


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/seeds/historical/morocco_elections.duckdb"
pytestmark = pytest.mark.skipif(not DATABASE.is_file(), reason="local historical seed required")


def test_hcp_official_arrondissement_codes_match_all_historical_comm2015_units() -> None:
    workbook = ROOT / "data/raw/elections/warehouse/demography/hcp_rgph2014_population_legale_12_regions.xlsx"
    if not workbook.is_file():
        pytest.skip("official HCP workbook not acquired locally")
    rows = load_hcp_rgph2014_arrondissement_identifiers(
        workbook, source_id="MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS",
    )
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        observed = {
            row[0] for row in connection.execute(
                "SELECT g.geo_id FROM dim_electoral_contest c JOIN dim_geo g USING(geo_id) "
                "WHERE c.election_id='COMM2015' AND g.geo_type='arrondissement'"
            ).fetchall()
        }
    finally:
        connection.close()
    assert len(rows) == len(observed) == 41
    assert {row["geo_id"] for row in rows} == observed
    assert len({row["prefecture_code"] for row in rows}) == 6
    seed = json.loads((ROOT / "metadata/warehouse/comm2015_council_candidates.seed.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))["sources"]
    referenced = {seed[field] for field in ("legal_source_id", "annex_source_id", "code_source_id")}
    referenced.update(
        group["urban_commune_order_source_id"] for group in seed["groups"]
        if group.get("urban_commune_order_source_id")
    )
    assert validate_official_source_registry(ROOT, {"sources": [row for row in sources if row["source_id"] in referenced]}) == []
    candidates = derive_comm2015_council_candidates(rows, observed, seed)
    assert candidates["group_counts"] == {
        "01.511.": 4, "03.231.": 6, "04.421.": 5,
        "04.441.": 5, "06.141.": 16, "07.351.": 5,
    }
    assert candidates["publication_claim_allowed"] is False
    assert candidates["urban_commune_order_source_group_count"] == 3
    assert candidates["arrondissement_boundary_source_group_count"] == 0


def test_original_bo6304_is_pinned_but_does_not_justify_arrondissement_boundaries() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6304_URBAN_COMMUNE_BOUNDARY_ORDERS_2014")
    assert validate_official_source_registry(ROOT, {"sources": [source]}) == []
    assert source["public_package_disposition"] == "METADATA_ONLY"
    assert "ne prouvent pas à eux seuls les frontières des arrondissements" in source["notes"]


def test_pre_comm2021_bo6980_bis_is_pinned_without_claiming_final_geometry() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(
        row for row in registry["sources"]
        if row["source_id"] == "MA_SGG_BO_6980_BIS_TANGIER_MARRAKECH_BOUNDARY_ORDERS_2021"
    )
    assert validate_official_source_registry(ROOT, {"sources": [source]}) == []
    assert source["document_effective_as_of"] == "2021-04-22"
    assert source["public_package_disposition"] == "METADATA_ONLY"
    assert "quatre arrondissements" in source["notes"]
    assert "cinq arrondissements" in source["notes"]
    assert "géométries et date juridique d'effet à reconstituer" in source["notes"]


def test_pre_comm2015_bo6374_is_pinned_without_claiming_official_universe() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(
        row for row in registry["sources"]
        if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015"
    )
    assert validate_official_source_registry(ROOT, {"sources": [source]}) == []
    assert source["document_effective_as_of"] == "2015-07-02"
    assert source["public_package_disposition"] == "METADATA_ONLY"
    assert "6105-6136" in source["notes"]
    assert "ne doivent pas servir de dénominateur officiel avant extraction contrôlée" in source["notes"]


def test_official_hcp_territorial_identifiers_expose_partial_exact_code_coverage() -> None:
    workbook = ROOT / "data/raw/elections/warehouse/demography/hcp_rgph2014_population_legale_12_regions.xlsx"
    if not workbook.is_file():
        pytest.skip("official HCP workbook not acquired locally")
    universe, members = load_hcp_rgph2014_territorial_universe(
        workbook, election_id="COMM2015",
        source_id="MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS",
        source_url="https://www.hcp.ma/file/230057/", acquired_at="2026-09-14",
    )
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        observations = [
            {"election_id": "COMM2015", "coverage_dimension": "TERRITORIAL", "geo_id": row[0]}
            for row in connection.execute(
                "SELECT geo_id FROM dim_electoral_contest WHERE election_id='COMM2015'"
            ).fetchall()
        ]
    finally:
        connection.close()
    report = coverage_report(observations, [universe], members)[2]
    assert universe["denominator"] == 1538
    assert len(report["covered_ids"]) == 1361
    assert len(report["missing_ids"]) == 177
    assert len(report["unexpected_ids"]) == 177
    assert report["status"] == "PARTIAL"


def test_semantic_package_binding_inspects_all_historical_seed_rows_without_omission() -> None:
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        def table_rows(table: str) -> list[dict]:
            cursor = connection.execute(f'SELECT * FROM "{table}"')
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]

        facts = [
            row
            for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result")
            for row in table_rows(table)
        ]
        elections, contests, geographies = (
            table_rows("dim_election"), table_rows("dim_electoral_contest"), table_rows("dim_geo")
        )
    finally:
        connection.close()
    context = PublicationContext(
        release_id="HISTORICAL-SEED-AUDIT", as_of_date="2026-09-15",
        files=[{"relative_path": DATABASE.name, "sha256": sha256_file(DATABASE)}],
        coverage_matrix=[],
        datasets={"semantic_facts": facts, "elections": elections, "contests": contests, "geographies": geographies},
        checks={}, package_root=DATABASE.parent, package_database_path=DATABASE.name,
    )
    result = _semantic_facts(context)
    assert len(facts) == 33576
    assert (len(elections), len(contests), len(geographies)) == (9, 3715, 1825)
    assert "were omitted" not in result.justification
    assert "absent from the package database" not in result.justification
    assert "absent or changed in the package database" not in result.justification
    assert result.status == "FAIL"  # Known historical territorial-parent violations remain visible.


def test_readiness_audit_reports_external_territorial_coverage_without_claiming_ready() -> None:
    workbook = ROOT / "data/raw/elections/warehouse/demography/hcp_rgph2014_population_legale_12_regions.xlsx"
    canonical_database = ROOT / "data/exports/open/warehouse/morocco_elections.duckdb"
    if not workbook.is_file():
        pytest.skip("official HCP workbook not acquired locally")
    if not canonical_database.is_file():
        pytest.skip("local canonical package required")
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "morocco_elections",
            "audit",
            "--summary",
            "--require-ready",
        ],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    # Technical integrity passes, but a release command must stop on the
    # remaining publication gates.
    assert process.returncode == 2
    report = json.loads(process.stdout)
    assert report["integrity_status"] == "PASS"
    assert report["publication_status"] == "NOT_PUBLICATION_READY"
    assert report["blocking_gate_count"] >= 1
    assert report["blocking_record_count"] >= 354
    assert "LEGAL_REGIME_PINNED" in {row["gate_id"] for row in report["blocking_gates"]}
    assert report["unresolved_geography_count"] == 177
    assert report["unresolved_geography_parent_count"] == 0
    assert report["unresolved_commune_identity_count"] == 177
    assert report["official_result_universe_gap_count"] == 7
    assert report["not_computable_check_count"] == 14860
    computability = report["reconciliation_computability_by_election"]
    assert {row["election_id"] for row in computability} == {
        "COMM2015", "COMM2021", "LEG2007", "LEG2011", "LEG2016", "LEG2021", "REG2015", "REG2021"
    }
    assert sum(row["calculable_checks"] for row in computability) == 0
    assert sum(row["not_computable_checks"] for row in computability) == 14860
    assert report["result_history_gap_count"] == 8


def test_canonical_database_has_no_active_intermediate_release_identity() -> None:
    canonical_database = ROOT / "data/exports/open/warehouse/morocco_elections.duckdb"
    if not canonical_database.is_file():
        pytest.skip("local canonical package required")
    pattern = r"(?i)(^|[^a-z0-9])v(" + "|".join(str(number) for number in range(9, 17)) + r")([^0-9]|$)"
    connection = duckdb.connect(str(canonical_database), read_only=True)
    try:
        columns = connection.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='main' AND data_type='VARCHAR' "
            "AND (column_name LIKE '%_id' OR column_name IN ('candidate_sources', 'notes')) "
            "ORDER BY table_name, column_name"
        ).fetchall()
        findings = []
        for table, column in columns:
            count = connection.execute(
                f'SELECT count(*) FROM "{table}" WHERE regexp_matches("{column}", ?, \'i\')',
                [pattern],
            ).fetchone()[0]
            if count:
                findings.append((table, column, count))
    finally:
        connection.close()
    assert findings == []


def test_audit_rejects_a_package_with_manifested_file_drift(tmp_path: Path) -> None:
    package = ROOT / "data/exports/open/warehouse"
    database = package / "morocco_elections.duckdb"
    if not database.is_file():
        pytest.skip("local canonical package required")
    tampered = tmp_path / "warehouse"
    for source in package.rglob("*"):
        destination = tampered / source.relative_to(package)
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif source.name == database.name:
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    contract = tampered / "data-contract.json"
    contract.write_bytes(contract.read_bytes() + b"\n")

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "morocco_elections",
            "audit",
            "--package",
            str(tampered),
            "--summary",
        ],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )

    assert process.returncode == 1
    report = json.loads(process.stdout)
    assert report["integrity_status"] == "FAIL"
    assert report["publication_status"] == "NOT_PUBLICATION_READY"
    assert report["package_integrity_failure_count"] >= 1


def test_analytical_question_matrix_and_queries_are_synchronized_and_executable() -> None:
    database = ROOT / "data/exports/open/warehouse/morocco_elections.duckdb"
    if not database.is_file():
        pytest.skip("local canonical package required")
    guide = (ROOT / "docs/ANALYTICAL_GUIDE.md").read_text(encoding="utf-8")
    query_text = (ROOT / "examples/analytical_queries.sql").read_text(encoding="utf-8")
    guide_ids = re.findall(r"^\| (Q\d{2}) — ", guide, flags=re.MULTILINE)
    query_blocks = re.findall(
        r"^-- (Q\d{2})\..*?\n(.*?;)",
        query_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    expected_ids = [f"Q{index:02d}" for index in range(1, 16)]

    assert guide_ids == expected_ids
    assert [question_id for question_id, _ in query_blocks] == expected_ids
    connection = duckdb.connect(str(database), read_only=True)
    try:
        for question_id, query in query_blocks:
            assert question_id in expected_ids
            connection.execute(query).fetchone()
    finally:
        connection.close()


def test_historical_seed_audit_exposes_semantic_and_reconciliation_limits() -> None:
    report = audit_historical_seed(DATABASE)
    assert sum(report["fact_rows"].values()) > 0
    semantic = {row["check"]: row["violations"] for row in report["semantic_checks"]}
    assert semantic["fact_election_result.historical_regional_parent"] > 0
    assert all(value == 0 for check, value in semantic.items() if check != "fact_election_result.historical_regional_parent")
    assert all(row["violations"] == 0 for row in report["reconciliation_checks"])
    assert all(row["validation_status"] == "NOT_COMPUTABLE" for row in report["reconciliation_checks"])
    assert all(row["compared"] == 0 and row["not_computable"] == row["eligible"] for row in report["reconciliation_checks"])
    assert {row["check"]: row["provisional_compared"] for row in report["reconciliation_checks"]}["party_votes_vs_valid_votes"] == 82
    assert all(row["official_detail_universe_id"] is None for row in report["reconciliation_checks"])
    assert report["publication_status"] == "NOT_PUBLICATION_READY"
    assert "BALLOT_COMPONENTS_INCOMPLETE" in report["blockers"]
    assert "HISTORICAL_GEO_PARENTS_MISSING_FROM_SEED" in report["blockers"]
    communal = report["communal_grain_audit"]
    assert communal["contest_rows"] == 1538
    assert communal["ordinary_commune_contests"] == 1497
    assert communal["arrondissement_contests"] == 41
    assert communal["represented_parent_territories"] == communal["represented_parent_prefectures"] == 6
    assert communal["represented_parent_communes"] == 0
    assert {row["geo_type"] for row in communal["arrondissement_parents"]} == {"province_prefecture"}
    assert communal["implied_council_units"] == 1497
    assert communal["unverified_collapsed_units"] == communal["official_council_count"] == 1503
    assert communal["aggregate_count_matches_official"] is False
    assert communal["unverified_count_coincidence"] is True
    assert communal["council_grain_materialized"] is False
    assert "COMMUNAL_COUNCIL_GRAIN_NOT_MATERIALIZED" in report["blockers"]
    assert "ARRONDISSEMENT_PARENT_NOT_COMMUNE" in report["blockers"]
    assert {row["status"] for row in report["coverage"]} == {"UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR"}


def test_development_build_materializes_verified_legal_evidence(tmp_path: Path) -> None:
    output = tmp_path / "warehouse.duckdb"
    report = build_development_database(
        DATABASE,
        output,
        legal_seed_path=ROOT / "metadata/warehouse/legal_regimes.seed.json",
        source_registry_path=ROOT / "metadata/warehouse/source_registry.json",
        evidence_root=ROOT,
    )
    assert report["publication_status"] == "NOT_PUBLICATION_READY"
    assert report["seeded_legal_regimes"] == 15
    assert report["seeded_election_legal_links"] == 15
    assert report["seeded_contest_legal_links"] == 3361
    assert report["seeded_geo_populations"] == 1538
    assert report["seeded_geo_crosswalks"] == 1538
    assert report["seeded_geo_parent_relations"] == 204
    assert report["seeded_result_reconciliations"] == 14860
    assert report["unmapped_contests"] == 354
    history = report["result_history_report"]
    assert history["as_of_date"] == "2026-09-21"
    assert len(history["inventory"]) == 9
    assert len(history["gaps"]) == 8
    assert history["diagnostic"] == {
        "elections_inventoried": 9,
        "contests_concerned": 3715,
        "result_rows_concerned": 32937,
        "official_status_proven": 0,
        "with_published_at": 0,
        "with_known_at": 0,
        "with_valid_from": 0,
        "without_available_history": 3715,
        "complete_revision_chains": 0,
        "broken_revision_chains": 0,
        "cycles": 0,
        "validity_overlaps": 0,
        "post_as_of_records": 0,
        "invented_or_insufficiently_sourced_statuses": 0,
    }
    connection = duckdb.connect(str(output), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM dim_legal_regime").fetchone()[0] == 15
        assert connection.execute("SELECT count(*) FROM bridge_contest_legal_regime").fetchone()[0] == 3361
        assert "fact_result_revision" not in {
            row[0] for row in connection.execute("SHOW TABLES").fetchall()
        }
        metadata = connection.execute(
            "SELECT release, schema_version, seed_identity, as_of_date FROM warehouse_metadata"
        ).fetchone()
        assert metadata[:3] == ("development-2026-09-21", 1, "historical_seed")
        assert str(metadata[3]) == "2026-09-21"
        views = {
            row[0] for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_type='VIEW'"
            ).fetchall()
        }
        assert {
            "analytics_elections", "analytics_contests", "analytics_party_results",
            "analytics_seats", "analytics_mobilization", "analytics_geographies",
            "analytics_quality_controls", "analytics_coverage",
            "analytics_provenance", "analytics_national_summary",
        } == views
        assert connection.execute(
            "SELECT count(*) FROM analytics_geographies WHERE hcp_link_status='UNRESOLVED'"
        ).fetchone()[0] == 177
        assert connection.execute(
            "SELECT count(*) = count(DISTINCT geo_id) FROM analytics_geographies"
        ).fetchone()[0]
        assert connection.execute(
            "SELECT count(*) FROM analytics_quality_controls "
            "WHERE validation_status='NOT_COMPUTABLE'"
        ).fetchone()[0] == 14860
        assert connection.execute(
            "SELECT count(*) FROM analytics_mobilization "
            "WHERE denominator_status='NOT_COMPUTABLE' "
            "AND recomputed_turnout_rate IS NOT NULL"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM analytics_national_summary "
            "WHERE coverage_status <> 'UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR' "
            "OR official_denominator IS NOT NULL"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT count(*) FROM analytics_national_summary"
        ).fetchone()[0] == 9
        identifier_columns = connection.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='main' AND data_type='VARCHAR' "
            "AND (column_name LIKE '%_id' OR column_name='candidate_sources')"
        ).fetchall()
        for table, column in identifier_columns:
            count = connection.execute(
                f'SELECT count(*) FROM "{table}" '
                f'''WHERE regexp_matches("{column}", '_V[0-9]+(_[0-9]+)*(_|$)', 'i')'''
            ).fetchone()[0]
            assert count == 0, (table, column)
        assert len(TABLE_GRAINS) == 45
        for table, (_, keys) in TABLE_GRAINS.items():
            quoted_keys = ", ".join(f'"{key}"' for key in keys)
            total = connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            distinct = connection.execute(
                f'SELECT count(*) FROM (SELECT DISTINCT {quoted_keys} FROM "{table}")'
            ).fetchone()[0]
            null_predicate = " OR ".join(f'"{key}" IS NULL' for key in keys)
            nulls = connection.execute(
                f'SELECT count(*) FROM "{table}" WHERE {null_predicate}'
            ).fetchone()[0]
            assert (distinct, nulls) == (total, 0), table
        for view, semantics in VIEW_SEMANTICS.items():
            keys = semantics["logical_key"]
            quoted_keys = ", ".join(f'"{key}"' for key in keys)
            total = connection.execute(f'SELECT count(*) FROM "{view}"').fetchone()[0]
            distinct = connection.execute(
                f'SELECT count(*) FROM (SELECT DISTINCT {quoted_keys} FROM "{view}")'
            ).fetchone()[0]
            assert distinct == total, view
    finally:
        connection.close()
    catalog = _table_catalog(output)
    assert (catalog["table_count"], catalog["view_count"]) == (45, 10)
    table_fields = {
        "role", "grain", "logical_key", "authorized_relation_keys",
        "authorized_relations", "usage", "known_limits",
    }
    assert all(table_fields <= row.keys() for row in catalog["tables"])
    assert all(
        {"dependencies", "sql_definition", "sql_sha256"} <= row.keys()
        and len(row["sql_sha256"]) == 64
        for row in catalog["views"]
    )
    assert all(
        relation["target_table"] in TABLE_GRAINS
        for row in catalog["tables"] for relation in row["authorized_relations"]
    )
    legal_payload = json.loads((ROOT / "metadata/warehouse/legal_regimes.seed.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))["sources"]
    population_source_id = legal_payload["population_link_rules"][0]["population_source_id"]
    population_source = next(row for row in sources if row["source_id"] == population_source_id)
    seed = duckdb.connect(str(DATABASE), read_only=True)
    try:
        geographies = [
            dict(zip(("geo_id", "geo_type", "geo_name", "parent_geo_id"), values, strict=True))
            for values in seed.execute("SELECT geo_id, geo_type, geo_name, parent_geo_id FROM dim_geo").fetchall()
        ]
        contests = [
            dict(zip(("contest_id", "election_id", "source_list_type", "geo_id"), values, strict=True))
            for values in seed.execute("SELECT contest_id, election_id, list_type, geo_id FROM dim_electoral_contest").fetchall()
        ]
    finally:
        seed.close()
    populations, crosswalks = load_hcp_rgph2014_individuals(
        ROOT / population_source["raw_path"], geographies,
        source_id=population_source_id, source_url=population_source["source_url"],
    )
    trusted_ids = {row["geo_id"] for row in crosswalks if row["confidence"] == 1.0}
    derived_links = derive_contest_legal_regime_links(
        contests, legal_payload,
        populations_by_geo={row["normalized_geo_id"]: row for row in populations if row["normalized_geo_id"] in trusted_ids},
        geography_types={row["geo_id"]: row["geo_type"] for row in geographies},
    )
    context = PublicationContext(
        release_id="test-audit", as_of_date="2026-09-15",
        files=[{"relative_path": output.name, "sha256": sha256_file(output)}],
        coverage_matrix=[], datasets={"geographies": geographies}, checks={},
        package_root=tmp_path, package_database_path=output.name, evidence_root=ROOT,
    )
    materialized, failures = _bind_contract_tables(context, {
        "legal_regimes": ("dim_legal_regime", legal_payload["legal_regimes"]),
        "election_legal_regimes": ("bridge_election_legal_regime", legal_payload["election_links"]),
        "contest_legal_regimes": ("bridge_contest_legal_regime", derived_links),
        "geo_populations": ("fact_geo_population", populations),
        "geo_official_identifier_crosswalks": ("bridge_geo_official_identifier", crosswalks),
    })
    assert failures == []
    assert {name: item["row_count"] for name, item in materialized.items()} == {
        "legal_regimes": 15, "election_legal_regimes": 15, "contest_legal_regimes": 3361,
        "geo_populations": 1538, "geo_official_identifier_crosswalks": 1538,
    }
    extracted, source_failures = _verify_demographic_source_rows(
        context, populations, crosswalks, {row["source_id"]: row for row in sources},
    )
    assert source_failures == []
    assert {item["derived_count"] for item in extracted.values()} == {1538}
