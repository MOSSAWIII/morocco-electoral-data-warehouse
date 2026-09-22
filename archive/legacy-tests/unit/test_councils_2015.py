from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from morocco_elections.research.councils_2015 import Contract, EXPECTED_COLUMNS, evaluate_frames


ROOT = Path(__file__).resolve().parents[2]


def frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = [
        [1, 1, 1, None, 1, 11, "R1", "W1", "P1", None, "C1", "D11", "Personne A", "PA", True, "président"],
        [1, 1, 1, None, 1, 12, "R1", "W1", "P1", None, "C1", "D12", "Personne B", "PB", False, "conseiller"],
        [1, 1, 1, None, 2, 21, "R1", "W1", "P1", None, "C2", "D21", "Personne C", "PA", True, "président"],
    ]
    data = pd.DataFrame(rows, columns=EXPECTED_COLUMNS)
    definitions = ["champ"] * 16
    definitions[EXPECTED_COLUMNS.index("role")] = "Valeurs: président, conseiller"
    dictionary = pd.DataFrame({"Label": EXPECTED_COLUMNS, "Définition (FR)": definitions})
    notes = pd.DataFrame({"Source": ["Licence", "CC BY 4.0 https://creativecommons.org/licenses/by/4.0/"]})
    baseline = pd.DataFrame({"idCommune": [1, 2], "nSieges": [2, 1]})
    crosswalk = pd.DataFrame(
        {"source_geo_id": ["TAFRA_COMM_1", "TAFRA_COMM_2"], "canonical_geo_id": ["MA-1", "MA-2"]}
    )
    parties = pd.DataFrame({"party_id": ["PA", "PB"], "acronym": ["PA", "PB"]})
    return data, dictionary, notes, baseline, crosswalk, parties


def evaluate(data: pd.DataFrame) -> dict:
    _, dictionary, notes, baseline, crosswalk, parties = frames()
    return evaluate_frames(
        data,
        dictionary,
        notes,
        baseline,
        crosswalk,
        parties,
        contract=Contract(expected_rows=3, expected_columns=16, expected_communes=2, expected_parties=2),
    )


def apply_mutation(data: pd.DataFrame, mutation: str) -> pd.DataFrame:
    if mutation == "none":
        return data
    if mutation == "drop_commune_2":
        return data[data.idCommune != 2].copy()
    if mutation == "append_unique_seat":
        extra = data.iloc[[0]].copy()
        extra.loc[:, "idCirconscription"] = 13
        extra.loc[:, "prenomNom"] = "Personne D"
        return pd.concat([data, extra], ignore_index=True)
    if mutation == "set_party_XXX":
        changed = data.copy()
        changed.loc[0, "parti"] = "XXX"
        return changed
    if mutation == "append_exact_duplicate":
        return pd.concat([data, data.iloc[[0]]], ignore_index=True)
    raise AssertionError(mutation)


@pytest.mark.parametrize("case", json.loads((ROOT / "tests/fixtures/synthetic/councils_2015_cases.json").read_text())["cases"])
def test_synthetic_gate_cases(case: dict) -> None:
    data, *_ = frames()
    result = evaluate(apply_mutation(data, case["mutation"]))
    assert result["decision"] == case["expected"]


def test_duplicate_anomaly_never_contains_person_name() -> None:
    data, *_ = frames()
    result = evaluate(pd.concat([data, data.iloc[[0]]], ignore_index=True))
    encoded = json.dumps(result["anomalies"], ensure_ascii=False)
    assert "Personne A" not in encoded
    assert result["anomalies"][0]["anomaly_id"].startswith("DUP2015_")
