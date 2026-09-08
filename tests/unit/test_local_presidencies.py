from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from morocco_elections.research.local_presidencies import EVIDENCE_COLUMNS, evaluate_case, validate_metadata


CASE = {"geo_id": "MA-TEST-001", "source_idcommune": 1}
MANDATES = {
    "PERS_1": {"source_idcommune": 1, "geo_id": "MA-TEST-001", "party_id": "PA"},
    "PERS_OTHER": {"source_idcommune": 2, "geo_id": "MA-TEST-002", "party_id": "PA"},
}


def _proof(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text("synthetic public evidence", encoding="utf-8")
    return path.name


def _row(tmp_path: Path, evidence_id: str = "E1", **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "evidence_id": evidence_id,
        "source_idcommune": "1",
        "person_id": "PERS_1",
        "party_id": "PA",
        "source_class": "official_primary",
        "publisher": "Official publisher",
        "origin_id": "OFFICIAL-1",
        "source_url": "https://example.test/proof",
        "published_on": "2021-09-20",
        "event_on": "2021-09-17",
        "local_path": _proof(tmp_path, f"{evidence_id}.txt"),
        "locator": "page 1",
        "direct_person": "true",
        "direct_party": "true",
        "initial_2021": "true",
        "identity_disambiguator": "true",
        "contradiction": "false",
    }
    row.update(overrides)
    return row


def _evaluate(tmp_path: Path, rows: list[dict[str, object]], *, ambiguous: bool = False) -> dict:
    frame = pd.DataFrame(rows, columns=sorted(EVIDENCE_COLUMNS))
    decision, _ = evaluate_case(CASE, frame, MANDATES, ambiguous=ambiguous, index_dir=tmp_path)
    return decision


def test_official_primary_evidence_is_go(tmp_path: Path) -> None:
    assert _evaluate(tmp_path, [_row(tmp_path)])['decision'] == "GO"


def test_two_independent_secondary_sources_are_go(tmp_path: Path) -> None:
    rows = [
        _row(tmp_path, "E1", source_class="secondary", publisher="Publisher A", origin_id="ORIGIN-A"),
        _row(tmp_path, "E2", source_class="secondary", publisher="Publisher B", origin_id="ORIGIN-B"),
    ]
    assert _evaluate(tmp_path, rows)["decision"] == "GO"


@pytest.mark.parametrize(
    "rows_factory,reason",
    [
        (lambda p: [_row(p, source_class="secondary")], "INSUFFICIENT_INDEPENDENT_SOURCES"),
        (
            lambda p: [
                _row(p, "E1", source_class="secondary", publisher="Publisher A", origin_id="WIRE"),
                _row(p, "E2", source_class="secondary", publisher="Publisher B", origin_id="WIRE"),
            ],
            "INSUFFICIENT_INDEPENDENT_SOURCES",
        ),
        (lambda p: [_row(p, event_on="2022-01-01")], "NO_VALID_EVIDENCE"),
        (lambda p: [_row(p, party_id="PB")], "NO_VALID_EVIDENCE"),
        (lambda p: [_row(p, person_id="PERS_OTHER")], "NO_VALID_EVIDENCE"),
        (lambda p: [_row(p, contradiction="true")], "CONTRADICTORY_EVIDENCE"),
    ],
)
def test_invalid_or_insufficient_evidence_is_no_go(tmp_path: Path, rows_factory, reason: str) -> None:
    decision = _evaluate(tmp_path, rows_factory(tmp_path))
    assert decision["decision"] == "NO_GO"
    assert reason in decision["reason_codes"]


def test_ambiguous_identity_requires_disambiguator(tmp_path: Path) -> None:
    decision = _evaluate(tmp_path, [_row(tmp_path, identity_disambiguator="false")], ambiguous=True)
    assert decision["decision"] == "NO_GO"


def test_competing_candidates_are_contradictory(tmp_path: Path) -> None:
    mandates = {**MANDATES, "PERS_2": {"source_idcommune": 1, "geo_id": "MA-TEST-001", "party_id": "PB"}}
    rows = pd.DataFrame(
        [_row(tmp_path, "E1"), _row(tmp_path, "E2", person_id="PERS_2", party_id="PB")],
        columns=sorted(EVIDENCE_COLUMNS),
    )
    decision, _ = evaluate_case(CASE, rows, mandates, ambiguous=False, index_dir=tmp_path)
    assert decision["decision"] == "NO_GO"
    assert "CONTRADICTORY_EVIDENCE" in decision["reason_codes"]


def test_metadata_requires_135_unique_decisions() -> None:
    metadata = {
        "schema_version": 1,
        "phase": "V10-QA-2",
        "decision": "NO_GO",
        "summary": {"expected": 135, "validated": 0, "unresolved": 135},
        "decisions": [],
        "baseline": {"modified": False, "sha256_before": "same", "sha256_after": "same"},
        "evidence": [],
    }
    assert any("135 décisions" in error for error in validate_metadata(metadata))
