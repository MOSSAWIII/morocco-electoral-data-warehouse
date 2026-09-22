from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Vocabulary:
    name: str
    version: str
    definitions: dict[str, str]

    @property
    def values(self) -> frozenset[str]:
        return frozenset(self.definitions)


def _v(name: str, **definitions: str) -> Vocabulary:
    return Vocabulary(name, "1.0.0", definitions)


VOCABULARIES = {
    item.name: item
    for item in (
        _v("quality_status", VERIFIED="Source and value verified", QUALIFIED="Usable with disclosed limits", UNRESOLVED="Not resolved", REJECTED="Rejected by validation"),
        _v("fact_status", OBSERVED="Directly observed", OFFICIAL="Published by competent authority", RECOMPUTED="Derived deterministically", INFERRED="Inferred and never an observed fact", FORECAST="Forecast and never an observed fact"),
        _v("list_type", LOCAL="Local constituency list", REGIONAL="Regional list", NATIONAL="National list", INDIVIDUAL="Individual candidacy"),
        _v("result_type", VOTES="Votes", SEATS="Seats", MOBILIZATION="Electoral mobilization", ALLOCATION="Seat allocation"),
        _v("result_status", SCHEDULED="Election scheduled", POLL_CLOSED="Poll closed", PROVISIONAL="Provisional result", PROCLAIMED="Officially proclaimed result", CONTESTED="Result under legal contest", RECTIFIED="Officially corrected result", ANNULLED="Annulled result", FINAL="Final result"),
        _v("verification_status", VERIFIED="Denominator verified against its source", PENDING="Verification pending", REJECTED="Failed verification"),
        _v("universe_type", OFFICIAL_CONTESTS="Official contests", OFFICIAL_TERRITORIES="Official territories", OFFICIAL_RECORDS="Official records", OFFICIAL_DOCUMENTS="Official documents", OFFICIAL_FIELDS="Expected official fields", OFFICIAL_PERIODS="Official temporal periods"),
        _v("member_extraction_method", HCP_RGPH2014_COMMUNES="Reparse all complete HCP RGPH 2014 communal and arrondissement codes, including suppressed-population rows", JSON_UNIVERSES_OBJECT="Reparse an official JSON universes object with explicit identifiers by universe ID"),
        _v("coverage_dimension", ACQUIRED="Acquired-source coverage", OFFICIAL="Official-universe coverage", TERRITORIAL="Territorial coverage", TEMPORAL="Temporal coverage", DOCUMENTARY="Document coverage", FIELD="Field coverage"),
        _v("coverage_status", COMPLETE="Numerator equals verified denominator", PARTIAL="Verified denominator is only partly covered", EMPTY="Verified universe has no acquired observations", UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR="No reliable official denominator"),
        _v("validation_status", PASS="Within tolerance", FAIL="Outside tolerance", NOT_COMPUTABLE="Inputs insufficient or incompatible"),
        _v("not_computable_reason", MOBILIZATION_RECORD_MISSING="No materialized mobilization row exists for the contest", MOBILIZATION_FIELDS_MISSING="Registered or voter count is absent or registered count is zero", OFFICIAL_TURNOUT_MISSING="The sourced official turnout rate is absent", BALLOT_COMPONENTS_MISSING="Voter or ballot-category component is absent", BALLOT_TAXONOMY_UNVERIFIED="Complete ballot components lack a verified accounting taxonomy", PARTY_UNIVERSE_UNVERIFIED="Expected official party identifiers are unverified", SEAT_UNIVERSE_UNVERIFIED="Expected official seat-allocation identifiers are unverified", UNSUPPORTED_METRIC="No package-fact derivation is implemented"),
        _v("legal_decision_type", RECTIFICATION="Rectifies a result", ANNULMENT="Annuls a result", PARTIAL_ELECTION="Orders or records a partial election", CONFIRMATION="Confirms a result"),
        _v("party_lineage_type", MERGER="Merger", SPLIT="Split", RENAME="Name change", COALITION="Coalition", SUCCESSION="Other documented succession"),
        _v("geo_lineage_type", SAME_BOUNDARY="Identical boundary", SPLIT="Territorial split", MERGER="Territorial merger", REDISTRICTED="Boundary changed", PARENT_CHANGE="Parent changed"),
        _v("geo_parent_relationship_type", ADMINISTRATIVE_PARENT="Administrative hierarchy parent", COUNCIL_PARENT="Commune council parent of an arrondissement"),
        _v("geo_parent_review_status", VERIFIED_OFFICIAL_CROSSWALK="Parent relation verified across official sources", VERIFIED_SOURCE_DERIVED="Parent relation reproduced from pinned source rows", CANDIDATE="Evidence is insufficient for promotion", REJECTED="Relation rejected by review"),
        _v("matching_method", OFFICIAL_IDENTIFIER="Official stable identifier", DOCUMENTED_CROSSWALK="Documented crosswalk", HUMAN_REVIEW="Human-reviewed evidence", NAME_ONLY="Name similarity alone; forbidden for person identity"),
        _v("metric_status", COMPUTED="All preconditions passed", NOT_COMPUTED="At least one precondition failed"),
        _v("publication_status", PUBLICATION_READY="All publication gates passed", NOT_PUBLICATION_READY="At least one gate failed"),
        _v("gate_status", PASS="Gate passed from inspected evidence", FAIL="Gate failed closed"),
        _v("claim_class", OBSERVED_FACT="Observed sourced fact", DERIVED_DESCRIPTIVE="Deterministic descriptive result", ASSOCIATION="Non-causal association", PREDICTION="Prediction", CAUSAL="Causal claim requiring a causal design"),
        _v("license_status", REDISTRIBUTABLE="Redistribution permitted", METADATA_ONLY="Only metadata may be redistributed", FORBIDDEN="Redistribution forbidden", UNKNOWN="License unresolved"),
    )
}


_TABLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "coverage_universe": {"primary_key": ["universe_id"], "required": ["universe_id", "election_id", "coverage_dimension", "universe_type", "denominator", "source_id", "source_url", "acquired_at", "verification_status", "is_external", "member_extraction_method"]},
    "coverage_universe_member": {"primary_key": ["universe_id", "expected_id"], "required": ["universe_id", "expected_id", "source_id"]},
    "fact_result_revision": {"primary_key": ["revision_id"], "required": ["revision_id", "result_id", "contest_id", "election_id", "geo_id", "geo_version_id", "result_status", "valid_from", "source_id", "known_at", "verification_method", "verification_status"]},
    "fact_result_reconciliation": {"primary_key": ["reconciliation_id"], "required": ["reconciliation_id", "contest_id", "metric", "tolerance", "validation_status", "source_id"]},
    "fact_legal_decision": {"primary_key": ["decision_id"], "required": ["decision_id", "decision_type", "decision_date", "legal_basis", "source_id", "source_url"]},
    "dim_legal_regime": {"primary_key": ["legal_regime_id"], "required": ["legal_regime_id", "valid_from", "legal_article", "legal_basis", "official_source_id", "official_source_url", "allocation_formula", "electoral_quotient_denominator", "threshold_rule", "district_magnitude_rule", "remainder_rule", "tie_break_rule", "list_type"]},
    "bridge_election_legal_regime": {"primary_key": ["election_id", "legal_regime_id"], "required": ["election_id", "legal_regime_id", "valid_from", "source_id"]},
    "bridge_contest_legal_regime": {"primary_key": ["contest_id", "legal_regime_id"], "required": ["contest_id", "election_id", "legal_regime_id", "valid_from", "source_id"]},
    "fact_geo_population": {"primary_key": ["geo_population_id"], "required": ["geo_population_id", "official_geo_code", "population", "census_date", "source_id", "source_url"]},
    "bridge_geo_official_identifier": {"primary_key": ["crosswalk_id"], "required": ["crosswalk_id", "geo_id", "official_geo_code", "matching_method", "source_id", "confidence"]},
    "dim_contest_type": {"primary_key": ["contest_type_id"], "required": ["contest_type_id", "label", "list_type"]},
    "dim_seat_category": {"primary_key": ["seat_category_id"], "required": ["seat_category_id", "label", "legal_regime_id"]},
    "fact_candidacy_list": {"primary_key": ["candidacy_list_id"], "required": ["candidacy_list_id", "contest_id", "list_type", "source_id"]},
    "fact_candidate": {"primary_key": ["candidacy_id"], "required": ["candidacy_id", "candidacy_list_id", "person_id", "position", "identity_match_method", "source_id"]},
    "fact_seat_allocation": {"primary_key": ["allocation_id"], "required": ["allocation_id", "contest_id", "candidacy_list_id", "seat_category_id", "legal_regime_id", "official_seats", "validation_status", "source_id"]},
    "dim_party_version": {"primary_key": ["party_version_id"], "required": ["party_version_id", "party_id", "name", "valid_from", "source_id"]},
    "bridge_party_lineage": {"primary_key": ["lineage_id"], "required": ["lineage_id", "predecessor_party_id", "successor_party_id", "party_lineage_type", "effective_date", "source_id"]},
    "bridge_person_party_affiliation": {"primary_key": ["affiliation_id"], "required": ["affiliation_id", "person_id", "party_id", "party_version_id", "valid_from", "matching_method", "source_id"]},
    "dim_geo_version": {"primary_key": ["geo_version_id"], "required": ["geo_version_id", "geo_id", "boundary_version", "valid_from", "source_id"]},
    "bridge_geo_lineage": {"primary_key": ["geo_lineage_id"], "required": ["geo_lineage_id", "from_geo_version_id", "to_geo_version_id", "geo_lineage_type", "method", "source_id", "confidence"]},
    "bridge_geo_parent": {"primary_key": ["relation_id"], "required": ["relation_id", "child_geo_id", "parent_geo_id", "relationship_type", "election_id", "valid_from", "source_id", "matching_method", "confidence", "review_status"]},
    "fact_metric_validation": {"primary_key": ["metric_validation_id"], "required": ["metric_validation_id", "metric_name", "formula", "denominator", "scope", "metric_status", "coverage_status", "limitations"]},
    "publication_file": {"primary_key": ["release_id", "relative_path"], "required": ["release_id", "relative_path", "byte_size", "sha256", "artifact_type", "source_id", "acquired_at", "license_status", "claim_class", "privacy_review_required", "evidence_id"]},
    "publication_review": {"primary_key": ["release_id", "relative_path", "review_type"], "required": ["release_id", "relative_path", "review_type", "decision", "file_sha256", "reviewed_by", "reviewed_at", "evidence_id"]},
    "release_coverage_matrix": {"primary_key": ["release_id", "scope_id"], "required": ["release_id", "scope_id", "universe_ids_json", "acquired", "expected", "covered", "missing", "non_comparable", "redistribution_forbidden", "status"]},
    "publication_gate_result": {"primary_key": ["release_id", "gate_id"], "required": ["release_id", "gate_id", "gate_status", "justification", "evidence_id", "affected_records"]},
}


PROPOSED_TABLE_NAMES = frozenset({
    "dim_contest_type",
    "dim_seat_category",
    "fact_candidacy_list",
    "fact_candidate",
    "fact_seat_allocation",
    "dim_party_version",
    "bridge_party_lineage",
    "bridge_person_party_affiliation",
    "dim_geo_version",
    "bridge_geo_lineage",
    "fact_legal_decision",
    "fact_result_revision",
    "fact_metric_validation",
})

# Only TABLE_CONTRACTS is materialized in the public warehouse. Proposal
# definitions remain importable so candidate schemas can be tested without
# representing empty tables as published capabilities.
TABLE_CONTRACTS = {
    name: contract for name, contract in _TABLE_DEFINITIONS.items()
    if name not in PROPOSED_TABLE_NAMES
}
PROPOSED_TABLE_CONTRACTS = {
    name: _TABLE_DEFINITIONS[name] for name in sorted(PROPOSED_TABLE_NAMES)
}
ALL_TABLE_CONTRACTS = {**TABLE_CONTRACTS, **PROPOSED_TABLE_CONTRACTS}


FIELD_VOCABULARIES = {
    "quality_status": "quality_status", "fact_status": "fact_status", "list_type": "list_type",
    "result_type": "result_type", "result_status": "result_status", "verification_status": "verification_status",
    "universe_type": "universe_type", "member_extraction_method": "member_extraction_method", "coverage_dimension": "coverage_dimension", "coverage_status": "coverage_status",
    "validation_status": "validation_status", "not_computable_reason": "not_computable_reason", "decision_type": "legal_decision_type", "party_lineage_type": "party_lineage_type",
    "geo_lineage_type": "geo_lineage_type", "matching_method": "matching_method", "identity_match_method": "matching_method",
    "relationship_type": "geo_parent_relationship_type", "review_status": "geo_parent_review_status",
    "metric_status": "metric_status", "publication_status": "publication_status", "claim_class": "claim_class",
    "license_status": "license_status", "gate_status": "gate_status",
}
