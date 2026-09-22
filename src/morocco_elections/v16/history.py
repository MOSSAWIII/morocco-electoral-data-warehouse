from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

from morocco_elections.v16.validation import ValidationIssue, _as_date, validate_rows


def affiliation_at_date(rows: Iterable[Mapping[str, Any]], person_id: str, on_date: date | str) -> list[Mapping[str, Any]]:
    when = _as_date(on_date)
    if when is None:
        raise ValueError("on_date must be an ISO date")
    return [
        row for row in rows
        if row.get("person_id") == person_id
        and (start := _as_date(row.get("valid_from"))) is not None
        and start <= when
        and ((end := _as_date(row.get("valid_to"))) is None or when <= end)
    ]


def validate_party_history(
    versions: Iterable[Mapping[str, Any]],
    lineages: Iterable[Mapping[str, Any]],
    affiliations: Iterable[Mapping[str, Any]],
) -> list[ValidationIssue]:
    versions, lineages, affiliations = list(versions), list(lineages), list(affiliations)
    issues = (
        validate_rows("dim_party_version", versions)
        + validate_rows("bridge_party_lineage", lineages)
        + validate_rows("bridge_person_party_affiliation", affiliations)
    )
    version_by_id = {row.get("party_version_id"): row for row in versions}
    party_ids = {row.get("party_id") for row in versions}
    by_party: dict[Any, list[Mapping[str, Any]]] = {}
    for row in versions:
        by_party.setdefault(row.get("party_id"), []).append(row)
    for party_id, party_versions in by_party.items():
        ordered = sorted(party_versions, key=lambda row: _as_date(row.get("valid_from")) or date.min)
        for previous, current in zip(ordered, ordered[1:]):
            previous_end = _as_date(previous.get("valid_to")) or date.max
            current_start = _as_date(current.get("valid_from")) or date.min
            if current_start <= previous_end:
                issues.append(ValidationIssue("OVERLAPPING_PARTY_VERSIONS", "dim_party_version", str(party_id), "party versions must not overlap"))
    for row in affiliations:
        rid = str(row.get("affiliation_id", "<unknown>"))
        version = version_by_id.get(row.get("party_version_id"))
        if version is None:
            issues.append(ValidationIssue("UNKNOWN_AFFILIATION_PARTY_VERSION", "bridge_person_party_affiliation", rid, str(row.get("party_version_id"))))
            continue
        if version.get("party_id") != row.get("party_id"):
            issues.append(ValidationIssue("AFFILIATION_PARTY_VERSION_MISMATCH", "bridge_person_party_affiliation", rid, "party_version_id belongs to another party"))
        affiliation_start, affiliation_end = _as_date(row.get("valid_from")), _as_date(row.get("valid_to")) or date.max
        version_start, version_end = _as_date(version.get("valid_from")), _as_date(version.get("valid_to")) or date.max
        if affiliation_start is None or version_start is None or affiliation_start < version_start or affiliation_end > version_end:
            issues.append(ValidationIssue("AFFILIATION_OUTSIDE_PARTY_VERSION", "bridge_person_party_affiliation", rid, "affiliation interval is outside its party version"))
    successors: dict[Any, list[Any]] = {}
    for row in lineages:
        rid = str(row.get("lineage_id", "<unknown>"))
        predecessor, successor = row.get("predecessor_party_id"), row.get("successor_party_id")
        if predecessor not in party_ids or successor not in party_ids:
            issues.append(ValidationIssue("UNKNOWN_LINEAGE_PARTY", "bridge_party_lineage", rid, "lineage endpoints must exist"))
        successors.setdefault(predecessor, []).append(successor)
    visiting: set[Any] = set()
    visited: set[Any] = set()

    def visit(party_id: Any) -> bool:
        if party_id in visiting:
            return True
        if party_id in visited:
            return False
        visiting.add(party_id)
        cyclic = any(visit(successor) for successor in successors.get(party_id, ()))
        visiting.remove(party_id)
        visited.add(party_id)
        return cyclic

    for start in successors:
        if start not in visited and visit(start):
            issues.append(ValidationIssue("CYCLIC_PARTY_LINEAGE", "bridge_party_lineage", str(start), "party lineage contains a cycle"))
    return issues


def validate_geo_history(versions: Iterable[Mapping[str, Any]], lineages: Iterable[Mapping[str, Any]]) -> list[ValidationIssue]:
    versions, lineages = list(versions), list(lineages)
    issues = validate_rows("dim_geo_version", versions) + validate_rows("bridge_geo_lineage", lineages)
    version_ids = {row.get("geo_version_id") for row in versions}
    by_geo: dict[Any, list[Mapping[str, Any]]] = {}
    for row in versions:
        by_geo.setdefault(row.get("geo_id"), []).append(row)
    for geo_id, geo_versions in by_geo.items():
        ordered = sorted(geo_versions, key=lambda row: _as_date(row.get("valid_from")) or date.min)
        for previous, current in zip(ordered, ordered[1:]):
            previous_end = _as_date(previous.get("valid_to")) or date.max
            current_start = _as_date(current.get("valid_from")) or date.min
            if current_start <= previous_end:
                issues.append(ValidationIssue("OVERLAPPING_GEO_VERSIONS", "dim_geo_version", str(geo_id), "geography versions must not overlap"))
    for row in lineages:
        rid = str(row.get("geo_lineage_id", "<unknown>"))
        if row.get("from_geo_version_id") not in version_ids or row.get("to_geo_version_id") not in version_ids:
            issues.append(ValidationIssue("UNKNOWN_GEO_VERSION", "bridge_geo_lineage", rid, "lineage endpoints must exist"))
        confidence = row.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            issues.append(ValidationIssue("INVALID_CROSSWALK_CONFIDENCE", "bridge_geo_lineage", rid, "confidence must be between 0 and 1"))
    return issues


def validate_result_geographies(
    revisions: Iterable[Mapping[str, Any]],
    versions: Iterable[Mapping[str, Any]],
    elections: Iterable[Mapping[str, Any]],
) -> list[ValidationIssue]:
    """Require the exact geography version applicable on election day."""
    version_by_id = {row.get("geo_version_id"): row for row in versions}
    election_by_id = {row.get("election_id"): row for row in elections}
    issues: list[ValidationIssue] = []
    for row in revisions:
        rid = str(row.get("revision_id", "<unknown>"))
        version = version_by_id.get(row.get("geo_version_id"))
        if version is None:
            issues.append(ValidationIssue("UNKNOWN_RESULT_GEO_VERSION", "fact_result_revision", rid, str(row.get("geo_version_id"))))
            continue
        if version.get("geo_id") != row.get("geo_id"):
            issues.append(ValidationIssue("RESULT_GEO_VERSION_MISMATCH", "fact_result_revision", rid, "geo_version_id belongs to another geo_id"))
        election = election_by_id.get(row.get("election_id"))
        election_date = _as_date(election.get("election_date")) if election else None
        start, end = _as_date(version.get("valid_from")), _as_date(version.get("valid_to"))
        if election_date is None:
            issues.append(ValidationIssue("UNKNOWN_RESULT_ELECTION_DATE", "fact_result_revision", rid, str(row.get("election_id"))))
        elif start is None or election_date < start or (end is not None and election_date > end):
            issues.append(ValidationIssue("GEO_VERSION_NOT_APPLICABLE", "fact_result_revision", rid, "geography version is not valid on election day"))
    return issues


def geographies_comparable(from_version_id: str, to_version_id: str, lineages: Iterable[Mapping[str, Any]], *, direct: bool = True) -> bool:
    if from_version_id == to_version_id:
        return True
    links = [row for row in lineages if row.get("from_geo_version_id") == from_version_id and row.get("to_geo_version_id") == to_version_id]
    if direct:
        return any(row.get("geo_lineage_type") == "SAME_BOUNDARY" and row.get("confidence") == 1 for row in links)
    return any(row.get("method") and row.get("source_id") and isinstance(row.get("confidence"), (int, float)) for row in links)
