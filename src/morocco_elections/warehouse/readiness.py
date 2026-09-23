"""Construct the package-derived publication context used by build and audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.warehouse import DEFAULT_SNAPSHOT_ID
from morocco_elections.warehouse.coverage import coverage_report
from morocco_elections.warehouse.councils import derive_comm2015_council_candidates
from morocco_elections.warehouse.demography import (
    load_hcp_rgph2014_arrondissement_identifiers,
    load_hcp_rgph2014_individuals,
    load_hcp_rgph2014_territorial_universe,
)
from morocco_elections.warehouse.evidence import (
    derive_contest_legal_regime_links,
    normalize_list_type,
    validate_official_source_registry,
)
from morocco_elections.warehouse.geo_parents import geo_parent_report
from morocco_elections.warehouse.publication import PublicationContext, sha256_file
from morocco_elections.warehouse.reconciliation import derive_reconciliation_matrix
from morocco_elections.warehouse.result_history import build_result_history_diagnostic
from morocco_elections.warehouse.result_universes import load_chamber_2021_seat_universe
from morocco_elections.warehouse.sources import load_source_registry


def _table_rows(connection: duckdb.DuckDBPyConnection, table: str) -> list[dict[str, Any]]:
    present = connection.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = ?",
        [table],
    ).fetchone()[0]
    if not present:
        return []
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]


def build_readiness_context(
    database: Path,
    repository_root: Path,
    *,
    files: list[dict[str, Any]],
    release_id: str = DEFAULT_SNAPSHOT_ID,
    as_of_date: str = "2026-09-21",
    package_manifest_path: str | None = None,
    package_manifest_sha256: str | None = None,
    evidence_bundle_path: str | None = None,
    evidence_bundle_sha256: str | None = None,
) -> tuple[PublicationContext, dict[str, Any]]:
    repository_root, database = repository_root.resolve(), database.resolve()
    matrix_payload = json.loads((repository_root / "metadata/warehouse/release_coverage_matrix.template.json").read_text(encoding="utf-8"))
    legal_payload = json.loads((repository_root / "metadata/warehouse/legal_regimes.seed.json").read_text(encoding="utf-8"))
    source_payload = load_source_registry(repository_root)
    connection = duckdb.connect(str(database), read_only=True)
    try:
        elections = [
            {"election_id": election_id, "election_date": election_date.isoformat(), "covered": contest_count > 0}
            for election_id, election_date, contest_count in connection.execute(
                "SELECT e.election_id, e.election_date, count(c.contest_id) "
                "FROM dim_election e LEFT JOIN dim_electoral_contest c USING (election_id) "
                "GROUP BY e.election_id, e.election_date ORDER BY e.election_id"
            ).fetchall()
        ]
        contests = [
            {
                "contest_id": contest_id, "election_id": election_id,
                "list_type": normalize_list_type(list_type), "source_list_type": list_type,
                "geo_id": geo_id, "region_geo_id": region_geo_id,
            }
            for contest_id, election_id, list_type, geo_id, region_geo_id in connection.execute(
                "SELECT contest_id, election_id, list_type, geo_id, region_geo_id "
                "FROM dim_electoral_contest ORDER BY contest_id"
            ).fetchall()
        ]
        geographies = [
            {"geo_id": geo_id, "geo_type": geo_type, "geo_name": geo_name, "parent_geo_id": parent_geo_id}
            for geo_id, geo_type, geo_name, parent_geo_id in connection.execute(
                "SELECT geo_id, geo_type, geo_name, parent_geo_id FROM dim_geo ORDER BY geo_id"
            ).fetchall()
        ]
        geography_by_id = {row["geo_id"]: row for row in geographies}
        for geography in geographies:
            ancestor, seen = geography, set()
            while ancestor:
                ancestor_id = str(ancestor.get("geo_id"))
                if ancestor_id in seen:
                    break
                seen.add(ancestor_id)
                if ancestor.get("geo_type") == "region":
                    geography["region_geo_id"] = ancestor.get("geo_id")
                    break
                ancestor = geography_by_id.get(ancestor.get("parent_geo_id"), {})
        semantic_facts = [
            row for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result")
            for row in _table_rows(connection, table)
        ]
        result_universe_required_elections = [
            {"election_id": row[0]} for row in connection.execute(
                "SELECT DISTINCT election_id FROM fact_election_result "
                "UNION SELECT DISTINCT election_id FROM fact_communal_election_result ORDER BY 1"
            ).fetchall()
        ]
        geo_parent_relations = _table_rows(connection, "bridge_geo_parent")
        reconciliations = _table_rows(connection, "fact_result_reconciliation")
        result_revisions = _table_rows(connection, "fact_result_revision")
        legal_decisions = _table_rows(connection, "fact_legal_decision")
        warehouse_metadata = _table_rows(connection, "warehouse_metadata")
        result_history = build_result_history_diagnostic(
            connection, repository_root, as_of_date,
        )
        _, reconciliation_report = derive_reconciliation_matrix(connection, repository_root)
        parent_report = geo_parent_report(connection, geo_parent_relations)
    finally:
        connection.close()

    territorial_source_id = "MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS"
    territorial_source = next(row for row in source_payload["sources"] if row["source_id"] == territorial_source_id)
    issues = validate_official_source_registry(repository_root, {"sources": [territorial_source]})
    if issues:
        raise RuntimeError("official territorial source bytes are not verified")
    territorial_universe, territorial_members = load_hcp_rgph2014_territorial_universe(
        repository_root / territorial_source["raw_path"], election_id="COMM2015",
        source_id=territorial_source_id, source_url=territorial_source["source_url"],
        acquired_at=territorial_source["acquired_at"],
    )
    territorial_observations = [
        {"election_id": "COMM2015", "coverage_dimension": "TERRITORIAL", "geo_id": row["geo_id"]}
        for row in contests if row["election_id"] == "COMM2015"
    ]
    territorial_report = coverage_report(territorial_observations, [territorial_universe], territorial_members)[2]
    result_source = next(row for row in source_payload["sources"] if row["source_id"] == "SRC_CHAMBER_2021")
    result_issues = validate_official_source_registry(repository_root, {"sources": [result_source]})
    if result_issues:
        raise RuntimeError("official result-universe source bytes are not verified")
    result_universe, result_members = load_chamber_2021_seat_universe(
        repository_root / result_source["raw_path"],
        source_url=result_source["source_url"], acquired_at=result_source["acquired_at"],
    )
    official_report = coverage_report([], [result_universe], result_members)[1]
    matrix_rows = [{"release_id": matrix_payload["release_id"], **row} for row in matrix_payload["dimensions"]]
    territorial_matrix = next(row for row in matrix_rows if row["scope_id"].upper() == "TERRITORIAL")
    territorial_matrix.update({
        "universe_ids_json": json.dumps([territorial_universe["universe_id"]], separators=(",", ":")),
        "acquired": len(territorial_report["covered_ids"]) + len(territorial_report["unexpected_ids"]),
        "expected": territorial_report["denominator"], "covered": len(territorial_report["covered_ids"]),
        "missing": len(territorial_report["missing_ids"]),
        "non_comparable": len(territorial_report["non_comparable_ids"]),
        "redistribution_forbidden": len(territorial_report["redistribution_forbidden_ids"]),
        "status": territorial_report["status"],
    })
    official_matrix = next(row for row in matrix_rows if row["scope_id"].upper() == "OFFICIAL")
    official_matrix.update({
        "universe_ids_json": json.dumps([result_universe["universe_id"]], separators=(",", ":")),
        "acquired": 0, "expected": official_report["denominator"], "covered": 0,
        "missing": len(official_report["missing_ids"]), "non_comparable": 0,
        "redistribution_forbidden": 0, "status": official_report["status"],
    })
    population_source_id = legal_payload["population_link_rules"][0]["population_source_id"]
    population_source = next(row for row in source_payload["sources"] if row["source_id"] == population_source_id)
    populations, crosswalks = load_hcp_rgph2014_individuals(
        repository_root / population_source["raw_path"], geographies,
        source_id=population_source_id, source_url=population_source["source_url"],
    )
    trusted_ids = {row["geo_id"] for row in crosswalks if row["confidence"] == 1.0}
    contest_legal_regimes = derive_contest_legal_regime_links(
        contests, legal_payload,
        populations_by_geo={row["normalized_geo_id"]: row for row in populations if row["normalized_geo_id"] in trusted_ids},
        geography_types={row["geo_id"]: row["geo_type"] for row in geographies},
    )
    council_seed = json.loads((repository_root / "metadata/warehouse/comm2015_council_candidates.seed.json").read_text(encoding="utf-8"))
    official_arrondissements = load_hcp_rgph2014_arrondissement_identifiers(
        repository_root / territorial_source["raw_path"], source_id=territorial_source_id,
    )
    observed_arrondissements = {
        row["geo_id"] for row in contests
        if row["election_id"] == "COMM2015" and geography_by_id[row["geo_id"]]["geo_type"] == "arrondissement"
    }
    council_candidates = derive_comm2015_council_candidates(
        official_arrondissements, observed_arrondissements, council_seed,
    )
    context = PublicationContext(
        release_id=release_id, as_of_date=as_of_date, files=files, coverage_matrix=matrix_rows,
        datasets={
            "elections": elections, "contests": contests, "geographies": geographies,
            "semantic_facts": semantic_facts, "geo_parent_relations": geo_parent_relations,
            "reconciliations": reconciliations, "legal_regimes": legal_payload["legal_regimes"],
            "election_legal_regimes": legal_payload["election_links"],
            "contest_legal_regimes": contest_legal_regimes,
            "official_sources": [
                row for row in source_payload["sources"]
                if "official_evidence" in row.get("usages", [])
            ],
            "geo_populations": populations, "geo_official_identifier_crosswalks": crosswalks,
            "population_legal_rules": legal_payload["population_link_rules"],
            "geo_type_legal_rules": legal_payload["geo_type_link_rules"],
            "coverage_universes": [territorial_universe, result_universe],
            "coverage_universe_members": [*territorial_members, *result_members],
            "coverage_observations": territorial_observations,
            "result_universe_required_elections": result_universe_required_elections,
            "result_revisions": result_revisions,
            "legal_decisions": legal_decisions,
            "warehouse_metadata": warehouse_metadata,
            "result_history_inventory": result_history["inventory"],
            "result_history_gaps": result_history["gaps"],
        },
        checks={}, evidence_root=repository_root, package_root=database.parent,
        package_database_path=database.name, package_manifest_path=package_manifest_path,
        package_manifest_sha256=package_manifest_sha256, evidence_bundle_path=evidence_bundle_path,
        evidence_bundle_sha256=evidence_bundle_sha256,
    )
    return context, {
        "geo_parent_report": parent_report,
        "reconciliation_report": reconciliation_report,
        "external_territorial_coverage": territorial_report,
        "council_candidates": council_candidates,
        "result_history_report": result_history,
    }
