from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from morocco_elections.research.electoral_denominators import (
    EXPECTED_ROWS,
    EXPECTED_TOTALS,
    _empty_evaluation,
    evaluate_frame,
    validate_metadata,
)


ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "tests/fixtures/synthetic/electoral_denominator_cases.json").read_text(encoding="utf-8"))


def _frame(year: int = 2015) -> pd.DataFrame:
    quotient, remainder = divmod(EXPECTED_TOTALS[year], EXPECTED_ROWS)
    registered = [quotient + (1 if index < remainder else 0) for index in range(EXPECTED_ROWS)]
    return pd.DataFrame(
        {
            "idCommune": range(1, EXPECTED_ROWS + 1),
            "year": year,
            "registered_voters": registered,
        }
    )


def _evaluate(frame: pd.DataFrame, year: int = 2015, turnout: dict[int, float] | None = None) -> dict:
    return evaluate_frame(
        frame,
        year=year,
        baseline_ids=set(range(1, EXPECTED_ROWS + 1)),
        canonical_ids={f"MA-{item}" for item in range(1, EXPECTED_ROWS + 1)},
        baseline_turnout=turnout or {},
        provenance_verified=True,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["case"])
def test_strict_gate_synthetic_cases(case: dict) -> None:
    frame = _frame()
    mutation = case["mutation"]
    if mutation == "drop_last":
        frame = frame.iloc[:-1].copy()
    elif mutation == "duplicate_first":
        frame.loc[EXPECTED_ROWS - 1, "idCommune"] = 1
    elif mutation == "blank_registered":
        frame.loc[0, "registered_voters"] = None
    elif mutation == "negative_registered":
        frame.loc[0, "registered_voters"] = -1
    elif mutation == "unknown_geo":
        frame.loc[EXPECTED_ROWS - 1, "idCommune"] = 999_999
    elif mutation == "wrong_total":
        frame.loc[0, "registered_voters"] += 1
    elif mutation == "wrong_year":
        frame.loc[0, "year"] = 2021
    elif mutation == "personal_field":
        frame["cnie"] = "synthetic-id"
    assert _evaluate(frame)["decision"] == case["expected"]


def test_optional_fields_absent_do_not_block_go() -> None:
    result = _evaluate(_frame())
    assert result["decision"] == "GO"
    assert result["profile"]["optional_fields_present"] == []


def test_turnout_mismatch_over_point_zero_one_blocks() -> None:
    frame = _frame()
    frame["voters"] = (frame["registered_voters"] * 0.5).astype(int)
    turnout = dict(zip(frame["idCommune"], 100 * frame["voters"] / frame["registered_voters"]))
    turnout[1] += 0.02
    result = _evaluate(frame, turnout=turnout)
    assert result["decision"] == "NO_GO"
    check = next(item for item in result["checks"] if item["check_id"] == "turnout_reconciliation")
    assert check["observed"]["mismatches_over_0_01_pp"] == 1


def test_missing_year_is_no_go() -> None:
    assert _empty_evaluation(2021)["decision"] == "NO_GO"


def test_metadata_rejects_partial_go() -> None:
    metadata = {
        "schema_version": 1,
        "phase": "V10-QA-1",
        "decision": "GO",
        "gate": {"expected_rows_total": 3076, "partial_go_allowed": False, "reconstruction_allowed": False},
        "year_results": {"2015": _evaluate(_frame(2015)), "2021": _empty_evaluation(2021)},
        "baseline": {"modified": False, "sha256_before": "a", "sha256_after": "a"},
        "candidates": {"2015": None, "2021": None},
    }
    assert any("Décision globale incohérente" in error for error in validate_metadata(metadata))
