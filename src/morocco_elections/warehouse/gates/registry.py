"""Declarative gate inventory; evaluator implementations live in domain modules."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from morocco_elections.warehouse.gates.base import FunctionGate, GateResult, GateSpec


SPECS = (
    GateSpec("SEMANTIC_FACTS_VALIDATED", "CORE_BLOCKING", "all", required_tables=("dim_election", "dim_electoral_contest", "dim_geo", "fact_election_result"), produced_evidence=("semantic-validation",)),
    GateSpec("LEGAL_REGIME_PINNED", "DOMAIN_BLOCKING", "elections", required_tables=("dim_legal_regime", "bridge_election_legal_regime", "bridge_contest_legal_regime"), required_sources=("official-legal-registry",), conditional=True),
    GateSpec("AS_OF_DATE_VALID", "CORE_BLOCKING", "all", required_tables=("warehouse_metadata",)),
    GateSpec("OFFICIAL_UNIVERSE_DECLARED", "DOMAIN_BLOCKING", "coverage", required_tables=("coverage_universe", "coverage_universe_member"), required_sources=("official-universe",), conditional=True),
    GateSpec("GRAIN_COMPATIBLE", "CORE_BLOCKING", "all", produced_evidence=("grain-validation",)),
    GateSpec("SOURCE_CONFLICTS_RESOLVED_OR_EXPOSED", "CORE_BLOCKING", "provenance", produced_evidence=("source-conflict-resolution",)),
    GateSpec("METRIC_RECONCILED", "DOMAIN_BLOCKING", "results", required_tables=("fact_result_reconciliation",), conditional=True),
    GateSpec("COVERAGE_DISCLOSED", "DOMAIN_BLOCKING", "coverage", required_tables=("release_coverage_matrix",), conditional=True),
    GateSpec("UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE", "DOMAIN_BLOCKING", "analyses", conditional=True),
    GateSpec("PRIVACY_REVIEW_PASSED", "CORE_BLOCKING", "persons", produced_evidence=("privacy-review",)),
    GateSpec("CLAIM_CLASS_DECLARED", "CORE_BLOCKING", "proofs", required_tables=("publication_file",)),
    GateSpec("REDISTRIBUTION_PERMITTED", "CORE_BLOCKING", "licenses", required_tables=("publication_file",), produced_evidence=("license-review",)),
)


def build_registry(evaluators: Mapping[str, Callable[[Any], GateResult]]) -> tuple[FunctionGate, ...]:
    expected = tuple(spec.gate_id for spec in SPECS)
    if tuple(evaluators) != expected:
        raise RuntimeError("gate specifications and evaluator registry differ")
    return tuple(FunctionGate(spec, evaluators[spec.gate_id]) for spec in SPECS)
