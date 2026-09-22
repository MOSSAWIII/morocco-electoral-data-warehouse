from __future__ import annotations

from typing import Any, Iterable, Mapping

from morocco_elections.warehouse.validation import ValidationIssue, validate_rows


DIMENSIONS = ("ACQUIRED", "OFFICIAL", "TERRITORIAL", "TEMPORAL", "DOCUMENTARY", "FIELD")
UNKNOWN = "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR"


def validate_universes(rows: Iterable[Mapping[str, Any]]) -> list[ValidationIssue]:
    rows = list(rows)
    issues = validate_rows("coverage_universe", rows)
    seen_scopes: set[tuple[Any, Any]] = set()
    for row in rows:
        rid = str(row.get("universe_id", "<unknown>"))
        scope = (row.get("election_id"), row.get("coverage_dimension"))
        if scope in seen_scopes:
            issues.append(ValidationIssue("DUPLICATE_UNIVERSE_SCOPE", "coverage_universe", rid, "one universe is allowed per election and coverage dimension"))
        seen_scopes.add(scope)
        if row.get("denominator", 0) < 0:
            issues.append(ValidationIssue("NEGATIVE_DENOMINATOR", "coverage_universe", rid, "denominator must be non-negative"))
        if row.get("is_external") is not True:
            issues.append(ValidationIssue("SELF_REFERENTIAL_UNIVERSE_FORBIDDEN", "coverage_universe", rid, "national completeness requires an external official universe"))
        if not str(row.get("source_url", "")).startswith(("https://", "http://")):
            issues.append(ValidationIssue("UNIVERSE_SOURCE_URL_REQUIRED", "coverage_universe", rid, "an auditable source URL is required"))
    return issues


def coverage_report(
    observations: Iterable[Mapping[str, Any]],
    universes: Iterable[Mapping[str, Any]],
    members: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Compare observed identifiers to explicit official sets, never just row counts."""
    observations, universes, members = list(observations), list(universes), list(members)
    verified_universes = [
        row for row in universes
        if row.get("verification_status") == "VERIFIED" and row.get("is_external") is True
    ]
    members_by_universe: dict[Any, set[str]] = {}
    for row in members:
        members_by_universe.setdefault(row.get("universe_id"), set()).add(str(row.get("expected_id")))

    def observation_id(row: Mapping[str, Any]) -> str | None:
        for field in ("expected_id", "observation_id", "contest_id", "geo_id", "document_id", "field_id", "period_id"):
            if row.get(field) is not None:
                return str(row[field])
        return None

    result = []
    for dimension in DIMENSIONS:
        dimension_rows = [row for row in observations if str(row.get("coverage_dimension", "ACQUIRED")) == dimension]
        scoped_universes = [row for row in verified_universes if row.get("coverage_dimension") == dimension]
        if not scoped_universes:
            unidentified = sum(observation_id(row) is None for row in dimension_rows)
            identified = {identifier for row in dimension_rows if (identifier := observation_id(row)) is not None}
            result.append({
                "coverage_dimension": dimension, "numerator": len(identified), "denominator": None, "status": UNKNOWN,
                "universe_id": None, "covered_ids": [], "missing_ids": [], "unexpected_ids": sorted(identified),
                "non_comparable_ids": [], "redistribution_forbidden_ids": [], "unidentified_observations": unidentified,
            })
            continue
        valid = all(
            isinstance(row.get("denominator"), int)
            and not isinstance(row.get("denominator"), bool)
            and row.get("denominator") == len(members_by_universe.get(row.get("universe_id"), set()))
            for row in scoped_universes
        )
        if not valid:
            result.append({
                "coverage_dimension": dimension, "numerator": 0, "denominator": None, "status": UNKNOWN,
                "universe_id": [row.get("universe_id") for row in scoped_universes], "covered_ids": [], "missing_ids": [],
                "unexpected_ids": [], "non_comparable_ids": [], "redistribution_forbidden_ids": [], "unidentified_observations": len(dimension_rows),
            })
            continue
        multiple = len(scoped_universes) > 1

        def label(key: tuple[str, str]) -> str:
            return f"{key[0]}::{key[1]}" if multiple else key[1]

        expected = {
            (str(universe.get("election_id")), identifier)
            for universe in scoped_universes
            for identifier in members_by_universe.get(universe.get("universe_id"), set())
        }
        denominator = sum(int(row["denominator"]) for row in scoped_universes)
        identified: set[tuple[str, str]] = set()
        forbidden: set[tuple[str, str]] = set()
        non_comparable: set[tuple[str, str]] = set()
        unidentified = 0
        for row in dimension_rows:
            identifier = observation_id(row)
            election_id = row.get("election_id")
            if election_id is None and len(scoped_universes) == 1:
                election_id = scoped_universes[0].get("election_id")
            if identifier is None or election_id is None:
                unidentified += 1
                continue
            key = (str(election_id), identifier)
            identified.add(key)
            if row.get("redistribution_forbidden") is True:
                forbidden.add(key)
            elif row.get("comparability_status") == "NOT_COMPARABLE":
                non_comparable.add(key)
        observed = identified - non_comparable - forbidden
        covered = observed & expected
        expected_non_comparable = non_comparable & expected
        expected_forbidden = forbidden & expected
        missing = expected - covered - expected_non_comparable - expected_forbidden
        unexpected = identified - expected
        complete = not missing and not unexpected and not expected_non_comparable and not expected_forbidden and unidentified == 0
        status = "COMPLETE" if complete else "EMPTY" if not observed and denominator > 0 else "PARTIAL"
        result.append({
            "coverage_dimension": dimension, "numerator": len(covered), "denominator": denominator, "status": status,
            "universe_id": scoped_universes[0]["universe_id"] if not multiple else [row["universe_id"] for row in scoped_universes],
            "covered_ids": sorted(label(key) for key in covered), "missing_ids": sorted(label(key) for key in missing),
            "unexpected_ids": sorted(label(key) for key in unexpected), "non_comparable_ids": sorted(label(key) for key in expected_non_comparable),
            "redistribution_forbidden_ids": sorted(label(key) for key in expected_forbidden),
            "unidentified_observations": unidentified,
        })
    return result
