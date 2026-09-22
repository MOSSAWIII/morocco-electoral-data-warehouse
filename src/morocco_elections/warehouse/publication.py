"""Stable publication API backed by modular gate infrastructure.

Gate metadata and interfaces live in :mod:`warehouse.gates.registry` and
:mod:`warehouse.gates.base`; evaluator implementations are isolated from the
package, CLI, and audit orchestration in :mod:`warehouse.gates.evaluators`.
"""

from morocco_elections.warehouse.gates.evaluators import (
    GATE_REGISTRY,
    REQUIRED_GATES,
    PublicationContext,
    _analytic_admissibility,
    _as_of,
    _bind_contract_tables,
    _boundary,
    _candidacy_seats,
    _claims,
    _coverage,
    _denominator,
    _evidence_bundle,
    _grain,
    _immutability,
    _legal_regime,
    _lineage,
    _metrics,
    _privacy,
    _redistribution,
    _reproducible,
    _result_status,
    _semantic_facts,
    _source_conflicts,
    _uncertainty,
    _verify_demographic_source_rows,
    evaluate_publication_gates,
    evidence_bundle_payload,
    generate_checksums,
    sha256_file,
    validate_coverage_matrix,
    validate_publication,
    write_evidence_bundle,
)

__all__ = [
    "GATE_REGISTRY",
    "REQUIRED_GATES",
    "PublicationContext",
    "evaluate_publication_gates",
    "evidence_bundle_payload",
    "generate_checksums",
    "sha256_file",
    "validate_coverage_matrix",
    "validate_publication",
    "write_evidence_bundle",
]
