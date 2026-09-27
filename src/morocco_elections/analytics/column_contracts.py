from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnContract:
    unit: str
    meaning: str
    nullable: bool
    calculation: str
    status_column: str | None
    source: str
    limitation: str | None = None


def contract(unit: str, meaning: str, *, nullable: bool = False, calculation: str = "copied from upstream",
             status: str | None = None, source: str = "canonical", limitation: str | None = None) -> ColumnContract:
    return ColumnContract(unit, meaning, nullable, calculation, status, source, limitation)


def _columns(specifications: dict[str, tuple[str, str]], *, source: str = "canonical") -> dict[str, ColumnContract]:
    return {name: contract(unit, meaning, source=source) for name, (unit, meaning) in specifications.items()}


COLUMN_CONTRACTS: dict[str, dict[str, ColumnContract]] = {
    "mart_contest_results": _columns({
        "analytical_result_id": ("identifier", "Stable analytical result identifier"), "election_id": ("identifier", "Election identifier"),
        "ballot_type": ("category", "Ballot family"), "contest_id": ("identifier", "Contest identifier"),
        "geo_id": ("identifier", "Geographic unit identifier"), "party_id": ("identifier", "Party identifier"),
        "source_id": ("identifier", "Canonical source identifier"), "votes": ("count", "Observed votes"),
        "seats": ("count", "Observed seats"), "vote_share_ratio": ("ratio_0_1", "Vote share within the identified denominator"),
        "rank": ("ordinal", "Rank within contest"), "winner_flag": ("boolean", "Whether the result is a winner"),
        "seat_share_ratio": ("ratio_0_1", "Seat share within the identified denominator"),
        "previous_vote_share_ratio": ("ratio_0_1", "Comparable previous vote share"), "swing_ratio": ("ratio_delta", "Vote-share change"),
        "vote_change": ("count_delta", "Observed vote change"), "seat_change": ("count_delta", "Observed seat change"),
        "metric_status": ("status", "Metric availability"), "metric_status_reason": ("text", "Reason a metric is limited"),
        "distribution_status": ("status", "Source distribution normalization status"), "identity_status": ("status", "Party identity resolution status"),
        "fact_status": ("status", "Observed or derived fact status"), "quality_status": ("status", "Canonical quality status"),
        "longitudinal_compatibility_status": ("status", "Longitudinal evidence status"), "limitations": ("text", "Known limitations"),
    }),
    "mart_contest_competitiveness": _columns({
        "contest_id": ("identifier", "Contest identifier"), "election_id": ("identifier", "Election identifier"),
        "ballot_type": ("category", "Ballot family"), "hhi": ("ratio_0_1", "Herfindahl-Hirschman concentration index"),
        "effective_number_of_parties": ("count_equivalent", "Effective number of parties"),
        "victory_margin_ratio": ("ratio_0_1", "Winner to runner-up margin"), "concentration_ratio": ("ratio_0_1", "Leading-party concentration"),
        "metric_status": ("status", "Competition metric availability"), "metric_status_reason": ("text", "Missing preconditions"),
        "identity_status": ("status", "Party identity compatibility"), "fact_status": ("status", "Observed or derived fact status"),
        "quality_status": ("status", "Analytical quality status"), "longitudinal_compatibility_status": ("status", "Longitudinal evidence status"),
    }),
    "mart_party_performance": _columns({
        "party_performance_id": ("identifier", "Stable party-election-ballot identifier"), "election_id": ("identifier", "Election identifier"),
        "ballot_type": ("category", "Ballot family"), "party_id": ("identifier", "Party identifier"),
        "observed_contest_count": ("count", "Distinct observed contests"), "observed_votes": ("count", "Sum of observed votes"),
        "observed_seats": ("count", "Sum of observed seats"), "mean_vote_share_ratio": ("ratio_0_1", "Mean observed vote share"),
        "won_contest_count": ("count", "Observed winning contests"), "metric_status": ("status", "Performance metric availability"),
        "metric_status_reason": ("text", "Reason performance is limited"), "identity_status": ("status", "Aggregate identity resolution"),
        "fact_status": ("status", "Observed or derived fact status"), "quality_status": ("status", "Aggregate quality status"),
        "source_ids": ("identifier_list", "Contributing source identifiers"), "limitations": ("text", "Interpretive limitations"),
    }, source="mart_contest_results"),
    "mart_geography_profile": _columns({
        "geography_profile_id": ("identifier", "Stable geography-election-ballot identifier"), "election_id": ("identifier", "Election identifier"),
        "ballot_type": ("category", "Ballot family"), "geo_id": ("identifier", "Geographic unit identifier"),
        "observed_contest_count": ("count", "Distinct observed contests"), "observed_party_count": ("count", "Distinct observed parties"),
        "observed_votes": ("count", "Sum of observed votes"), "observed_seats": ("count", "Sum of observed seats"),
        "mean_hhi": ("ratio_0_1", "Mean contest concentration"), "mean_victory_margin_ratio": ("ratio_0_1", "Mean victory margin"),
        "metric_status": ("status", "Geography metric availability"), "metric_status_reason": ("text", "Reason geography profile is limited"),
        "identity_status": ("status", "Aggregate identity resolution"), "fact_status": ("status", "Observed or derived fact status"),
        "quality_status": ("status", "Aggregate quality status"), "source_ids": ("identifier_list", "Contributing source identifiers"),
        "limitations": ("text", "Interpretive limitations"),
    }, source="analytical marts"),
    "mart_parliamentary_activity": _columns({
        "parliamentary_activity_id": ("identifier", "Stable parliamentary activity identifier"), "person_id": ("identifier", "Person identifier"),
        "party_id": ("identifier", "Assigned party identifier"), "legislature": ("category", "Legislature label"),
        "period_id": ("identifier", "Reporting period identifier"), "question_type": ("category", "Parliamentary question type"),
        "first_deposit_date": ("date", "First published deposit date"), "last_deposit_date": ("date", "Last published deposit date"),
        "published_question_count": ("count", "Published questions"), "published_response_date_count": ("count", "Questions with a response date"),
        "published_response_date_ratio": ("ratio_0_1", "Share with a published response date"),
        "metric_status": ("status", "Activity metric availability"), "metric_status_reason": ("text", "Reason activity is limited"),
        "identity_status": ("status", "Party assignment method"), "fact_status": ("status", "Upstream derivation status"),
        "quality_status": ("status", "Analytical quality status"), "longitudinal_compatibility_status": ("status", "Longitudinal evidence status"),
        "limitations": ("text", "Coverage limitations"),
    }),
}


# Nullable and computed attributes are explicit rather than inferred from names.
for table, nullable_columns in {
    "mart_contest_results": {"votes", "seats", "vote_share_ratio", "rank", "winner_flag", "seat_share_ratio", "previous_vote_share_ratio", "swing_ratio", "vote_change", "seat_change", "metric_status_reason", "limitations"},
    "mart_contest_competitiveness": {"hhi", "effective_number_of_parties", "victory_margin_ratio", "concentration_ratio", "metric_status_reason"},
    "mart_party_performance": {"observed_votes", "observed_seats", "mean_vote_share_ratio", "won_contest_count", "metric_status_reason"},
    "mart_geography_profile": {"observed_votes", "observed_seats", "mean_hhi", "mean_victory_margin_ratio", "metric_status_reason"},
    "mart_parliamentary_activity": {"party_id", "first_deposit_date", "last_deposit_date", "published_response_date_ratio", "metric_status_reason"},
}.items():
    for name in nullable_columns:
        value = COLUMN_CONTRACTS[table][name]
        COLUMN_CONTRACTS[table][name] = ColumnContract(value.unit, value.meaning, True, value.calculation, value.status_column, value.source, value.limitation)


CALCULATIONS = {
    "mart_contest_results": {
        "metric_status": "AVAILABLE when vote_share_ratio is present; otherwise LIMITED",
        "metric_status_reason": "declared when vote_share_ratio is absent",
        "distribution_status": "SOURCE_INTERNAL_COMPLETE is exposed as SOURCE_DISTRIBUTION_NORMALIZED; otherwise OBSERVED",
        "fact_status": "constant OBSERVED", "quality_status": "upper-case upstream quality_status",
        "longitudinal_compatibility_status": "constant UNKNOWN pending dedicated evidence",
    },
    "mart_contest_competitiveness": {
        "metric_status": "COMPUTED maps to AVAILABLE; other upstream states map to NOT_AVAILABLE",
        "metric_status_reason": "upstream missing_preconditions with a non-null fallback",
        "identity_status": "RESOLVED when party_identities_compatible is true; otherwise UNRESOLVED",
        "fact_status": "constant DERIVED", "quality_status": "constant QUALIFIED",
        "longitudinal_compatibility_status": "constant UNKNOWN pending dedicated evidence",
    },
    "mart_party_performance": {
        "party_performance_id": "election_id || ':' || ballot_type || ':' || party_id",
        "observed_contest_count": "count distinct contest_id", "observed_votes": "sum votes", "observed_seats": "sum seats",
        "mean_vote_share_ratio": "average vote_share_ratio", "won_contest_count": "sum of non-null true winner_flag values",
        "metric_status": "AVAILABLE when all vote shares are present; otherwise LIMITED",
        "metric_status_reason": "declared when any vote share is absent", "identity_status": "RESOLVED when all input identities resolve",
        "fact_status": "constant DERIVED", "quality_status": "QUALIFIED when all input quality states are accepted",
        "source_ids": "distinct sorted source_id joined by comma", "limitations": "declared observed-contest limitation",
    },
    "mart_geography_profile": {
        "geography_profile_id": "election_id || ':' || ballot_type || ':' || geo_id",
        "observed_contest_count": "count distinct contest_id", "observed_party_count": "count distinct party_id",
        "observed_votes": "sum votes", "observed_seats": "sum seats", "mean_hhi": "average one HHI value per distinct contest",
        "mean_victory_margin_ratio": "average one victory margin per distinct contest",
        "metric_status": "AVAILABLE when all contests match and mean HHI is present; otherwise LIMITED",
        "metric_status_reason": "declared when a normalized contest distribution is absent",
        "identity_status": "RESOLVED when all input identities resolve", "fact_status": "constant DERIVED",
        "quality_status": "QUALIFIED when all input quality states are accepted",
        "source_ids": "distinct sorted source_id joined by comma", "limitations": "declared observed-contest limitation",
    },
    "mart_parliamentary_activity": {
        "parliamentary_activity_id": "copied from trajectory_id",
        "published_response_date_ratio": "published_response_date_rate_pct / 100",
        "metric_status": "AVAILABLE for DERIVED_FROM_PUBLISHED_QUESTIONS; otherwise LIMITED",
        "metric_status_reason": "upstream derivation_status when the metric is limited",
        "fact_status": "copied from derivation_status", "quality_status": "constant QUALIFIED",
        "longitudinal_compatibility_status": "constant UNKNOWN pending dedicated evidence",
        "limitations": "declared published-document coverage limitation",
    },
}

STATUS_COLUMNS = {
    "mart_contest_results": {"vote_share_ratio", "seat_share_ratio", "previous_vote_share_ratio", "swing_ratio", "vote_change", "seat_change"},
    "mart_contest_competitiveness": {"hhi", "effective_number_of_parties", "victory_margin_ratio", "concentration_ratio"},
    "mart_party_performance": {"mean_vote_share_ratio"},
    "mart_geography_profile": {"mean_hhi", "mean_victory_margin_ratio"},
    "mart_parliamentary_activity": {"published_response_date_ratio"},
}

for table, formulas in CALCULATIONS.items():
    for name, formula in formulas.items():
        value = COLUMN_CONTRACTS[table][name]
        COLUMN_CONTRACTS[table][name] = ColumnContract(
            value.unit, value.meaning, value.nullable, formula, value.status_column, value.source, value.limitation
        )

for table, names in STATUS_COLUMNS.items():
    for name in names:
        value = COLUMN_CONTRACTS[table][name]
        status = "longitudinal_compatibility_status" if name in {"previous_vote_share_ratio", "swing_ratio", "vote_change", "seat_change"} else "metric_status"
        COLUMN_CONTRACTS[table][name] = ColumnContract(
            value.unit, value.meaning, value.nullable, value.calculation, status, value.source, value.limitation
        )
