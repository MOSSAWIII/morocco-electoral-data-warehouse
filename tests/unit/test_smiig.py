from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from morocco_elections.research.smiig import Contract, EXPECTED_COLUMNS, INDICATOR_COLUMNS, evaluate_frames

ROOT = Path(__file__).resolve().parents[2]


def frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for unit in (1, 2):
        row = {column: 0 for column in EXPECTED_COLUMNS}
        row.update(
            {
                "idRegion": 1,
                "idWilaya": 1,
                "idPrefProv": 1,
                "idSousPref": None,
                "idCommune": unit,
                "region": "R",
                "wilaya": "W",
                "prefProv": "P",
                "sousPref": None,
                "commune": f"Unité {unit}",
                "url": None,
                "annee": 2020,
                "inDb": None,
            }
        )
        rows.append(row)
    data = pd.DataFrame(rows, columns=EXPECTED_COLUMNS)
    definitions = []
    for column in EXPECTED_COLUMNS:
        definitions.append(f"{column} (10 points max)" if column in INDICATOR_COLUMNS else f"Définition {column}")
    dictionary = pd.DataFrame({"Label": EXPECTED_COLUMNS, "Définition (FR)": definitions, "Définition (EN)": definitions})
    notes = pd.DataFrame({"Source": ["CC BY 4.0 https://creativecommons.org/licenses/by/4.0/deed.fr"]})
    baseline = pd.DataFrame({"idCommune": [1, 2]})
    crosswalk = pd.DataFrame(
        {"source_geo_id": ["TAFRA_COMM_1", "TAFRA_COMM_2"], "canonical_geo_id": ["MA-1", "MA-2"]}
    )
    dim_geo = pd.DataFrame({"geo_id": ["MA-1", "MA-2"], "geo_type": ["commune", "commune"]})
    return data, dictionary, notes, baseline, crosswalk, dim_geo


def evaluate_case(mutation: str) -> dict:
    data, dictionary, notes, baseline, crosswalk, dim_geo = frames()
    if mutation == "license_absent":
        notes.iloc[0, 0] = "Licence non précisée"
    elif mutation == "empty_identifier":
        data.loc[0, "idCommune"] = None
    elif mutation == "duplicate_grain":
        data = pd.concat([data, data.iloc[[0]]], ignore_index=True)
    elif mutation == "year_out_of_range":
        data.loc[0, "annee"] = 2019
    elif mutation == "unexpected_role_field":
        data["role"] = "rôle inconnu"
    elif mutation == "invalid_indicator_domain":
        data.loc[0, "participation_compositionConseil"] = 13
    elif mutation == "unmapped_geography":
        crosswalk = crosswalk.iloc[[0]].copy()
    elif mutation != "none":
        raise AssertionError(mutation)
    return evaluate_frames(
        data,
        dictionary,
        notes,
        baseline,
        crosswalk,
        dim_geo,
        contract=Contract(expected_rows=2, expected_columns=38, expected_units=2, expected_years=(2020,)),
    )


@pytest.mark.parametrize("case", json.loads((ROOT / "tests/fixtures/synthetic/smiig_cases.json").read_text())["cases"])
def test_smiig_gate_cases(case: dict) -> None:
    assert evaluate_case(case["mutation"])["decision"] == case["expected"]


def test_smiig_anomalies_never_expose_geographic_names() -> None:
    result = evaluate_case("invalid_indicator_domain")
    encoded = json.dumps(result["anomalies"], ensure_ascii=False)
    assert "Unité 1" not in encoded
    assert result["anomalies"][0]["anomaly_id"].startswith("SMIIG_")
