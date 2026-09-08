from __future__ import annotations

from pathlib import Path

import openpyxl

from morocco_elections.research import hcp_indicators as hcp


def _indicator(indicator_id: str) -> dict:
    return next(item for item in hcp.INDICATORS if item["indicator_id"] == indicator_id)


def test_missing_symbols_and_numeric_domains(monkeypatch) -> None:
    assert [hcp._numeric(value) for value in (None, "", ".", "…", "-")] == [None] * 5
    monkeypatch.setattr(hcp, "EXPECTED_UNITS", 2)
    context = {"universe": {"A", "B"}}
    rows = {"A": [(None, 50)], "B": [(None, 101)]}
    decision, values = hcp._evaluate_observed(
        _indicator("activity_rate"), 2024, rows, "TEST", 2, "Taux synthétique", context
    )
    assert decision["decision"] == "NO_GO"
    assert decision["invalid_values"] == 1
    assert values == {"A": 50.0, "B": None}


def test_derived_formulas_and_null_denominator(monkeypatch) -> None:
    monkeypatch.setattr(hcp, "EXPECTED_UNITS", 2)
    urban, values = hcp._evaluate_derived(
        _indicator("urbanization_rate"),
        2024,
        {"population_urban": {"A": 25.0, "B": 4.0}, "population_municipal": {"A": 100.0, "B": 0.0}},
    )
    assert values == {"A": 25.0, "B": None}
    assert urban["decision"] == "NO_GO"
    assert urban["matched_units"] == 2

    literacy, values = hcp._evaluate_derived(
        _indicator("literacy_rate_10_plus"), 2024, {"illiteracy_rate_10_plus": {"A": 30.0, "B": 20.0}}
    )
    assert values == {"A": 70.0, "B": 80.0}
    assert literacy["decision"] == "GO"


def test_exact_geography_mapping_and_documented_alias() -> None:
    context = {
        "universe": {"MA-01-001-0101", "MA-06-385-0305"},
        "by_name_parent": {("MA-01-001", "commune test"): ["MA-01-001-0101"]},
    }
    assert hcp._match_geo("MA-01-001-0101", "x", "MA-01-001", context, 2014) == (
        "MA-01-001-0101",
        "official_code",
    )
    assert hcp._match_geo("MA-01-001-9999", "Commune Test", "MA-01-001", context, 2014) == (
        "MA-01-001-0101",
        "exact_normalized_name_and_parent",
    )
    assert hcp._match_geo("MA-06-385-0105", "Ouled Salah", "MA-06-385", context, 2024) == (
        "MA-06-385-0305",
        "documented_hcp_2024_code_alias",
    )
    assert hcp._match_geo("MA-99-999-9999", "inconnue", "MA-99-999", context, 2024)[0] is None


def test_code_formats_and_prefecture_aggregate_exclusion() -> None:
    assert hcp._canonical_2014((6, 385, 1, None, 5)) == "MA-06-385-0105"
    assert hcp._canonical_2024(63850305) == "MA-06-385-0305"
    assert hcp._is_prefecture_aggregate("Préfecture d'arrondissements de Casablanca")
    assert not hcp._is_prefecture_aggregate("Arrondissement de Sidi Belyout")


def test_source_schema_records_multilevel_workbook_shape(tmp_path: Path) -> None:
    candidate = tmp_path / "rgph2014_individus.xlsx"
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for sheet_name in hcp.SOURCE_SPECS["RGPH2014_INDIVIDUALS"]["expected_sheets"]:
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(["Géographie", "Indicateur"])
        sheet.append(["Code", "Population"])
        sheet.append([None, "Personnes"])
        sheet.append([1, 10])
    workbook.save(candidate)
    record = hcp._source_record(candidate, "RGPH2014_INDIVIDUALS", "2026-09-08")
    assert record["status"] == "qualified_candidate"
    assert record["sheets"][0] == {"name": "Indic.Ensemble", "rows": 4, "columns": 2}


def test_comparability_is_separate_from_annual_availability() -> None:
    decisions = []
    for indicator in hcp.INDICATORS:
        for year in (2014, 2024):
            decisions.append({"indicator_id": indicator["indicator_id"], "observation_year": year, "decision": "GO"})
    results = {item["indicator_id"]: item for item in hcp._comparability(decisions)}
    assert results["population_legal"]["decision"] == "GO"
    assert results["school_enrollment_rate"]["decision"] == "NO_GO"
    assert "7-12" in results["school_enrollment_rate"]["reason"]
    assert results["activity_rate"]["decision"] == "NO_GO"


def test_missing_candidates_never_create_a_derived_go(monkeypatch) -> None:
    monkeypatch.setattr(hcp, "EXPECTED_UNITS", 2)
    decision, values = hcp._evaluate_derived(
        _indicator("urbanization_rate"), 2014, {"population_urban": {}, "population_municipal": {}}
    )
    assert decision["decision"] == "NO_GO"
    assert decision["matched_units"] == 0
    assert values == {}
