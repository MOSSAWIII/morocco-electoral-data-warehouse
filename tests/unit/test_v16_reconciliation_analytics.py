from __future__ import annotations

import pytest

from morocco_elections.v16.analytics import (
    concentration, effective_parliamentary_parties, gallagher, observed_published_question_rate,
    regional_party_shares, unique_parliamentary_grain, volatility,
)
from morocco_elections.v16.reconciliation import reconcile_detail_to_aggregate, recompute_contest


def test_full_contest_reconciliation_preserves_official_and_recomputed_values() -> None:
    mobilization = {"registered_voters": 200, "voters": 120, "valid_votes": 100, "invalid_votes": 15, "blank_votes": 5, "contest_seats": 3, "turnout_rate": 0.6, "hhi": 0.52, "enp": 1 / 0.52, "winner_party_id": "A", "victory_margin_votes": 20, "victory_margin_share": 0.2}
    parties = [
        {"party_id": "A", "votes": 60, "seats": 2, "vote_share": 0.6, "rank": 1, "winner_flag": True},
        {"party_id": "B", "votes": 40, "seats": 1, "vote_share": 0.4, "rank": 2, "winner_flag": False},
    ]
    result = recompute_contest("C1", mobilization, parties, expected_party_ids=["A", "B"])
    assert all({"official_value", "recomputed_value", "difference", "tolerance", "validation_status"} <= row.keys() for row in result["reconciliations"])
    assert all(row["validation_status"] == "PASS" for row in result["reconciliations"])
    assert [row["recomputed_rank"] for row in result["party_results"]] == [1, 2]
    assert result["party_results"][0]["recomputed_winner"] is True
    assert result["recomputed"]["hhi"] == 0.52
    assert result["recomputed"]["enp"] == 1 / 0.52
    assert result["recomputed"]["winner_party_id"] == "A"
    assert result["recomputed"]["margin_votes"] == 20
    assert result["recomputed"]["margin_share"] == pytest.approx(0.2)


def test_mismatch_is_exposed_without_overwriting_official_value() -> None:
    result = recompute_contest("C1", {"voters": 100, "valid_votes": 90, "invalid_votes": 5, "blank_votes": 5, "contest_seats": 2}, [{"party_id": "A", "votes": 80, "seats": 1}], expected_party_ids=["A"])
    votes_check = result["reconciliations"][0]
    assert votes_check["official_value"] == 90
    assert votes_check["recomputed_value"] == 80
    assert votes_check["difference"] == -10
    assert votes_check["validation_status"] == "FAIL"
    detail = reconcile_detail_to_aggregate("C1", [{"votes": 5, "seats": 1}, {"votes": 7, "seats": 1}], {"votes": 13, "seats": 2})
    assert [row["validation_status"] for row in detail] == ["FAIL", "PASS"]


def test_missing_party_values_never_become_zero_or_partial_totals() -> None:
    result = recompute_contest(
        "C1",
        {"valid_votes": 100, "contest_seats": 3},
        [{"party_id": "A", "votes": 60, "seats": 2}, {"party_id": "B", "votes": None, "seats": None}],
        expected_party_ids=["A", "B"],
    )
    checks = {row["metric"]: row for row in result["reconciliations"]}
    assert checks["party_votes_vs_valid_votes"]["recomputed_value"] is None
    assert checks["party_votes_vs_valid_votes"]["validation_status"] == "NOT_COMPUTABLE"
    assert checks["allocated_seats_vs_contest_seats"]["recomputed_value"] is None
    assert checks["allocated_seats_vs_contest_seats"]["validation_status"] == "NOT_COMPUTABLE"
    assert result["party_results"] == []
    assert result["recomputed"]["hhi"] is None
    detail = reconcile_detail_to_aggregate("C1", [{"votes": 5}, {"votes": None}], {"votes": 5}, metrics=("votes",))
    assert detail[0]["recomputed_value"] is None
    assert detail[0]["validation_status"] == "NOT_COMPUTABLE"


def test_party_totals_fail_closed_without_complete_expected_identifier_set() -> None:
    mobilization = {"valid_votes": 100, "contest_seats": 2, "hhi": 1.0}
    rows = [{"party_id": "A", "votes": 100, "seats": 2}]
    for expected in (None, ["A", "B"], ["A", "A"]):
        result = recompute_contest("C", mobilization, rows, expected_party_ids=expected)
        checks = {row["metric"]: row for row in result["reconciliations"]}
        assert result["party_vector_status"] == "NOT_COMPUTABLE_WITHOUT_COMPLETE_PARTY_UNIVERSE"
        assert checks["party_votes_vs_valid_votes"]["validation_status"] == "NOT_COMPUTABLE"
        assert checks["party_votes_vs_valid_votes"]["recomputed_value"] is None
        assert checks["allocated_seats_vs_contest_seats"]["validation_status"] == "NOT_COMPUTABLE"
        assert checks["hhi"]["validation_status"] == "NOT_COMPUTABLE"
        assert result["party_results"] == []


def test_ballot_categories_require_an_explicit_compatible_accounting_rule() -> None:
    with pytest.raises(ValueError, match="must not be silently merged"):
        recompute_contest("C", {}, [], ballot_accounting_rule="MIXED_UNKNOWN_DEFINITIONS")


def test_weighted_regional_share_is_not_commune_mean() -> None:
    rows = [
        {"geo_id": "C1", "region_geo_id": "R", "party_id": "P", "party_votes": 90, "valid_votes": 100},
        {"geo_id": "C2", "region_geo_id": "R", "party_id": "P", "party_votes": 0, "valid_votes": 10},
    ]
    result = regional_party_shares(rows, {"R": {"C1", "C2"}})[0]
    assert result["regional_weighted_vote_share"] == 90 / 110
    assert result["commune_unweighted_mean_vote_share"] == 0.45
    incomplete = regional_party_shares([*rows, {"geo_id": "C3", "region_geo_id": "R", "party_id": "P", "party_votes": None, "valid_votes": 20}], {"R": {"C1", "C2", "C3"}})[0]
    assert incomplete["metric_status"] == "NOT_COMPUTED"
    assert incomplete["regional_weighted_vote_share"] is None
    assert incomplete["commune_unweighted_mean_vote_share"] is None
    unknown = regional_party_shares(rows)[0]
    assert unknown["metric_status"] == "NOT_COMPUTED"
    assert unknown["coverage_status"] == "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR"


def test_scientific_metrics_fail_closed_when_preconditions_fail() -> None:
    assert concentration([0.6, 0.3], scope="national", coverage_status="COMPLETE")["hhi"]["value"] is None
    assert gallagher([0.6, 0.4], [0.5, 0.5], scope="national", coverage_status="PARTIAL", comparable=True)["metric_status"] == "NOT_COMPUTED"
    assert effective_parliamentary_parties([0.5, 0.5], scope="national", coverage_status="COMPLETE")["value"] == 2
    assert volatility({"A": 0.5, "B": 0.5}, {"A": 0.4, "B": 0.6}, scope="same", coverage_status="COMPLETE", boundary_compatible=False, lineage_reviewed=True)["value"] is None
    assert concentration([float("nan")], scope="national", coverage_status="COMPLETE")["hhi"]["value"] is None
    assert gallagher([float("inf")], [1.0], scope="national", coverage_status="COMPLETE", comparable=True)["value"] is None
    assert volatility({"A": 1.0}, {"A": float("nan")}, scope="same", coverage_status="COMPLETE", boundary_compatible=True, lineage_reviewed=True)["value"] is None


def test_parliamentary_metric_names_observed_corpus_and_grain_is_unique() -> None:
    assert observed_published_question_rate(10, 20) == 50
    rows = [{"person_id": "P", "period_id": "T", "question_type": "WRITTEN"}]
    assert unique_parliamentary_grain(rows)
    assert not unique_parliamentary_grain(rows * 2)
