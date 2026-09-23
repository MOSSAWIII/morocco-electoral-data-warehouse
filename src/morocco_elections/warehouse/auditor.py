from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]

from morocco_elections.warehouse.audit import audit_historical_seed  # noqa: E402
from morocco_elections.warehouse.coverage import coverage_report  # noqa: E402
from morocco_elections.warehouse.councils import derive_comm2015_council_candidates  # noqa: E402
from morocco_elections.warehouse.demography import load_hcp_rgph2014_arrondissement_identifiers, load_hcp_rgph2014_individuals, load_hcp_rgph2014_territorial_universe  # noqa: E402
from morocco_elections.warehouse.evidence import derive_contest_legal_regime_links, normalize_list_type, validate_official_source_registry  # noqa: E402
from morocco_elections.warehouse.geo_parents import geo_parent_report, validate_geo_parent_relations  # noqa: E402
from morocco_elections.warehouse.publication import PublicationContext, sha256_file, validate_publication  # noqa: E402
from morocco_elections.warehouse.reconciliation import derive_reconciliation_matrix  # noqa: E402
from morocco_elections.warehouse.result_history import build_result_history_diagnostic  # noqa: E402
from morocco_elections.warehouse.result_universes import load_chamber_2021_seat_universe  # noqa: E402
from morocco_elections.warehouse.sources import load_source_registry  # noqa: E402
from morocco_elections.warehouse.validation import validate_semantic_consistency  # noqa: E402


def _table_rows(connection: duckdb.DuckDBPyConnection, table: str) -> list[dict]:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only historical-seed-to-canonical readiness audit")
    parser.add_argument("--database", type=Path, default=ROOT / "data/exports/open/warehouse/morocco_elections.duckdb")
    parser.add_argument("--seed-database", type=Path, default=ROOT / "data/seeds/historical/morocco_elections.duckdb")
    parser.add_argument("--require-ready", action="store_true", help="return a non-zero exit status unless all publication gates pass")
    parser.add_argument("--summary", action="store_true", help="emit counts and gate statuses without full affected-record lists")
    parser.add_argument(
        "--historical-seed-diagnostic", action="store_true",
        help="include the legacy seed diagnostic separately from current product status",
    )
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error(f"warehouse database not found: {args.database}")
    if args.historical_seed_diagnostic and not args.seed_database.is_file():
        parser.error(f"historical seed database not found: {args.seed_database}")
    seed_audit = audit_historical_seed(args.seed_database) if args.historical_seed_diagnostic else None
    matrix_payload = json.loads((ROOT / "metadata/warehouse/release_coverage_matrix.template.json").read_text(encoding="utf-8"))
    legal_payload = json.loads((ROOT / "metadata/warehouse/legal_regimes.seed.json").read_text(encoding="utf-8"))
    source_payload = load_source_registry(ROOT)
    connection = duckdb.connect(str(args.database), read_only=True)
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
                "contest_id": contest_id,
                "election_id": election_id,
                "list_type": normalize_list_type(list_type),
                "source_list_type": list_type,
                "geo_id": geo_id,
                "region_geo_id": region_geo_id,
            }
            for contest_id, election_id, list_type, geo_id, region_geo_id in connection.execute(
                "SELECT contest_id, election_id, list_type, geo_id, region_geo_id FROM dim_electoral_contest ORDER BY contest_id"
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
            ancestor = geography
            seen: set[str] = set()
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
            row
            for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result")
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
        database_as_of = str(warehouse_metadata[0].get("as_of_date") or "2026-09-21")
        result_history = build_result_history_diagnostic(connection, ROOT, database_as_of)
        _, reconciliation_report = derive_reconciliation_matrix(connection, ROOT)
        parent_report = geo_parent_report(connection, geo_parent_relations)
    finally:
        connection.close()
    territorial_source_id = "MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS"
    territorial_source = next(row for row in source_payload["sources"] if row["source_id"] == territorial_source_id)
    territorial_issues = validate_official_source_registry(ROOT, {"sources": [territorial_source]})
    if territorial_issues:
        raise RuntimeError("official territorial source bytes are not verified: " + ", ".join(sorted({issue.code for issue in territorial_issues})))
    territorial_universe, territorial_members = load_hcp_rgph2014_territorial_universe(
        ROOT / territorial_source["raw_path"],
        election_id="COMM2015",
        source_id=territorial_source_id,
        source_url=territorial_source["source_url"],
        acquired_at=territorial_source["acquired_at"],
    )
    territorial_observations = [
        {"election_id": "COMM2015", "coverage_dimension": "TERRITORIAL", "geo_id": row["geo_id"]}
        for row in contests if row["election_id"] == "COMM2015"
    ]
    territorial_report = coverage_report(territorial_observations, [territorial_universe], territorial_members)[2]
    result_source = next(row for row in source_payload["sources"] if row["source_id"] == "SRC_CHAMBER_2021")
    result_issues = validate_official_source_registry(ROOT, {"sources": [result_source]})
    if result_issues:
        raise RuntimeError("official result-universe source bytes are not verified")
    result_universe, result_members = load_chamber_2021_seat_universe(
        ROOT / result_source["raw_path"],
        source_url=result_source["source_url"], acquired_at=result_source["acquired_at"],
    )
    official_report = coverage_report([], [result_universe], result_members)[1]
    council_seed = json.loads((ROOT / "metadata/warehouse/comm2015_council_candidates.seed.json").read_text(encoding="utf-8"))
    council_source_ids = {council_seed[field] for field in ("legal_source_id", "annex_source_id", "code_source_id")}
    council_source_ids.update(
        group["urban_commune_order_source_id"] for group in council_seed["groups"]
        if group.get("urban_commune_order_source_id")
    )
    council_sources = [row for row in source_payload["sources"] if row["source_id"] in council_source_ids]
    council_issues = validate_official_source_registry(ROOT, {"sources": council_sources})
    if len(council_sources) != len(council_source_ids) or council_issues:
        raise RuntimeError("council candidate sources are absent or unverified")
    official_arrondissements = load_hcp_rgph2014_arrondissement_identifiers(
        ROOT / territorial_source["raw_path"], source_id=territorial_source_id,
    )
    observed_arrondissements = {
        row["geo_id"] for row in contests
        if row["election_id"] == "COMM2015" and geography_by_id[row["geo_id"]]["geo_type"] == "arrondissement"
    }
    council_candidates = derive_comm2015_council_candidates(
        official_arrondissements, observed_arrondissements, council_seed,
    )
    matrix_rows = [{"release_id": matrix_payload["release_id"], **row} for row in matrix_payload["dimensions"]]
    territorial_matrix = next(row for row in matrix_rows if row["scope_id"].upper() == "TERRITORIAL")
    territorial_matrix.update({
        "universe_ids_json": json.dumps([territorial_universe["universe_id"]], separators=(",", ":")),
        "acquired": len(territorial_report["covered_ids"]) + len(territorial_report["unexpected_ids"]),
        "expected": territorial_report["denominator"],
        "covered": len(territorial_report["covered_ids"]),
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
        ROOT / population_source["raw_path"],
        geographies,
        source_id=population_source_id,
        source_url=population_source["source_url"],
    )
    trusted_ids = {row["geo_id"] for row in crosswalks if row["confidence"] == 1.0}
    contest_legal_regimes = derive_contest_legal_regime_links(
        contests,
        legal_payload,
        populations_by_geo={row["normalized_geo_id"]: row for row in populations if row["normalized_geo_id"] in trusted_ids},
        geography_types={row["geo_id"]: row["geo_type"] for row in geographies},
    )
    manifest_path = args.database.parent / "package-manifest.json"
    bundle_path = args.database.parent / "evidence-bundle.json"
    bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8")) if bundle_path.is_file() else {}
    if manifest_path.is_file():
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        package_files = manifest_payload["files"]
    else:
        package_files = [{"relative_path": args.database.name, "sha256": sha256_file(args.database)}]
    parent_report_path = args.database.with_name("geo-parent-report.json")
    reconciliation_report_path = args.database.with_name("reconciliation-report.json")
    context = PublicationContext(
        release_id="development-2026-09-21" if manifest_path.is_file() else "warehouse",
        as_of_date=package_files[0].get("acquired_at") if manifest_path.is_file() else source_payload.get("as_of_date") or "",
        files=package_files,
        coverage_matrix=matrix_rows,
        datasets={
            "elections": elections,
            "contests": contests,
            "geographies": geographies,
            "semantic_facts": semantic_facts,
            "geo_parent_relations": geo_parent_relations,
            "reconciliations": reconciliations,
            "legal_regimes": legal_payload["legal_regimes"],
            "election_legal_regimes": legal_payload["election_links"],
            "contest_legal_regimes": contest_legal_regimes,
            "official_sources": [
                row for row in source_payload["sources"]
                if "official_evidence" in row.get("usages", [])
            ],
            "geo_populations": populations,
            "geo_official_identifier_crosswalks": crosswalks,
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
        checks=bundle_payload.get("checks", {}),
        evidence_root=ROOT,
        package_root=args.database.parent,
        package_database_path=args.database.name,
        package_manifest_path=manifest_path.name if manifest_path.is_file() else None,
        package_manifest_sha256=sha256_file(manifest_path) if manifest_path.is_file() else None,
        evidence_bundle_path=bundle_path.name if bundle_path.is_file() else None,
        evidence_bundle_sha256=sha256_file(bundle_path) if bundle_path.is_file() else None,
    )
    publication = validate_publication(context)
    relation_issues = validate_geo_parent_relations(geo_parent_relations, geographies, elections)
    semantic_issues = validate_semantic_consistency(
        semantic_facts, contests, elections, geographies, geo_parent_relations,
    )
    semantic_failure = bool(relation_issues or semantic_issues or parent_report["remaining"])
    integrity_status = "FAIL" if semantic_failure else "PASS"
    report = {
        "integrity_status": integrity_status,
        "publication_status": publication["publication_status"],
        "geo_parent_report": parent_report,
        "reconciliation_report": reconciliation_report,
        "external_territorial_coverage": territorial_report,
        "council_candidates": council_candidates,
        "result_history_report": result_history,
        "publication_evaluation": publication,
    }
    if seed_audit is not None:
        report["historical_seed_diagnostic"] = seed_audit
    if args.summary:
        unresolved_commune_identities = sum(
            row.get("matching_method") != "OFFICIAL_IDENTIFIER" or row.get("confidence") != 1.0
            for row in crosswalks
        )
        declared_result_elections = {
            str(row["election_id"])
            for row in (territorial_universe, result_universe)
            if row.get("coverage_dimension") == "OFFICIAL"
        }
        required_result_elections = {
            str(row["election_id"]) for row in result_universe_required_elections
        }
        blocking_gates = [
            {
                "gate_id": row["gate_id"],
                "affected_record_count": len(json.loads(row["affected_records"])),
                "justification": row["justification"],
            }
            for row in publication["gate_results"] if row["gate_status"] != "PASS"
        ]
        report = {
            "integrity_status": integrity_status,
            "publication_status": publication["publication_status"],
            "blocking_gate_count": len(blocking_gates),
            "blocking_record_count": sum(row["affected_record_count"] for row in blocking_gates),
            "blocking_gates": blocking_gates,
            "unresolved_geography_count": parent_report["remaining"] + unresolved_commune_identities,
            "unresolved_geography_parent_count": parent_report["remaining"],
            "unresolved_commune_identity_count": unresolved_commune_identities,
            "official_result_universe_gap_count": len(
                required_result_elections - declared_result_elections
            ),
            "not_computable_check_count": sum(
                row.get("validation_status") == "NOT_COMPUTABLE" for row in reconciliations
            ),
            "reconciliation_computability_by_election": [
                {
                    "election_id": row["election_id"],
                    "calculable_checks": row["calculable_checks"],
                    "not_computable_checks": row["not_computable_checks"],
                }
                for row in reconciliation_report["computability_by_election"]
            ],
            "result_history_gap_count": len(result_history["gaps"]),
        }
        if seed_audit is not None:
            report["historical_seed_diagnostic"] = seed_audit
    print(json.dumps(report, ensure_ascii=False, indent=2))
    readiness_failure = args.require_ready and publication["publication_status"] != "PUBLICATION_READY"
    if semantic_failure:
        return 1
    return 2 if readiness_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
