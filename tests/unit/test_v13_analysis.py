from __future__ import annotations

import pytest

from morocco_elections.analysis.v13 import summarize


def _fixture() -> tuple[list[dict], list[dict], list[dict]]:
    contests = [
        {
            "contest_id": "C1",
            "election_id": "E1",
            "list_type": "locale",
            "identity_review_status": "boundary_bridge_required",
        },
        {
            "contest_id": "C2",
            "election_id": "E1",
            "list_type": "regionale",
            "identity_review_status": "automatic",
        },
    ]
    results = [
        {"contest_id": "C1", "election_id": "E1", "party_id": "P1", "votes": 60},
        {"contest_id": "C1", "election_id": "E1", "party_id": "P2", "votes": 40},
        {"contest_id": "C2", "election_id": "E1", "party_id": "P1", "votes": 20},
        {"contest_id": "C2", "election_id": "E1", "party_id": "P2", "votes": 20},
    ]
    mobilization = [
        {
            "contest_id": "C1",
            "registered_voters": 200,
            "turnout_rate": 0.5,
            "valid_votes": None,
            "invalid_vote_rate": 0.1,
        },
        {
            "contest_id": "C2",
            "registered_voters": None,
            "turnout_rate": 0.6,
            "valid_votes": 40,
            "invalid_vote_rate": None,
        },
    ]
    return contests, results, mobilization


def test_analysis_separates_list_types_and_preserves_denominator_coverage() -> None:
    report = summarize(*_fixture())
    assert report["counts"] == {
        "contests": 2,
        "results": 4,
        "mobilization": 2,
        "elections": 1,
        "analysis_scopes": 2,
    }
    scopes = {item["scope_id"]: item for item in report["coverage_by_election_and_list_type"]}
    assert scopes["E1|locale"]["observed_votes"] == 100
    assert scopes["E1|locale"]["registered_voters_available"] == 1
    assert scopes["E1|locale"]["historical_boundary_contests"] == 1
    assert scopes["E1|regionale"]["observed_votes"] == 40
    assert scopes["E1|regionale"]["valid_votes_available"] == 1
    assert report["competition"]["E1|locale"]["mean_enp_observed_votes"] == 1.9231
    assert report["competition"]["E1|regionale"]["top_vote_ties"] == 1


def test_top_parties_are_ranked_within_scope_only() -> None:
    report = summarize(*_fixture())
    assert report["top_parties_by_observed_votes"]["E1|locale"][0] == {
        "party_id": "P1",
        "observed_votes": 60,
    }
    assert report["top_parties_by_observed_votes"]["E1|regionale"][0]["observed_votes"] == 20


def test_analysis_rejects_duplicate_fact_grain() -> None:
    contests, results, mobilization = _fixture()
    results.append(dict(results[0]))
    with pytest.raises(ValueError, match="grain"):
        summarize(contests, results, mobilization)
