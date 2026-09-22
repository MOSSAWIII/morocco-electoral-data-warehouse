from __future__ import annotations

from fractions import Fraction
from typing import Any, Iterable, Mapping

from morocco_elections.warehouse.validation import ValidationIssue, validate_rows


def reproduce_largest_remainder_allocation(
    contest_id: str,
    lists: Iterable[Mapping[str, Any]],
    *,
    seats_to_fill: int | None,
    quotient_base: int | None,
    unique_list_minimum: Fraction | None = None,
    registered_voters: int | None = None,
) -> dict[str, Any]:
    """Reproduce a quotient/largest-remainder allocation and fail closed on ambiguity."""
    rows = list(lists)
    failures: list[str] = []
    if not isinstance(seats_to_fill, int) or isinstance(seats_to_fill, bool) or seats_to_fill <= 0:
        failures.append("seats_to_fill must be a positive integer")
    if not isinstance(quotient_base, int) or isinstance(quotient_base, bool) or quotient_base <= 0:
        failures.append("quotient_base must be a positive integer")
    identifiers = [row.get("candidacy_list_id") for row in rows]
    if not rows or any(identifier is None for identifier in identifiers) or len(set(identifiers)) != len(identifiers):
        failures.append("candidacy lists must be present and uniquely identified")
    for row in rows:
        if not isinstance(row.get("votes"), int) or isinstance(row.get("votes"), bool) or row.get("votes", -1) < 0:
            failures.append(f"{row.get('candidacy_list_id', '<unknown>')}: votes must be a non-negative integer")
        if not isinstance(row.get("candidate_count"), int) or isinstance(row.get("candidate_count"), bool) or row.get("candidate_count", 0) <= 0:
            failures.append(f"{row.get('candidacy_list_id', '<unknown>')}: candidate_count must be a positive integer")
    if failures:
        return {"contest_id": contest_id, "metric_status": "NOT_COMPUTED", "allocations": [], "failed_preconditions": failures}

    assert seats_to_fill is not None and quotient_base is not None
    if sum(row["votes"] for row in rows) > quotient_base:
        failures.append("sum of list votes exceeds the sourced quotient base")
    if len(rows) == 1 and unique_list_minimum is not None:
        if not isinstance(registered_voters, int) or isinstance(registered_voters, bool) or registered_voters <= 0:
            failures.append("registered_voters is required for the unique-list minimum")
        elif Fraction(rows[0]["votes"], registered_voters) < unique_list_minimum:
            return {
                "contest_id": contest_id,
                "metric_status": "COMPUTED",
                "quotient": str(Fraction(quotient_base, seats_to_fill)),
                "allocations": [{"candidacy_list_id": identifiers[0], "recomputed_seats": 0}],
                "failed_preconditions": [],
                "explanation": "unique list did not reach the sourced minimum",
            }
    if failures:
        return {"contest_id": contest_id, "metric_status": "NOT_COMPUTED", "allocations": [], "failed_preconditions": failures}

    allocations: dict[Any, int] = {}
    remainders: dict[Any, int] = {}
    candidate_counts: dict[Any, int] = {}
    tie_break_ranks: dict[Any, Any] = {}
    for row in rows:
        identifier = row["candidacy_list_id"]
        numerator = row["votes"] * seats_to_fill
        allocations[identifier], remainders[identifier] = divmod(numerator, quotient_base)
        candidate_counts[identifier] = row["candidate_count"]
        tie_break_ranks[identifier] = row.get("tie_break_rank")
    remaining = seats_to_fill - sum(allocations.values())
    eligible = [identifier for identifier in identifiers if remainders[identifier] > 0]
    if remaining > len(eligible):
        failures.append("largest-remainder rule cannot assign every remaining seat once per eligible list")
    else:
        by_remainder: dict[int, list[Any]] = {}
        for identifier in eligible:
            by_remainder.setdefault(remainders[identifier], []).append(identifier)
        for remainder in sorted(by_remainder, reverse=True):
            group = by_remainder[remainder]
            if remaining >= len(group):
                winners = group
            elif remaining == 0:
                winners = []
            else:
                ranks = [tie_break_ranks[identifier] for identifier in group]
                if any(not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0 for rank in ranks) or len(set(ranks)) != len(ranks):
                    failures.append("a sourced unique tie_break_rank is required for a remainder tie at the allocation boundary")
                    break
                winners = sorted(group, key=lambda identifier: tie_break_ranks[identifier])[:remaining]
            for identifier in winners:
                allocations[identifier] += 1
            remaining -= len(winners)
    for identifier, seats in allocations.items():
        if seats > candidate_counts[identifier]:
            failures.append(f"{identifier}: allocated seats exceed available candidates")
    if failures:
        return {"contest_id": contest_id, "metric_status": "NOT_COMPUTED", "allocations": [], "failed_preconditions": failures}
    return {
        "contest_id": contest_id,
        "metric_status": "COMPUTED",
        "quotient": str(Fraction(quotient_base, seats_to_fill)),
        "allocations": [
            {"candidacy_list_id": identifier, "recomputed_seats": allocations[identifier]}
            for identifier in identifiers
        ],
        "failed_preconditions": [],
    }


def validate_candidacies_and_seats(
    lists: Iterable[Mapping[str, Any]],
    candidates: Iterable[Mapping[str, Any]],
    allocations: Iterable[Mapping[str, Any]],
    contests: Iterable[Mapping[str, Any]],
    regimes: Iterable[Mapping[str, Any]],
    seat_categories: Iterable[Mapping[str, Any]] = (),
) -> list[ValidationIssue]:
    lists, candidates, allocations, seat_categories = list(lists), list(candidates), list(allocations), list(seat_categories)
    issues = validate_rows("fact_candidacy_list", lists) + validate_rows("fact_candidate", candidates) + validate_rows("fact_seat_allocation", allocations)
    list_ids = {row.get("candidacy_list_id") for row in lists}
    list_by_id = {row.get("candidacy_list_id"): row for row in lists}
    contest_ids = {row.get("contest_id") for row in contests}
    regime_ids = {row.get("legal_regime_id") for row in regimes}
    category_by_id = {row.get("seat_category_id"): row for row in seat_categories}
    positions: set[tuple[Any, Any]] = set()
    for row in lists:
        if row.get("contest_id") not in contest_ids:
            issues.append(ValidationIssue("UNKNOWN_CANDIDACY_CONTEST", "fact_candidacy_list", str(row.get("candidacy_list_id")), "candidate list must reference a contest"))
    for row in candidates:
        rid = str(row.get("candidacy_id", "<unknown>"))
        if row.get("candidacy_list_id") not in list_ids:
            issues.append(ValidationIssue("UNKNOWN_CANDIDACY_LIST", "fact_candidate", rid, "candidate list does not exist"))
        position = row.get("position")
        if not isinstance(position, int) or isinstance(position, bool) or position <= 0:
            issues.append(ValidationIssue("INVALID_CANDIDATE_POSITION", "fact_candidate", rid, "position must be a positive integer"))
        key = (row.get("candidacy_list_id"), position)
        if key in positions:
            issues.append(ValidationIssue("DUPLICATE_LIST_POSITION", "fact_candidate", rid, "candidate position must be unique within a list"))
        positions.add(key)
    for row in allocations:
        rid = str(row.get("allocation_id", "<unknown>"))
        candidacy_list = list_by_id.get(row.get("candidacy_list_id"))
        if candidacy_list is None:
            issues.append(ValidationIssue("UNKNOWN_ALLOCATION_LIST", "fact_seat_allocation", rid, "seat must reference a candidacy list"))
        elif candidacy_list.get("contest_id") != row.get("contest_id"):
            issues.append(ValidationIssue("ALLOCATION_LIST_CONTEST_MISMATCH", "fact_seat_allocation", rid, "allocation contest differs from candidacy-list contest"))
        if row.get("contest_id") not in contest_ids:
            issues.append(ValidationIssue("UNKNOWN_ALLOCATION_CONTEST", "fact_seat_allocation", rid, "seat must reference a contest"))
        if row.get("legal_regime_id") not in regime_ids:
            issues.append(ValidationIssue("UNKNOWN_ALLOCATION_RULE", "fact_seat_allocation", rid, "seat must reference a legal rule"))
        category = category_by_id.get(row.get("seat_category_id"))
        if seat_categories and category is None:
            issues.append(ValidationIssue("UNKNOWN_SEAT_CATEGORY", "fact_seat_allocation", rid, "seat category does not exist"))
        elif category is not None and category.get("legal_regime_id") != row.get("legal_regime_id"):
            issues.append(ValidationIssue("SEAT_CATEGORY_REGIME_MISMATCH", "fact_seat_allocation", rid, "seat category belongs to another legal regime"))
        official, recomputed = row.get("official_seats"), row.get("recomputed_seats")
        if not isinstance(official, int) or isinstance(official, bool) or official < 0:
            issues.append(ValidationIssue("INVALID_OFFICIAL_SEATS", "fact_seat_allocation", rid, "official_seats must be a non-negative integer"))
            continue
        if recomputed is None:
            expected_status, expected_difference = "NOT_COMPUTABLE", None
        elif not isinstance(recomputed, int) or isinstance(recomputed, bool) or recomputed < 0:
            issues.append(ValidationIssue("INVALID_RECOMPUTED_SEATS", "fact_seat_allocation", rid, "recomputed_seats must be a non-negative integer or null"))
            continue
        else:
            expected_difference = recomputed - official
            expected_status = "PASS" if expected_difference == 0 else "FAIL"
        if row.get("validation_status") != expected_status:
            issues.append(ValidationIssue("ALLOCATION_STATUS_MISMATCH", "fact_seat_allocation", rid, f"validation_status must be {expected_status}"))
        if row.get("difference") is not None and row.get("difference") != expected_difference:
            issues.append(ValidationIssue("ALLOCATION_DIFFERENCE_MISMATCH", "fact_seat_allocation", rid, f"difference must be {expected_difference!r}"))
        if expected_status in {"FAIL", "NOT_COMPUTABLE"} and not row.get("difference_explanation"):
            issues.append(ValidationIssue("UNEXPLAINED_SEAT_DIFFERENCE", "fact_seat_allocation", rid, "unresolved difference must be retained and documented"))
    return issues
