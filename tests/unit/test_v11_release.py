from __future__ import annotations

import json
from pathlib import Path

from morocco_elections.releases.v11 import build


ROOT = Path(__file__).resolve().parents[2]


def test_release_report_has_closed_change_set_and_expected_controls() -> None:
    report = json.loads((ROOT / "metadata/v11_release_report.json").read_text(encoding="utf-8"))
    assert report["release"] == "V11"
    assert report["baseline"] == "V10"
    assert set(report["actual_changed_sheets"]) == build.ALLOWED_CHANGED_SHEETS
    assert report["volumes"]["FACT_OBSERVATION_V11"] == 3_203
    assert report["volumes"]["population_legal_2014"] == 1_538
    assert report["volumes"]["population_municipal_2024"] == 1_538
    assert report["controls"]["population_legal_2014_sum"] == 33_848_242
    assert report["controls"]["population_municipal_2024_sum"] == 36_490_591
    assert report["controls"]["population_legal_2024_sum"] == 36_828_330
    assert report["controls"]["population_legal_2024_differences"] == 0
    assert report["controls"]["no_go_ingested"] == 0
    assert report["controls"]["derived_values_ingested"] == 0
    assert report["controls"]["electoral_panels_changed"] is False


def test_diff_report_is_generated_from_release_report() -> None:
    report = json.loads((ROOT / "metadata/v11_release_report.json").read_text(encoding="utf-8"))
    actual = (ROOT / "docs/research/V11_VS_V10_DIFF.txt").read_text(encoding="utf-8-sig")
    assert actual == build.render_diff_report(report)


def test_canonical_v11_inputs_do_not_include_prior_release_workbooks(tmp_path: Path) -> None:
    inputs = build.canonical_source_inputs(tmp_path)
    names = {path.name for path in inputs}
    assert "Morocco_Electoral_Data_Warehouse_V9.xlsx" not in names
    assert "Morocco_Electoral_Data_Warehouse_V10.xlsx" not in names
    assert "Morocco_Electoral_Data_Warehouse_V11.xlsx" not in names
    assert "Morocco_Electoral_Data_Warehouse_V8.xlsx" in names
