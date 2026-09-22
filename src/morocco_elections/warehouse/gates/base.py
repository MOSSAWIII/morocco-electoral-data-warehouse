"""Shared gate interface and metadata contract."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str
    justification: str
    evidence_id: str
    affected_records: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["affected_records"] = list(self.affected_records)
        return payload

    def as_contract_row(self, snapshot_id: str) -> dict[str, Any]:
        return {
            "release_id": snapshot_id,
            "gate_id": self.gate_id,
            "gate_status": self.status,
            "justification": self.justification,
            "evidence_id": self.evidence_id,
            "affected_records": json.dumps(self.affected_records, ensure_ascii=False),
        }


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    classification: str
    scope: str
    required_tables: tuple[str, ...] = ()
    required_sources: tuple[str, ...] = ()
    produced_evidence: tuple[str, ...] = ()
    blocking: bool = True
    conditional: bool = False


class Gate(Protocol):
    spec: GateSpec

    def evaluate(self, package: Any) -> GateResult: ...


@dataclass(frozen=True)
class FunctionGate:
    spec: GateSpec
    evaluator: Callable[[Any], GateResult]

    def evaluate(self, package: Any) -> GateResult:
        result = self.evaluator(package)
        if result.gate_id != self.spec.gate_id:
            raise RuntimeError(f"gate {self.spec.gate_id} returned {result.gate_id}")
        return result
