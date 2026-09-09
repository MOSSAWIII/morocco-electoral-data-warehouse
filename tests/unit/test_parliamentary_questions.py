from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl

from morocco_elections.research import parliamentary_questions as questions


def _baseline(path: Path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "PARLIAMENTARY_MANDATES"
    worksheet.append(["synthetic"])
    worksheet.append(["synthetic"])
    worksheet.append([])
    headers = ["mandate_id", "person_id", "full_name", "full_name_ar", "gender", "legislature", "party_id"]
    worksheet.append(headers)
    worksheet.append(["M1", "P1", "Synthetic Person", "شخص تجريبي", None, "2021-2026", "PARTY"])
    workbook.save(path)
    workbook.close()


def _candidate(path: Path, *, person: str = "شخص تجريبي", formula_text: bool = False) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(list(questions.EXPECTED_HEADERS))
    text = "=نص منشور" if formula_text else "نص منشور"
    worksheet.append([1, "فترة", datetime(2023, 4, 1), person, "فريق", "وزارة", "موضوع", text, "-"])
    workbook.save(path)
    workbook.close()


def test_four_official_segments_pass_with_exact_identity_and_formula_text(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.xlsx"
    _baseline(baseline)
    candidates = []
    for index, name in enumerate(questions.SOURCE_SPECS):
        path = tmp_path / name
        _candidate(path, formula_text=index == 0)
        candidates.append(path)
    report = questions.qualify_sources(candidates, baseline_workbook=baseline, as_of="2026-09-09")
    assert report["decision"] == "GO"
    assert report["profile"]["rows"] == 4
    assert report["profile"]["identity_rows_exact_unique"] == 4
    assert report["profile"]["formula_like_text_rows"] == 1


def test_identity_coverage_below_gate_fails_without_fuzzy_matching(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.xlsx"
    _baseline(baseline)
    candidates = []
    for index, name in enumerate(questions.SOURCE_SPECS):
        path = tmp_path / name
        _candidate(path, person="شخص غير معروف" if index == 0 else "شخص تجريبي")
        candidates.append(path)
    report = questions.qualify_sources(candidates, baseline_workbook=baseline, as_of="2026-09-09")
    assert report["decision"] == "NO_GO"
    assert report["profile"]["identity_rows_unmatched"] == 1
    assert report["profile"]["identity_rows_ambiguous"] == 0
