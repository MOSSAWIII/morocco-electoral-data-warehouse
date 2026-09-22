"""Declarative gate inventory; evaluator implementations live in domain modules."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from morocco_elections.warehouse.gates.base import FunctionGate, GateResult, GateSpec


SPECS = (
    GateSpec("EVIDENCE_BUNDLE_VERIFIED", "REDUNDANT", "proofs", produced_evidence=("proof-index",)),
    GateSpec("SEMANTIC_FACTS_VALIDATED", "CORE_BLOCKING", "all", required_tables=("dim_election", "dim_electoral_contest", "dim_geo", "fact_election_result"), produced_evidence=("semantic-validation",)),
    GateSpec("LEGAL_REGIME_PINNED", "DOMAIN_BLOCKING", "elections", required_tables=("dim_legal_regime", "bridge_election_legal_regime", "bridge_contest_legal_regime"), required_sources=("official-legal-registry",), conditional=True),
    GateSpec("RESULT_STATUS_KNOWN", "DOMAIN_BLOCKING", "results", required_tables=("fact_result_revision", "fact_legal_decision"), conditional=True),
    GateSpec("AS_OF_DATE_VALID", "CORE_BLOCKING", "all", required_tables=("warehouse_metadata",)),
    GateSpec("OFFICIAL_UNIVERSE_DECLARED", "DOMAIN_BLOCKING", "coverage", required_tables=("coverage_universe", "coverage_universe_member"), required_sources=("official-universe",), conditional=True),
    GateSpec("DENOMINATOR_TYPED", "REDUNDANT", "coverage", required_tables=("coverage_universe", "coverage_universe_member"), conditional=True),
    GateSpec("GRAIN_COMPATIBLE", "CORE_BLOCKING", "all", produced_evidence=("grain-validation",)),
    GateSpec("BOUNDARY_COMPATIBLE", "DOMAIN_BLOCKING", "territories", required_tables=("dim_geo_version", "bridge_geo_lineage"), conditional=True),
    GateSpec("PARTY_LINEAGE_REVIEWED", "DOMAIN_BLOCKING", "parties", required_tables=("dim_party_version", "bridge_party_lineage"), conditional=True),
    GateSpec("SOURCE_CONFLICTS_RESOLVED_OR_EXPOSED", "CORE_BLOCKING", "provenance", produced_evidence=("source-conflict-resolution",)),
    GateSpec("CANDIDACY_AND_SEATS_VALIDATED", "DOMAIN_BLOCKING", "candidacies", required_tables=("fact_candidacy_list", "fact_candidate", "fact_seat_allocation"), conditional=True),
    GateSpec("METRIC_RECONCILED", "DOMAIN_BLOCKING", "results", required_tables=("fact_result_reconciliation",), conditional=True),
    GateSpec("ANALYTIC_METRICS_ADMISSIBLE", "DOMAIN_BLOCKING", "indicators", required_tables=("fact_metric_validation",), conditional=True),
    GateSpec("COVERAGE_DISCLOSED", "DOMAIN_BLOCKING", "coverage", required_tables=("release_coverage_matrix",), conditional=True),
    GateSpec("UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE", "DOMAIN_BLOCKING", "analyses", conditional=True),
    GateSpec("PRIVACY_REVIEW_PASSED", "CORE_BLOCKING", "persons", produced_evidence=("privacy-review",)),
    GateSpec("CLAIM_CLASS_DECLARED", "CORE_BLOCKING", "proofs", required_tables=("publication_file",)),
    GateSpec("REDISTRIBUTION_PERMITTED", "CORE_BLOCKING", "licenses", required_tables=("publication_file",), produced_evidence=("license-review",)),
    GateSpec("REPRODUCIBLE_FROM_CLEAN_ENVIRONMENT", "REMOVE", "build", produced_evidence=("ci-clean-build",)),
    GateSpec("V15_IMMUTABILITY_VERIFIED", "REMOVE", "archives", required_sources=("immutable-snapshot-manifest",)),
)


def build_registry(evaluators: Mapping[str, Callable[[Any], GateResult]]) -> tuple[FunctionGate, ...]:
    expected = tuple(spec.gate_id for spec in SPECS)
    if tuple(evaluators) != expected:
        raise RuntimeError("gate specifications and evaluator registry differ")
    return tuple(FunctionGate(spec, evaluators[spec.gate_id]) for spec in SPECS)
