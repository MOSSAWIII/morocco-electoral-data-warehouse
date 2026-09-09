from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from morocco_elections.research.electoral_archives import (
    _profile_workbook,
    render_report,
    validate_profile,
)


def test_profiles_grain_empty_columns_and_party_codes(tmp_path: Path) -> None:
    workbook = tmp_path / "synthetic.xlsx"
    data = pd.DataFrame(
        {
            "idCirconscription": [10, 11],
            "typeListe": ["locale", "locale"],
            "nSieges": [3, 4],
            "nInscrits": [None, None],
            "txParticipation": [0.50, 0.60],
            "P1": [100, None],
            "UNKNOWN": [20, 30],
        }
    )
    dictionary = pd.DataFrame(
        {
            "Label": list(data.columns),
            "Définition (FR)": ["définition"] * len(data.columns),
        }
    )
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        data.to_excel(writer, sheet_name="données", index=False)
        dictionary.to_excel(writer, sheet_name="dictionnaire", index=False)
        pd.DataFrame({"Source": ["fixture synthétique"]}).to_excel(writer, sheet_name="notes", index=False)
    record = {
        "source_id": "SYNTHETIC",
        "sha256": "0" * 64,
        "byte_size": workbook.stat().st_size,
    }
    spec = {
        "year": 2021,
        "election_type": "legislative",
        "election_id": "LEG2021",
        "key_fields": ["idCirconscription", "typeListe"],
        "destination": "CANONICAL_CANDIDATE",
        "limitations": [],
    }
    profile = _profile_workbook(
        workbook,
        record,
        spec,
        known_party_codes={"P1"},
        election_rows={"LEG2021": {"total_seats": 7}},
    )
    assert profile["duplicate_key_rows"] == 0
    assert profile["completely_empty_columns"] == ["nInscrits"]
    assert profile["party_codes"] == ["P1", "UNKNOWN"]
    assert profile["unrecognized_party_codes"] == ["UNKNOWN"]
    assert profile["party_null_cells"] == 1
    assert profile["seat_scope_gap"] == 0


def test_profile_validator_allows_recorded_source_anomalies() -> None:
    profile = {
        "schema_version": 1,
        "phase": "V13_SOURCE_PROFILE",
        "baseline_release": "V12",
        "source_count": 7,
        "integration_authorized": False,
        "destination_counts": {
            "CANONICAL_CANDIDATE": 0,
            "REFERENCE": 0,
            "CONTEXTUAL": 0,
            "PILOT": 0,
            "BLOCKED": 7,
            "ARCHIVE_ONLY": 0,
        },
        "profiles": [],
    }
    required = {
        "sha256": "0" * 64,
        "year": 2021,
        "election_type": "regional",
        "election_id": "REG2021",
        "probable_grain": "source_geo_unit",
        "key_fields": ["source_geo_unit"],
        "rows": 2,
        "columns": 2,
        "useful_rows": 2,
        "geographic_units": 1,
        "duplicate_key_rows": 2,
        "missing_key_cells": 0,
        "completely_empty_columns": [],
        "party_codes": [],
        "personal_data_headers": [],
        "destination": "BLOCKED",
        "integration_gate": "BLOCKED",
        "limitations": ["doublon critique"],
    }
    profile["profiles"] = [{"source_id": f"S{i}", **required} for i in range(7)]
    assert validate_profile(profile) == []


def test_report_is_deterministic() -> None:
    profile = json.loads(
        (Path(__file__).resolve().parents[2] / "metadata" / "v13_electoral_sources_profile.json").read_text(
            encoding="utf-8"
        )
    )
    assert render_report(profile) == render_report(profile)
