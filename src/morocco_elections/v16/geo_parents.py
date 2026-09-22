"""Versioned V16 parent relations without rewriting immutable V15 geography rows."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping

import duckdb
import openpyxl

from morocco_elections.v16.bo6374_reconciliation import normalize_arabic
from morocco_elections.v16.evidence import validate_official_source_registry
from morocco_elections.v16.validation import ValidationIssue, validate_rows, validate_semantic_consistency


COMM2015_SEED_PATH = Path("metadata/v16/comm2015_geo_parents.seed.json")
HCP_SOURCE_ID = "MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS"
HISTORICAL_ELECTIONS = {"LEG2007", "LEG2011"}


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _table_rows(connection: duckdb.DuckDBPyConnection, table: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]


def _verify_manifest_sources(root: Path, source_ids: set[str]) -> dict[str, dict[str, Any]]:
    payload = json.loads((root / "metadata/source_manifest.json").read_text(encoding="utf-8"))
    selected = {row["source_id"]: row for row in payload.get("sources", []) if row.get("source_id") in source_ids}
    if set(selected) != source_ids:
        raise ValueError("historical parent source is absent from the source manifest")
    for source_id, row in selected.items():
        path = (root / row["local_path"]).resolve()
        if not path.is_file() or path.stat().st_size != row["byte_size"] or _sha256(path) != row["sha256"]:
            raise ValueError(f"historical parent source bytes differ: {source_id}")
    return selected


def derive_historical_parent_relations(
    connection: duckdb.DuckDBPyConnection,
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recover omitted historical parents already declared by pinned contest rows."""
    cursor = connection.execute(
        "SELECT f.election_id, e.election_date, g.geo_id, g.geo_name, c.region_geo_id, "
        "min(c.source_id) source_id, count(*) affected_facts, count(DISTINCT c.region_geo_id) parent_count "
        "FROM fact_election_result f JOIN dim_electoral_contest c ON c.contest_id=f.contest_id "
        "JOIN dim_election e ON e.election_id=f.election_id JOIN dim_geo g ON g.geo_id=f.geo_id "
        "WHERE f.election_id IN ('LEG2007','LEG2011') AND c.region_geo_id IS NOT NULL "
        "AND g.geo_type IN ('province_prefecture_snapshot','prefecture_district') "
        "AND g.parent_geo_id IS DISTINCT FROM c.region_geo_id "
        "GROUP BY f.election_id,e.election_date,g.geo_id,g.geo_name,c.region_geo_id "
        "ORDER BY f.election_id,g.geo_id"
    )
    grouped = [
        dict(zip(("election_id", "election_date", "geo_id", "geo_name", "region_geo_id", "source_id", "affected_facts", "parent_count"), values, strict=True))
        for values in cursor.fetchall()
    ]
    if sum(int(row["affected_facts"]) for row in grouped) != 3610 or len(grouped) != 151:
        raise ValueError("historical parent diagnostic no longer matches 3,610 result facts and 151 election-territory pairs")
    if any(row["parent_count"] != 1 or row["source_id"] not in HISTORICAL_ELECTIONS | {"TAFRA_LEGISLATIVE_RESULTS_2007", "TAFRA_LEGISLATIVE_RESULTS_2011"} for row in grouped):
        raise ValueError("historical source rows do not declare one stable regional parent")
    source_ids = {str(row["source_id"]) for row in grouped}
    descriptors = _verify_manifest_sources(root, source_ids)
    relations = [
        {
            "relation_id": f"V16-PARENT:{row['election_id']}:{row['geo_id']}",
            "child_geo_id": row["geo_id"],
            "parent_geo_id": row["region_geo_id"],
            "relationship_type": "ADMINISTRATIVE_PARENT",
            "election_id": row["election_id"],
            "valid_from": row["election_date"].isoformat(),
            "valid_to": row["election_date"].isoformat(),
            "source_id": row["source_id"],
            "matching_method": "OFFICIAL_IDENTIFIER",
            "confidence": 1.0,
            "review_status": "VERIFIED_SOURCE_DERIVED",
            "supporting_source_ids": json.dumps([row["source_id"]], separators=(",", ":")),
            "notes": "Parent reproduced from the pinned source-derived contest row; this verifies source consistency, not independent official authority.",
        }
        for row in grouped
    ]
    report = {
        "cause_code": "HISTORICAL_PARENT_RELATION_OMITTED_FROM_DIM_GEO",
        "initial_snapshot_violations": 3293,
        "additional_prefecture_district_violations": 317,
        "initial_fact_election_result_violations": 3610,
        "territories": len(relations),
        "by_election": {
            election_id: {
                "affected_facts": sum(int(row["affected_facts"]) for row in grouped if row["election_id"] == election_id),
                "territories": sum(row["election_id"] == election_id for row in grouped),
                "source_id": next(row["source_id"] for row in grouped if row["election_id"] == election_id),
                "source_sha256": descriptors[next(row["source_id"] for row in grouped if row["election_id"] == election_id)]["sha256"],
            }
            for election_id in sorted(HISTORICAL_ELECTIONS)
        },
    }
    return relations, report


def _hcp_rows(workbook_path: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    units: dict[str, dict[str, str]] = {}
    parents: dict[str, dict[str, str]] = {}
    try:
        for values in workbook["Communes"].iter_rows(min_row=6, values_only=True):
            code = str(values[0] or "")
            row = {"official_code": code, "name_latin": str(values[1] or ""), "name_ar": str(values[6] or "")}
            if len(code) == 7 and code[2] == "." and code[6] == ".":
                parents[code] = row
            elif len(code) == 13 and code.endswith("."):
                units[code] = row
    finally:
        workbook.close()
    return units, parents


def derive_comm2015_parent_relations(
    root: Path,
    geographies: Iterable[Mapping[str, Any]],
    contests: Iterable[Mapping[str, Any]],
    seed: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seed = seed or json.loads((root / COMM2015_SEED_PATH).read_text(encoding="utf-8"))
    if seed.get("status") != "VERIFIED_PARENT_RELATIONS_ONLY" or seed.get("election_id") != "COMM2015":
        raise ValueError("COMM2015 parent seed has an invalid scope or review status")
    registry = json.loads((root / "metadata/v16/official_source_registry.json").read_text(encoding="utf-8"))
    source_ids = {seed[field] for field in ("annex_source_id", "code_source_id", "legal_source_id")}
    sources = [row for row in registry["sources"] if row.get("source_id") in source_ids]
    if len(sources) != len(source_ids) or validate_official_source_registry(root, {"sources": sources}):
        raise ValueError("COMM2015 parent source bytes are absent or invalid")
    hcp_source = next(row for row in sources if row["source_id"] == seed["code_source_id"])
    hcp_units, _hcp_parents = _hcp_rows(root / hcp_source["raw_path"])
    geography_by_id = {str(row.get("geo_id")): row for row in geographies}
    groups = list(seed.get("groups", []))
    group_by_id = {row.get("parent_geo_id"): row for row in groups}
    arrondissement_rows = list(seed.get("arrondissements", []))
    if len(groups) != 6 or len(group_by_id) != 6 or len(arrondissement_rows) != 41:
        raise ValueError("COMM2015 parent seed must contain six groups and 41 arrondissements")
    observed = {
        str(row.get("geo_id")) for row in contests
        if row.get("election_id") == "COMM2015" and geography_by_id.get(str(row.get("geo_id")), {}).get("geo_type") == "arrondissement"
    }
    child_ids = [str(row.get("child_geo_id")) for row in arrondissement_rows]
    official_codes = [str(row.get("official_child_code")) for row in arrondissement_rows]
    if len(set(child_ids)) != 41 or len(set(official_codes)) != 41 or set(child_ids) != observed:
        raise ValueError("COMM2015 arrondissement identifiers are missing, duplicated, or invented")
    counts: Counter[str] = Counter()
    for row in arrondissement_rows:
        code, child_id, parent_id = str(row["official_child_code"]), str(row["child_geo_id"]), str(row["parent_geo_id"])
        hcp = hcp_units.get(code)
        if hcp is None or "(Arrond.)" not in hcp["name_latin"]:
            raise ValueError(f"invented or non-arrondissement official identifier: {code}")
        expected_child = f"MA-{code[0:2]}-{code[3:6]}-{code[7:9]}{code[10:12]}"
        if child_id != expected_child or parent_id not in group_by_id:
            raise ValueError(f"official identifier or parent mutation: {child_id}")
        group = group_by_id[parent_id]
        if not code.startswith(str(group["prefecture_geo_id"])[3:].replace("-", ".") + "."):
            raise ValueError(f"arrondissement is assigned outside its official prefecture: {child_id}")
        annex_name, hcp_name = normalize_arabic(row.get("annex_name_ar")), normalize_arabic(hcp["name_ar"])
        if annex_name not in hcp_name and SequenceMatcher(None, annex_name, hcp_name).ratio() < 0.75:
            raise ValueError(f"BO annex name does not crosswalk to HCP code: {child_id}")
        counts[parent_id] += 1
    if any(counts[group["parent_geo_id"]] != group["annex_count"] for group in groups):
        raise ValueError("COMM2015 annex group count differs from explicit arrondissement rows")
    election_date = str(seed["election_date"])
    relations: list[dict[str, Any]] = []
    for row in arrondissement_rows:
        relations.append({
            "relation_id": f"V16-PARENT:COMM2015:{row['child_geo_id']}",
            "child_geo_id": row["child_geo_id"],
            "parent_geo_id": row["parent_geo_id"],
            "relationship_type": "COUNCIL_PARENT",
            "election_id": "COMM2015",
            "valid_from": election_date,
            "valid_to": election_date,
            "source_id": seed["annex_source_id"],
            "matching_method": "DOCUMENTED_CROSSWALK",
            "confidence": 1.0,
            "review_status": "VERIFIED_OFFICIAL_CROSSWALK",
            "official_child_code": row["official_child_code"],
            "supporting_source_ids": json.dumps([seed["code_source_id"], seed["legal_source_id"]], separators=(",", ":")),
            "notes": "BO 6381 annex group visually reviewed and crosswalked to the exact HCP arrondissement code; parent identity only, no polygon claim.",
        })
    for group in groups:
        prefecture = geography_by_id.get(group["prefecture_geo_id"])
        region = geography_by_id.get(group["region_geo_id"])
        if prefecture is None or prefecture.get("geo_type") != "province_prefecture" or prefecture.get("parent_geo_id") != group["region_geo_id"]:
            raise ValueError(f"invalid V15 prefecture/region chain for {group['parent_geo_id']}")
        if region is None or region.get("geo_type") != "region":
            raise ValueError(f"unknown official region for {group['parent_geo_id']}")
        relations.extend([
            {
                "relation_id": f"V16-PARENT:COMM2015:{group['parent_geo_id']}",
                "child_geo_id": group["parent_geo_id"],
                "parent_geo_id": group["prefecture_geo_id"],
                "relationship_type": "ADMINISTRATIVE_PARENT",
                "election_id": "COMM2015",
                "valid_from": election_date,
                "valid_to": election_date,
                "source_id": seed["annex_source_id"],
                "matching_method": "DOCUMENTED_CROSSWALK",
                "confidence": 1.0,
                "review_status": "VERIFIED_OFFICIAL_CROSSWALK",
                "supporting_source_ids": json.dumps([seed["code_source_id"], seed["legal_source_id"]], separators=(",", ":")),
                "notes": "Internal V16 commune-parent identifier; not asserted as an official identifier.",
            },
            {
                "relation_id": f"V16-PARENT:COMM2015:{group['prefecture_geo_id']}",
                "child_geo_id": group["prefecture_geo_id"],
                "parent_geo_id": group["region_geo_id"],
                "relationship_type": "ADMINISTRATIVE_PARENT",
                "election_id": "COMM2015",
                "valid_from": election_date,
                "valid_to": election_date,
                "source_id": seed["code_source_id"],
                "matching_method": "OFFICIAL_IDENTIFIER",
                "confidence": 1.0,
                "review_status": "VERIFIED_OFFICIAL_CROSSWALK",
                "supporting_source_ids": json.dumps([seed["annex_source_id"]], separators=(",", ":")),
                "notes": "Exact HCP administrative-code hierarchy, scoped to the COMM2015 election date.",
            },
        ])
    report = {
        "arrondissements": 41,
        "parent_communes": 6,
        "commune_prefecture_relations": 6,
        "prefecture_region_relations": 6,
        "ambiguous_relations": 0,
        "source_ids": sorted(source_ids),
    }
    return sorted(relations, key=lambda row: row["relation_id"]), report


def validate_geo_parent_relations(
    relations: Iterable[Mapping[str, Any]],
    geographies: Iterable[Mapping[str, Any]],
    elections: Iterable[Mapping[str, Any]],
) -> list[ValidationIssue]:
    rows, geographies, elections = list(relations), list(geographies), list(elections)
    issues = validate_rows("bridge_geo_parent", rows)
    geo_ids = {str(row.get("geo_id")) for row in geographies}
    internal_ids = {str(row.get("child_geo_id")) for row in rows if str(row.get("child_geo_id", "")).startswith("COMM2015-CITY:")}
    known_ids = geo_ids | internal_ids
    election_dates = {str(row.get("election_id")): _as_date(row.get("election_date")) for row in elections}
    active_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        rid = str(row.get("relation_id", "<unknown>"))
        child, parent = str(row.get("child_geo_id")), str(row.get("parent_geo_id"))
        if child not in known_ids:
            issues.append(ValidationIssue("UNKNOWN_GEO_PARENT_CHILD", "bridge_geo_parent", rid, child))
        if parent not in known_ids:
            issues.append(ValidationIssue("UNKNOWN_GEO_PARENT", "bridge_geo_parent", rid, parent))
        if child == parent:
            issues.append(ValidationIssue("SELF_GEO_PARENT", "bridge_geo_parent", rid, child))
        election_id = str(row.get("election_id"))
        election_date = election_dates.get(election_id)
        valid_from, valid_to = _as_date(row.get("valid_from")), _as_date(row.get("valid_to"))
        if election_date is None or valid_from is None or valid_from > election_date or (valid_to is not None and valid_to < election_date):
            issues.append(ValidationIssue("GEO_PARENT_NOT_APPLICABLE", "bridge_geo_parent", rid, election_id))
        key = (election_id, child, str(row.get("relationship_type")))
        if key in active_keys:
            issues.append(ValidationIssue("DUPLICATE_ACTIVE_GEO_PARENT", "bridge_geo_parent", rid, repr(key)))
        active_keys.add(key)
        if row.get("relationship_type") == "COUNCIL_PARENT":
            if parent in geo_ids and next((geo.get("geo_type") for geo in geographies if str(geo.get("geo_id")) == parent), None) == "province_prefecture":
                issues.append(ValidationIssue("ARRONDISSEMENT_DIRECT_PREFECTURE_PARENT", "bridge_geo_parent", rid, parent))
            if not parent.startswith("COMM2015-CITY:"):
                issues.append(ValidationIssue("ARRONDISSEMENT_PARENT_NOT_COMMUNE", "bridge_geo_parent", rid, parent))
    return issues


def build_geo_parent_evidence(connection: duckdb.DuckDBPyConnection, root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    geographies = _table_rows(connection, "dim_geo")
    contests = _table_rows(connection, "dim_electoral_contest")
    elections = _table_rows(connection, "dim_election")
    historical, historical_report = derive_historical_parent_relations(connection, root)
    communal, communal_report = derive_comm2015_parent_relations(root, geographies, contests)
    rows = historical + communal
    issues = validate_geo_parent_relations(rows, geographies, elections)
    if issues:
        raise ValueError("invalid V16 geo parent evidence: " + ", ".join(sorted({issue.code for issue in issues})))
    return rows, {"historical": historical_report, "comm2015": communal_report}


def geo_parent_report(
    connection: duckdb.DuckDBPyConnection,
    relations: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    relations = list(relations)
    geographies = _table_rows(connection, "dim_geo")
    elections = _table_rows(connection, "dim_election")
    contests = _table_rows(connection, "dim_electoral_contest")
    facts = [
        row for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result")
        for row in _table_rows(connection, table)
    ]
    before = sum(
        issue.code == "REGIONAL_PARENT_MISMATCH"
        for issue in validate_semantic_consistency(facts, contests, elections, geographies)
    )
    remaining_count = sum(
        issue.code == "REGIONAL_PARENT_MISMATCH"
        for issue in validate_semantic_consistency(facts, contests, elections, geographies, relations)
    )
    council = [row for row in relations if row.get("election_id") == "COMM2015" and row.get("relationship_type") == "COUNCIL_PARENT"]
    city_ids = {row["parent_geo_id"] for row in council}
    all_children = {row["child_geo_id"] for row in relations}
    all_parents = {row["parent_geo_id"] for row in relations}
    geo_ids = {row[0] for row in connection.execute("SELECT geo_id FROM dim_geo").fetchall()}
    return {
        "initial_regional_parent_mismatch": before,
        "corrected": before - remaining_count,
        "remaining": remaining_count,
        "requested_snapshot_mismatches": 3293,
        "cause_distribution": [
            {"cause_code": "HISTORICAL_PARENT_RELATION_OMITTED_FROM_DIM_GEO", "count": 3293},
            {"cause_code": "HISTORICAL_REGION_VERSION_NOT_REACHED_THROUGH_CURRENT_PREFECTURE_CHAIN", "count": before - 3293},
        ],
        "orphan_geographic_references": len((all_children | all_parents) - (geo_ids | city_ids)),
        "arrondissements_linked_to_commune": len(council),
        "distinct_parent_communes": len(city_ids),
        "ambiguous_or_insufficient_relations": sum(row.get("review_status") == "CANDIDATE" for row in relations),
        "relation_count": len(relations),
        "relationship_type_distribution": dict(sorted(Counter(str(row["relationship_type"]) for row in relations).items())),
        "matching_method_distribution": dict(sorted(Counter(str(row["matching_method"]) for row in relations).items())),
        "review_status_distribution": dict(sorted(Counter(str(row["review_status"]) for row in relations).items())),
        "confidence_distribution": dict(sorted(Counter(str(row["confidence"]) for row in relations).items())),
        "election_day_scoped_relations": sum(
            _as_date(row.get("valid_from")) == _as_date(row.get("valid_to")) for row in relations
        ),
        "official_child_codes": sum(bool(row.get("official_child_code")) for row in relations),
        "sources_used": sorted({str(row["source_id"]) for row in relations}),
    }
