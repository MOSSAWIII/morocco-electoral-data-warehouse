from __future__ import annotations

import json
from pathlib import Path

from morocco_elections.releases.v12 import build


ROOT = Path(__file__).resolve().parents[2]


def test_release_report_has_closed_change_set_and_partial_scope() -> None:
    report = json.loads((ROOT / "metadata/v12_release_report.json").read_text(encoding="utf-8"))
    assert report["release"] == "V12"
    assert report["baseline"] == "V11"
    assert report["scope_status"] == "PARTIAL"
    assert set(report["actual_changed_sheets"]) == build.ALLOWED_CHANGED_SHEETS
    assert report["volumes"] == {"sheets": 68, "PARLIAMENTARY_QUESTIONS": 5_589}
    assert report["controls"]["identity_rows_linked"] == 5_453
    assert report["controls"]["identity_rows_unlinked"] == 136
    assert report["controls"]["fuzzy_matches"] == 0


def test_diff_report_is_generated_from_release_report() -> None:
    report = json.loads((ROOT / "metadata/v12_release_report.json").read_text(encoding="utf-8"))
    actual = (ROOT / "docs/research/V12_VS_V11_DIFF.txt").read_text(encoding="utf-8-sig")
    assert actual == build.render_diff_report(report)


def test_canonical_v12_inputs_do_not_include_prior_release_workbooks(tmp_path: Path) -> None:
    names = {path.name for path in build.canonical_source_inputs(tmp_path)}
    for version in ("V9", "V10", "V11", "V12"):
        assert f"Morocco_Electoral_Data_Warehouse_{version}.xlsx" not in names
    assert "Morocco_Electoral_Data_Warehouse_V8.xlsx" in names
