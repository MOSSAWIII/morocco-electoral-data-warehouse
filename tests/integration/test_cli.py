from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from morocco_elections.research.councils_2015 import EXPECTED_COLUMNS
from morocco_elections.research.smiig import EXPECTED_COLUMNS as SMIIG_COLUMNS
from morocco_elections.research.smiig import INDICATOR_COLUMNS as SMIIG_INDICATORS


ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, env=ENV, text=True, capture_output=True, check=False)


def test_structured_cli_validation() -> None:
    result = run_command(sys.executable, "-m", "morocco_elections", "validate", "--mode", "ci")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALIDATION_OK" in result.stdout


def test_legacy_wrappers_expose_help() -> None:
    for script in ("build_v9.py", "generate_v9_documentation.py"):
        result = run_command(sys.executable, script, "--help")
        assert result.returncode == 0, result.stdout + result.stderr


def test_all_structured_commands_are_registered() -> None:
    for args in (
        ("build", "--help"),
        ("docs", "--help"),
        ("validate", "--help"),
        ("qualify", "councils-2015", "--help"),
        ("qualify", "smiig", "--help"),
        ("github", "publish-backlog", "--help"),
    ):
        result = run_command(sys.executable, "-m", "morocco_elections", *args)
        assert result.returncode == 0, result.stdout + result.stderr


def test_v10_versions_are_registered() -> None:
    for command in ("build", "docs"):
        result = run_command(sys.executable, "-m", "morocco_elections", command, "v10", "--help")
        assert result.returncode == 0, result.stdout + result.stderr


def test_full_mode_reports_missing_override_without_writing(tmp_path: Path) -> None:
    result = run_command(
        sys.executable,
        "-m",
        "morocco_elections",
        "validate",
        "--mode",
        "full",
        "--data-dir",
        str(tmp_path),
    )
    assert result.returncode == 1
    assert "fichier local absent" in result.stdout


def test_councils_2015_qualification_runs_offline(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.xlsx"
    baseline = tmp_path / "exports/excel/v10/Morocco_Electoral_Data_Warehouse_V10.xlsx"
    baseline.parent.mkdir(parents=True)
    row = [1, 1, 1, None, 1, 11, "R", "W", "P", None, "C", "D", "Personne X", "PX", True, "président"]
    with pd.ExcelWriter(candidate, engine="openpyxl") as writer:
        pd.DataFrame([row], columns=EXPECTED_COLUMNS).to_excel(writer, sheet_name="données", index=False)
        pd.DataFrame({"Label": EXPECTED_COLUMNS, "Définition (FR)": ["champ"] * 16}).to_excel(
            writer, sheet_name="dictionnaire", index=False
        )
        pd.DataFrame({"Source": ["CC BY 4.0"]}).to_excel(writer, sheet_name="notes", index=False)
    with pd.ExcelWriter(baseline, engine="openpyxl") as writer:
        pd.DataFrame({"idCommune": [1], "nSieges": [1]}).to_excel(writer, sheet_name="RAW_COMM2015_FULL", index=False, startrow=3)
        pd.DataFrame({"source_geo_id": ["TAFRA_COMM_1"], "canonical_geo_id": ["MA-1"]}).to_excel(
            writer, sheet_name="CROSSWALK_GEO", index=False, startrow=3
        )
        pd.DataFrame({"party_id": ["PX"], "acronym": ["PX"]}).to_excel(writer, sheet_name="DIM_PARTY", index=False, startrow=3)
    metadata = tmp_path / "decision.json"
    decision = tmp_path / "decision.txt"
    result = run_command(
        sys.executable,
        "-m",
        "morocco_elections",
        "qualify",
        "councils-2015",
        "--candidate",
        str(candidate),
        "--baseline",
        "v10",
        "--data-dir",
        str(tmp_path),
        "--metadata-output",
        str(metadata),
        "--decision-output",
        str(decision),
    )
    assert result.returncode == 1
    assert "QUALIFICATION_NO_GO" in result.stdout
    assert metadata.is_file() and decision.is_file()


def test_smiig_qualification_runs_offline(tmp_path: Path) -> None:
    candidate = tmp_path / "smiig.xlsx"
    baseline = tmp_path / "exports/excel/v10/Morocco_Electoral_Data_Warehouse_V10.xlsx"
    baseline.parent.mkdir(parents=True)
    row = {column: 0 for column in SMIIG_COLUMNS}
    row.update(
        {
            "idRegion": 1,
            "idWilaya": 1,
            "idPrefProv": 1,
            "idSousPref": None,
            "idCommune": 1,
            "region": "R",
            "wilaya": "W",
            "prefProv": "P",
            "sousPref": None,
            "commune": "Unité synthétique",
            "url": None,
            "annee": 2020,
            "inDb": None,
        }
    )
    definitions = [f"champ (10 points max)" if column in SMIIG_INDICATORS else "champ" for column in SMIIG_COLUMNS]
    with pd.ExcelWriter(candidate, engine="openpyxl") as writer:
        pd.DataFrame([row], columns=SMIIG_COLUMNS).to_excel(writer, sheet_name="donnees", index=False)
        pd.DataFrame({"Label": SMIIG_COLUMNS, "Définition (FR)": definitions, "Définition (EN)": definitions}).to_excel(
            writer, sheet_name="dictionnaire", index=False
        )
        pd.DataFrame({"Source": ["CC BY 4.0 https://creativecommons.org/licenses/by/4.0/deed.fr"]}).to_excel(
            writer, sheet_name="notes", index=False
        )
    with pd.ExcelWriter(baseline, engine="openpyxl") as writer:
        pd.DataFrame({"idCommune": [1]}).to_excel(writer, sheet_name="RAW_COMM2015_FULL", index=False, startrow=3)
        pd.DataFrame({"source_geo_id": ["TAFRA_COMM_1"], "canonical_geo_id": ["MA-1"]}).to_excel(
            writer, sheet_name="CROSSWALK_GEO", index=False, startrow=3
        )
        pd.DataFrame({"geo_id": ["MA-1"], "geo_type": ["commune"]}).to_excel(
            writer, sheet_name="DIM_GEO", index=False, startrow=3
        )
    metadata = tmp_path / "smiig-decision.json"
    decision = tmp_path / "smiig-decision.txt"
    result = run_command(
        sys.executable,
        "-m",
        "morocco_elections",
        "qualify",
        "smiig",
        "--candidate",
        str(candidate),
        "--baseline",
        "v10",
        "--data-dir",
        str(tmp_path),
        "--metadata-output",
        str(metadata),
        "--decision-output",
        str(decision),
    )
    assert result.returncode == 1
    assert "SMIIG_QUALIFICATION_NO_GO" in result.stdout
    assert metadata.is_file() and decision.is_file()
