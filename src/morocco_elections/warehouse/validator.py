from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]

from morocco_elections.warehouse.contracts import TABLE_CONTRACTS, VOCABULARIES  # noqa: E402
from morocco_elections.warehouse.bo6374 import validate_visual_candidate  # noqa: E402
from morocco_elections.warehouse.bo6374_reconciliation import DEFAULT_ARTIFACT_PATH, build_reconciliation, validate_reconciliation  # noqa: E402
from morocco_elections.warehouse.evidence import load_json, validate_legal_regime_seed, validate_official_source_registry  # noqa: E402
from morocco_elections.warehouse.geo_parents import build_geo_parent_evidence, geo_parent_report, validate_geo_parent_relations  # noqa: E402
from morocco_elections.warehouse.reconciliation import derive_reconciliation_matrix  # noqa: E402
from morocco_elections.warehouse.validation import ValidationIssue, validate_semantic_consistency  # noqa: E402
from morocco_elections.warehouse.package import validate_package  # noqa: E402
from morocco_elections.warehouse.sources import load_source_registry, official_source_rows, source_registry_issues  # noqa: E402


def _rows(connection: duckdb.DuckDBPyConnection, table: str) -> list[dict]:
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    fields = [item[0] for item in cursor.description]
    return [dict(zip(fields, values, strict=True)) for values in cursor.fetchall()]


def _canonical_row(row: dict) -> str:
    numeric = {"official_value", "recomputed_value", "difference", "tolerance"}
    return json.dumps(
        {
            key: value.isoformat() if isinstance(value, date) else float(value)
            if key in numeric and isinstance(value, (int, float)) and not isinstance(value, bool) else value
            for key, value in sorted(row.items()) if value is not None
        },
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def main(argv: list[str] | None = None) -> int:
    issues: list[ValidationIssue] = []
    source_registry = load_source_registry(ROOT)
    issues.extend(
        ValidationIssue("SOURCE_REGISTRY_INVALID", "source_registry", "REGISTRY", message)
        for message in source_registry_issues(source_registry)
    )
    legal_seed = load_json(ROOT / "metadata/warehouse/legal_regimes.seed.json")
    issues.extend(validate_official_source_registry(ROOT, {"sources": official_source_rows(ROOT)}))
    issues.extend(validate_legal_regime_seed(legal_seed, source_registry))
    visual_paths = sorted((ROOT / "metadata/warehouse").glob("bo6374_page*_visual_transcription.candidate.json"))
    visual_candidates = [load_json(path) for path in visual_paths]
    bo6374_source = next(
        (row for row in source_registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015"),
        {},
    )
    for visual_candidate in visual_candidates:
        issues.extend(
            ValidationIssue("VISUAL_CANDIDATE_INVALID", "bo6374_visual_transcription", str(visual_candidate.get("printed_page")), message)
            for message in validate_visual_candidate(visual_candidate, bo6374_source)
        )
    visual_pages = [candidate.get("printed_page") for candidate in visual_candidates]
    if visual_pages != list(range(6105, 6105 + len(visual_pages))):
        issues.append(ValidationIssue("VISUAL_CANDIDATE_PAGE_GAP", "bo6374_visual_transcription", "BO6374", "candidate pages must start at 6105 and remain consecutive"))
    reconciliation_path = ROOT / DEFAULT_ARTIFACT_PATH
    if not reconciliation_path.is_file():
        reconciliation = build_reconciliation(ROOT)
        issues.extend(validate_reconciliation(reconciliation, ROOT))
    else:
        reconciliation = load_json(reconciliation_path)
        issues.extend(validate_reconciliation(reconciliation, ROOT))
    database = ROOT / "data/exports/open/warehouse/morocco_elections.duckdb"
    package_report = validate_package(database.parent) if (database.parent / "package-manifest.json").is_file() else {}
    if package_report and package_report["status"] != "PASS":
        issues.extend(
            ValidationIssue("warehouse_PACKAGE_INVALID", "package", str(row["record"]), str(row["message"]))
            for row in package_report["failures"]
        )
    parent_report = {}
    materialized_parent_count = 0
    reconciliation_report = {}
    materialized_reconciliation_count = 0
    if not database.is_file():
        issues.append(ValidationIssue("warehouse_DATABASE_MISSING", "bridge_geo_parent", "warehouse", str(database)))
    else:
        connection = duckdb.connect(str(database), read_only=True)
        try:
            materialized = _rows(connection, "bridge_geo_parent")
            expected, _ = build_geo_parent_evidence(connection, ROOT)
            materialized_reconciliations = _rows(connection, "fact_result_reconciliation")
            expected_reconciliations, reconciliation_report = derive_reconciliation_matrix(connection, ROOT)
            geographies = _rows(connection, "dim_geo")
            elections = _rows(connection, "dim_election")
            contests = _rows(connection, "dim_electoral_contest")
            facts = [
                row for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result")
                for row in _rows(connection, table)
            ]
            materialized_parent_count = len(materialized)
            materialized_reconciliation_count = len(materialized_reconciliations)
            if Counter(map(_canonical_row, materialized)) != Counter(map(_canonical_row, expected)):
                issues.append(ValidationIssue("GEO_PARENT_MATERIALIZATION_DIFFERS", "bridge_geo_parent", "warehouse", "materialized rows differ from reproducible evidence"))
            if Counter(map(_canonical_row, materialized_reconciliations)) != Counter(map(_canonical_row, expected_reconciliations)):
                issues.append(ValidationIssue("RECONCILIATION_MATERIALIZATION_DIFFERS", "fact_result_reconciliation", "warehouse", "materialized rows differ from reproducible package facts"))
            issues.extend(validate_geo_parent_relations(materialized, geographies, elections))
            issues.extend(validate_semantic_consistency(facts, contests, elections, geographies, materialized))
            parent_report = geo_parent_report(connection, materialized)
        except duckdb.Error as error:
            issues.append(ValidationIssue("warehouse_DATABASE_INVALID", "bridge_geo_parent", "warehouse", type(error).__name__))
        finally:
            connection.close()
    payload = {
        "release": "warehouse",
        "contract_tables": len(TABLE_CONTRACTS),
        "controlled_vocabularies": len(VOCABULARIES),
        "canonical_warehouse_sources": len(source_registry["sources"]),
        "encoded_warehouse_legal_regimes": len(legal_seed["legal_regimes"]),
        "bo6374_visual_candidate_rows": sum(
            len(group["rows"]) for candidate in visual_candidates for group in candidate["groups"]
        ),
        "bo6374_visual_candidate_pages": visual_pages,
        "bo6374_tafra_reconciliation_rows": len(reconciliation.get("rows", [])),
        "bo6374_tafra_reconciliation_report": reconciliation.get("report", {}),
        "materialized_geo_parent_relations": materialized_parent_count,
        "geo_parent_report": parent_report,
        "materialized_result_reconciliations": materialized_reconciliation_count,
        "reconciliation_report": reconciliation_report,
        "package_validation": package_report,
        "status": "PASS" if not issues else "FAIL",
        "issues": [issue.__dict__ for issue in issues],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
