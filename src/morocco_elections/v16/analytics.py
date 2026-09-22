from __future__ import annotations

from math import isfinite, sqrt
from typing import Any, Iterable, Mapping, Sequence


def _metric(name: str, value: float | None, formula: str, denominator: str, scope: str, coverage_status: str, limitations: Sequence[str], failed: Sequence[str]) -> dict[str, Any]:
    return {
        "metric_name": name, "value": value, "formula": formula, "denominator": denominator,
        "scope": scope, "metric_status": "NOT_COMPUTED" if failed else "COMPUTED",
        "coverage_status": coverage_status, "limitations": list(limitations), "failed_preconditions": list(failed),
    }


def regional_party_shares(
    rows: Iterable[Mapping[str, Any]],
    expected_geo_ids_by_region: Mapping[Any, Iterable[Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return both the regional electorate-weighted share and explicitly named commune mean."""
    groups: dict[tuple[Any, Any], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["region_geo_id"], row["party_id"]), []).append(row)
    output = []
    for (region, party), values in sorted(groups.items(), key=lambda item: tuple(map(str, item[0]))):
        expected = (
            {str(identifier) for identifier in expected_geo_ids_by_region.get(region, ())}
            if expected_geo_ids_by_region is not None and region in expected_geo_ids_by_region
            else None
        )
        observed = [str(row["geo_id"]) for row in values if row.get("geo_id") is not None]
        vector_complete = all(row.get("party_votes") is not None and row.get("valid_votes") not in (None, 0) for row in values)
        universe_complete = expected is not None and set(observed) == expected and len(observed) == len(values) == len(set(observed))
        complete = vector_complete and universe_complete
        votes = sum(float(row["party_votes"]) for row in values) if complete else None
        valid = sum(float(row["valid_votes"]) for row in values) if complete else None
        commune_shares = [float(row["party_votes"]) / float(row["valid_votes"]) for row in values] if complete else []
        failed = []
        if not vector_complete:
            failed.append("INCOMPLETE_COMMUNE_VECTOR")
        if expected is None:
            failed.append("UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR")
        elif not universe_complete:
            failed.append("OBSERVED_COMMUNES_DO_NOT_MATCH_EXPECTED_UNIVERSE")
        output.append({
            "region_geo_id": region, "party_id": party,
            "regional_weighted_vote_share": votes / valid if votes is not None and valid else None,
            "commune_unweighted_mean_vote_share": sum(commune_shares) / len(commune_shares) if commune_shares else None,
            "party_votes": votes, "valid_votes": valid, "observed_communes": len(set(observed)),
            "expected_communes": len(expected) if expected is not None else None,
            "coverage_status": "COMPLETE" if universe_complete else "PARTIAL" if expected is not None else "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR",
            "metric_status": "COMPUTED" if complete else "NOT_COMPUTED",
            "failed_preconditions": failed,
        })
    return output


def concentration(shares: Sequence[float], *, scope: str, coverage_status: str, tolerance: float = 1e-6) -> dict[str, dict[str, Any]]:
    failed = []
    if not shares or any(not isfinite(value) or value < 0 or value > 1 for value in shares):
        failed.append("SHARES_OUT_OF_RANGE_OR_EMPTY")
    if shares and abs(sum(shares) - 1) > tolerance:
        failed.append("SHARES_DO_NOT_SUM_TO_ONE")
    if coverage_status != "COMPLETE":
        failed.append("INCOMPLETE_COVERAGE")
    hhi = None if failed else sum(value * value for value in shares)
    return {
        "hhi": _metric("HHI", hhi, "SUM(p_i^2)", "complete vote-share distribution", scope, coverage_status, ["Descriptive fragmentation only; no fraud inference."], failed),
        "enep": _metric("ENEP", 1 / hhi if hhi else None, "1 / HHI_votes", "complete vote-share distribution", scope, coverage_status, ["Comparable party identities and geography required."], failed),
    }


def gallagher(vote_shares: Sequence[float], seat_shares: Sequence[float], *, scope: str, coverage_status: str, comparable: bool, tolerance: float = 1e-6) -> dict[str, Any]:
    failed = []
    if len(vote_shares) != len(seat_shares) or not vote_shares:
        failed.append("PARTY_VECTORS_NOT_ALIGNED")
    if any(not isfinite(value) or value < 0 or value > 1 for value in (*vote_shares, *seat_shares)):
        failed.append("SHARES_OUT_OF_RANGE_OR_NON_FINITE")
    if vote_shares and (abs(sum(vote_shares) - 1) > tolerance or abs(sum(seat_shares) - 1) > tolerance):
        failed.append("SHARES_DO_NOT_SUM_TO_ONE")
    if not comparable:
        failed.append("PARTIES_OR_SCOPE_NOT_COMPARABLE")
    if coverage_status != "COMPLETE":
        failed.append("INCOMPLETE_COVERAGE")
    value = None if failed else sqrt(0.5 * sum((s - v) ** 2 for v, s in zip(vote_shares, seat_shares, strict=True)))
    return _metric("GALLAGHER", value, "SQRT(0.5 * SUM((seat_share - vote_share)^2))", "complete aligned vote and seat shares", scope, coverage_status, ["Descriptive disproportionality; not a causal or fraud score."], failed)


def effective_parliamentary_parties(seat_shares: Sequence[float], *, scope: str, coverage_status: str) -> dict[str, Any]:
    result = concentration(seat_shares, scope=scope, coverage_status=coverage_status)["enep"]
    return {**result, "metric_name": "ENPP", "formula": "1 / SUM(seat_share_i^2)", "denominator": "complete seat-share distribution"}


def volatility(previous: Mapping[str, float], current: Mapping[str, float], *, scope: str, coverage_status: str, boundary_compatible: bool, lineage_reviewed: bool) -> dict[str, Any]:
    failed = []
    if set(previous) != set(current):
        failed.append("PARTY_VECTORS_NOT_ALIGNED")
    if any(not isfinite(value) or value < 0 or value > 1 for value in (*previous.values(), *current.values())):
        failed.append("SHARES_OUT_OF_RANGE_OR_NON_FINITE")
    if abs(sum(previous.values()) - 1) > 1e-6 or abs(sum(current.values()) - 1) > 1e-6:
        failed.append("SHARES_DO_NOT_SUM_TO_ONE")
    if not boundary_compatible:
        failed.append("BOUNDARY_NOT_COMPARABLE")
    if not lineage_reviewed:
        failed.append("PARTY_LINEAGE_NOT_REVIEWED")
    if coverage_status != "COMPLETE":
        failed.append("INCOMPLETE_COVERAGE")
    value = None if failed else 0.5 * sum(abs(current[key] - previous[key]) for key in current)
    return _metric("PEDERSEN_VOLATILITY", value, "0.5 * SUM(ABS(p_i,t - p_i,t-1))", "aligned party vote shares in two elections", scope, coverage_status, ["Requires identical or crosswalked boundaries and reviewed party lineages."], failed)


def observed_published_question_rate(published_questions: int, observed_mandate_days: int) -> float | None:
    """Rate for the observed published corpus, never an official activity rate."""
    return None if observed_mandate_days <= 0 else published_questions * 100 / observed_mandate_days


def unique_parliamentary_grain(rows: Iterable[Mapping[str, Any]]) -> bool:
    keys = [(row.get("person_id"), row.get("period_id"), row.get("question_type")) for row in rows]
    return len(keys) == len(set(keys))
