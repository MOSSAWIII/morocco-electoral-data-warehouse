from __future__ import annotations

import json
from pathlib import Path

from morocco_elections.domains.elections.core import stable_result_id
from morocco_elections.releases.v13 import build


ROOT = Path(__file__).resolve().parents[2]


def test_release_report_has_closed_change_set_and_expected_controls() -> None:
    report = json.loads((ROOT / "metadata/v13_release_report.json").read_text(encoding="utf-8"))
    assert report["release"] == "V13"
    assert report["baseline"] == "V12"
    assert report["scope_status"] == "PARTIAL"
    assert set(report["actual_changed_sheets"]) == build.ALLOWED_CHANGED_SHEETS
    assert report["volumes"] == {
        "sheets": 71,
        "DIM_ELECTORAL_CONTEST": 639,
        "FACT_ELECTION_RESULT": 10_883,
        "FACT_ELECTORAL_MOBILIZATION": 639,
    }
    assert report["controls"]["new_geo_entities"] == 159
    assert report["controls"]["new_party_entities"] == 4
    assert report["controls"]["technical_zero_imputations"] == 0
    assert report["controls"]["archive_2002_rows_ingested"] == 0


def test_diff_report_is_generated_from_release_report() -> None:
    report = json.loads((ROOT / "metadata/v13_release_report.json").read_text(encoding="utf-8"))
    actual = (ROOT / "docs/research/V13_VS_V12_DIFF.txt").read_text(encoding="utf-8-sig")
    assert actual == build.render_diff_report(report)


def test_result_id_is_deterministic_and_contextualized() -> None:
    first = stable_result_id("CONTEST_A", "PARTY_X")
    assert first == stable_result_id("CONTEST_A", "PARTY_X")
    assert first != stable_result_id("CONTEST_A", "PARTY_Y")
    assert first != stable_result_id("CONTEST_B", "PARTY_X")
    assert first.startswith("RESULT_V13_")


def test_canonical_v13_inputs_do_not_include_prior_release_workbooks(tmp_path: Path) -> None:
    names = {path.name for path in build.canonical_source_inputs(tmp_path)}
    for version in ("V9", "V10", "V11", "V12", "V13"):
        assert f"Morocco_Electoral_Data_Warehouse_{version}.xlsx" not in names
    assert "Morocco_Electoral_Data_Warehouse_V8.xlsx" in names
    assert "parlement-elections-2007-1-0.xlsx" in names
    assert "regional-elections-2021-1-0.xlsx" in names
