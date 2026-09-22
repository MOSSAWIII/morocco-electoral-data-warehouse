from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from morocco_elections.v16.publication import sha256_file
from morocco_elections.v16.validation import ValidationIssue, validate_rows


SOURCE_STATUSES = {"VERIFIED_AUTHORITY_AND_BYTES", "VERIFIED_PORTAL_NOT_ACQUIRED", "VERIFIED_PORTAL_ACQUISITION_BLOCKED"}
LICENSE_STATUSES = {"REDISTRIBUTABLE", "METADATA_ONLY", "FORBIDDEN", "UNKNOWN"}
PUBLIC_DISPOSITIONS = {"INCLUDE", "METADATA_ONLY", "EXCLUDE"}
LIST_TYPE_ALIASES = {
    "communal": "LOCAL",
    "locale": "LOCAL",
    "local": "LOCAL",
    "nationale": "NATIONAL",
    "national": "NATIONAL",
    "regionale": "REGIONAL",
    "regional": "REGIONAL",
    "regional_council": "REGIONAL",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_list_type(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return LIST_TYPE_ALIASES.get(normalized, normalized.upper())


def derive_contest_legal_regime_links(
    contests: Iterable[Mapping[str, Any]],
    payload: Mapping[str, Any],
    *,
    populations_by_geo: Mapping[str, Mapping[str, Any]] | None = None,
    geography_types: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Expand explicit election/source-list rules into auditable contest-level links."""
    rules = {
        (str(row.get("election_id")), str(row.get("source_list_type", "")).strip().lower()): row
        for row in payload.get("contest_link_rules", [])
    }
    regimes = {str(row.get("legal_regime_id")): row for row in payload.get("legal_regimes", [])}
    population_rules = {str(row.get("election_id")): row for row in payload.get("population_link_rules", [])}
    geo_type_rules = {
        (str(row.get("election_id")), str(row.get("geo_type"))): row
        for row in payload.get("geo_type_link_rules", [])
    }
    links: list[dict[str, Any]] = []
    for contest in contests:
        key = (str(contest.get("election_id")), str(contest.get("source_list_type", "")).strip().lower())
        rule = rules.get(key)
        classification: dict[str, Any] = {}
        if rule is None and populations_by_geo is not None and geography_types is not None:
            population_rule = population_rules.get(str(contest.get("election_id")))
            geo_id = str(contest.get("geo_id"))
            population = populations_by_geo.get(geo_id)
            if population_rule is not None and geography_types.get(geo_id) == population_rule.get("geo_type") and population:
                value, threshold = population.get("population"), population_rule.get("threshold")
                if isinstance(value, int) and isinstance(threshold, int):
                    regime_id = population_rule["at_or_below_regime_id"] if value <= threshold else population_rule["above_regime_id"]
                    regime = regimes.get(str(regime_id))
                    rule = {"legal_regime_id": regime_id, "source_id": regime.get("official_source_id") if regime else None}
                    classification = {
                        "classification_basis": "POPULATION_THRESHOLD",
                        "classification_source_id": population_rule.get("population_source_id"),
                        "classification_value": value,
                        "classification_rule": f"population <= {threshold}",
                    }
        if rule is None and geography_types is not None:
            geo_type = geography_types.get(str(contest.get("geo_id")))
            geo_rule = geo_type_rules.get((str(contest.get("election_id")), str(geo_type)))
            if geo_rule is not None:
                rule = geo_rule
                classification = {
                    "classification_basis": "GEO_TYPE",
                    "classification_rule": f"geo_type == {geo_type}",
                }
        if rule is None:
            continue
        regime = regimes.get(str(rule.get("legal_regime_id")))
        links.append(
            {
                "contest_id": contest.get("contest_id"),
                "election_id": contest.get("election_id"),
                "legal_regime_id": rule.get("legal_regime_id"),
                "valid_from": regime.get("valid_from") if regime else None,
                "source_id": rule.get("source_id"),
                **classification,
            }
        )
    return links


def validate_official_source_registry(root: Path, payload: Mapping[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    resolved_root = root.resolve()
    for row in payload.get("sources", []):
        source_id = str(row.get("source_id", "<unknown>"))
        if source_id in seen:
            issues.append(ValidationIssue("DUPLICATE_SOURCE_ID", "official_source_registry", source_id, "source_id must be unique"))
        seen.add(source_id)
        required = ("title", "authority", "source_url", "verification_status", "license_status", "public_package_disposition")
        missing = [field for field in required if not row.get(field)]
        if missing:
            issues.append(ValidationIssue("SOURCE_METADATA_MISSING", "official_source_registry", source_id, ", ".join(missing)))
        if not str(row.get("source_url", "")).startswith("https://"):
            issues.append(ValidationIssue("OFFICIAL_SOURCE_HTTPS_REQUIRED", "official_source_registry", source_id, "source URL must use HTTPS"))
        if row.get("verification_status") not in SOURCE_STATUSES:
            issues.append(ValidationIssue("INVALID_SOURCE_VERIFICATION_STATUS", "official_source_registry", source_id, str(row.get("verification_status"))))
        license_status, disposition = row.get("license_status"), row.get("public_package_disposition")
        if license_status not in LICENSE_STATUSES or disposition not in PUBLIC_DISPOSITIONS:
            issues.append(ValidationIssue("INVALID_SOURCE_DISTRIBUTION_STATUS", "official_source_registry", source_id, "license or disposition is invalid"))
        if license_status in {"UNKNOWN", "FORBIDDEN", "METADATA_ONLY"} and disposition == "INCLUDE":
            issues.append(ValidationIssue("UNLICENSED_SOURCE_INCLUDED", "official_source_registry", source_id, "source bytes cannot enter the public package"))
        if row.get("verification_status") == "VERIFIED_AUTHORITY_AND_BYTES":
            relative = row.get("raw_path")
            path = (root / str(relative)).resolve() if relative else None
            if path is None or resolved_root not in path.parents or not path.is_file():
                issues.append(ValidationIssue("VERIFIED_SOURCE_BYTES_MISSING", "official_source_registry", source_id, str(relative)))
                continue
            observed_size = path.stat().st_size
            if observed_size != row.get("bytes"):
                issues.append(
                    ValidationIssue(
                        "SOURCE_SIZE_MISMATCH",
                        "official_source_registry",
                        source_id,
                        f"{relative}: expected {row.get('bytes')}, observed {observed_size}",
                    )
                )
            observed_sha256 = sha256_file(path)
            if observed_sha256 != row.get("sha256"):
                issues.append(
                    ValidationIssue(
                        "SOURCE_CHECKSUM_MISMATCH",
                        "official_source_registry",
                        source_id,
                        f"{relative}: expected {row.get('sha256')}, observed {observed_sha256}",
                    )
                )
    return issues


def validate_legal_regime_seed(payload: Mapping[str, Any], source_registry: Mapping[str, Any]) -> list[ValidationIssue]:
    regimes = list(payload.get("legal_regimes", []))
    links = list(payload.get("election_links", []))
    issues = validate_rows("dim_legal_regime", regimes) + validate_rows("bridge_election_legal_regime", links)
    sources_by_id = {row.get("source_id"): row for row in source_registry.get("sources", [])}
    source_ids = set(sources_by_id)

    def require_verified_legal_source(table: str, record_id: str, source_id: Any, *, supporting: bool = False) -> None:
        unknown_code = "UNKNOWN_SUPPORTING_LEGAL_SOURCE" if supporting else "UNKNOWN_OFFICIAL_LEGAL_SOURCE"
        if source_id not in source_ids:
            issues.append(ValidationIssue(unknown_code, table, record_id, str(source_id)))
            return
        if sources_by_id[source_id].get("verification_status") != "VERIFIED_AUTHORITY_AND_BYTES":
            issues.append(
                ValidationIssue(
                    "LEGAL_SOURCE_BYTES_NOT_VERIFIED",
                    table,
                    record_id,
                    f"{source_id} is not VERIFIED_AUTHORITY_AND_BYTES",
                )
            )

    for row in regimes:
        rid = str(row.get("legal_regime_id", "<unknown>"))
        require_verified_legal_source("dim_legal_regime", rid, row.get("official_source_id"))
        for source_id in row.get("supporting_source_ids", []):
            require_verified_legal_source("dim_legal_regime", rid, source_id, supporting=True)
    for row in links:
        rid = f"{row.get('election_id')}:{row.get('legal_regime_id')}"
        require_verified_legal_source("bridge_election_legal_regime", rid, row.get("source_id"))
    regime_ids = {row.get("legal_regime_id") for row in regimes}
    rule_keys: set[tuple[str, str]] = set()
    for row in payload.get("contest_link_rules", []):
        election_id = str(row.get("election_id", ""))
        source_list_type = str(row.get("source_list_type", "")).strip().lower()
        rid = f"{election_id}:{source_list_type or '<missing>'}"
        key = (election_id, source_list_type)
        if not election_id or not source_list_type or not row.get("legal_regime_id") or not row.get("source_id"):
            issues.append(ValidationIssue("CONTEST_LEGAL_RULE_MISSING_FIELD", "contest_link_rule", rid, "election_id, source_list_type, legal_regime_id and source_id are required"))
        if key in rule_keys:
            issues.append(ValidationIssue("DUPLICATE_CONTEST_LEGAL_RULE", "contest_link_rule", rid, "election and source list type must identify one rule"))
        rule_keys.add(key)
        if row.get("legal_regime_id") not in regime_ids:
            issues.append(ValidationIssue("UNKNOWN_CONTEST_LEGAL_RULE_REGIME", "contest_link_rule", rid, str(row.get("legal_regime_id"))))
        require_verified_legal_source("contest_link_rule", rid, row.get("source_id"))
        regime = next((item for item in regimes if item.get("legal_regime_id") == row.get("legal_regime_id")), None)
        if regime and normalize_list_type(source_list_type) != normalize_list_type(regime.get("list_type")):
            issues.append(ValidationIssue("CONTEST_LEGAL_RULE_LIST_TYPE_MISMATCH", "contest_link_rule", rid, str(regime.get("list_type"))))
    population_elections: set[str] = set()
    for row in payload.get("population_link_rules", []):
        election_id = str(row.get("election_id", ""))
        rid = election_id or "<missing>"
        required = ("election_id", "geo_type", "threshold", "at_or_below_regime_id", "above_regime_id", "population_source_id")
        if any(row.get(field) is None or row.get(field) == "" for field in required):
            issues.append(ValidationIssue("POPULATION_LEGAL_RULE_MISSING_FIELD", "population_link_rule", rid, ", ".join(required)))
        if election_id in population_elections:
            issues.append(ValidationIssue("DUPLICATE_POPULATION_LEGAL_RULE", "population_link_rule", rid, "election_id must identify one population rule"))
        population_elections.add(election_id)
        if not isinstance(row.get("threshold"), int) or isinstance(row.get("threshold"), bool) or row.get("threshold", -1) < 0:
            issues.append(ValidationIssue("INVALID_POPULATION_THRESHOLD", "population_link_rule", rid, str(row.get("threshold"))))
        for field in ("at_or_below_regime_id", "above_regime_id"):
            if row.get(field) not in regime_ids:
                issues.append(ValidationIssue("UNKNOWN_POPULATION_RULE_REGIME", "population_link_rule", rid, str(row.get(field))))
        require_verified_legal_source("population_link_rule", rid, row.get("population_source_id"))
    geo_type_keys: set[tuple[str, str]] = set()
    for row in payload.get("geo_type_link_rules", []):
        election_id, geo_type = str(row.get("election_id", "")), str(row.get("geo_type", ""))
        rid, key = f"{election_id}:{geo_type}", (election_id, geo_type)
        if not all(row.get(field) for field in ("election_id", "geo_type", "legal_regime_id", "source_id")):
            issues.append(ValidationIssue("GEO_TYPE_LEGAL_RULE_MISSING_FIELD", "geo_type_link_rule", rid, "all fields are required"))
        if key in geo_type_keys:
            issues.append(ValidationIssue("DUPLICATE_GEO_TYPE_LEGAL_RULE", "geo_type_link_rule", rid, "election and geo type must identify one rule"))
        geo_type_keys.add(key)
        if row.get("legal_regime_id") not in regime_ids:
            issues.append(ValidationIssue("UNKNOWN_GEO_TYPE_RULE_REGIME", "geo_type_link_rule", rid, str(row.get("legal_regime_id"))))
        require_verified_legal_source("geo_type_link_rule", rid, row.get("source_id"))
    if payload.get("coverage_status") != "PARTIAL" or not payload.get("coverage_limitation"):
        issues.append(ValidationIssue("LEGAL_SEED_COVERAGE_NOT_DISCLOSED", "legal_regime_seed", "V16", "partial seed coverage and its limitation must be explicit"))
    return issues
