from __future__ import annotations

import copy

from morocco_elections.research.electoral_qualification import (
    build_qualification,
    render_report,
    validate_qualification,
)


def test_grouped_qualification_has_closed_binary_gates() -> None:
    result = build_qualification("2026-09-10")
    assert result["counts"]["go_sources"] == 6
    assert result["counts"]["no_go_sources"] == 1
    assert {item["decision"] for item in result["measure_decisions"]} == {"GO", "NO_GO"}
    archive = next(item for item in result["source_decisions"] if item["election_id"] == "LEG2002")
    assert archive["decision"] == "NO_GO"
    assert not [
        item
        for item in result["measure_decisions"]
        if item["election_id"] == "LEG2002" and item["decision"] == "GO"
    ]


def test_missing_denominators_and_historical_boundaries_remain_restricted() -> None:
    result = build_qualification("2026-09-10")
    measures = {(item["election_id"], item["measure_id"]): item["decision"] for item in result["measure_decisions"]}
    assert measures[("LEG2007", "registered_voters")] == "GO"
    assert measures[("LEG2021", "registered_voters")] == "NO_GO"
    assert measures[("REG2015", "valid_votes")] == "GO"
    assert measures[("REG2021", "invalid_vote_rate")] == "NO_GO"
    historical = next(item for item in result["source_decisions"] if item["election_id"] == "LEG2011")
    assert any("découpage historique" in restriction for restriction in historical["restrictions"])


def test_validator_rejects_unmotivated_or_non_binary_decision() -> None:
    result = build_qualification("2026-09-10")
    broken = copy.deepcopy(result)
    broken["measure_decisions"][0]["decision"] = "PARTIAL"
    broken["measure_decisions"][0]["reason"] = ""
    errors = validate_qualification(broken)
    assert any("vocabulaire" in error for error in errors)
    assert any("motivée" in error for error in errors)


def test_qualification_and_report_are_deterministic() -> None:
    first = build_qualification("2026-09-10")
    second = build_qualification("2026-09-10")
    assert first == second
    assert render_report(first) == render_report(second)
