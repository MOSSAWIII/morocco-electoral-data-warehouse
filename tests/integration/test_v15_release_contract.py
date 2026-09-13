from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pytest

from morocco_elections.quality.v15.package import validate_package
from morocco_elections.v15.queries import ANALYSES


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(os.environ.get("V15_TEST_PACKAGE", ROOT / "data/exports/open/v15"))
pytestmark = pytest.mark.skipif(not (PACKAGE / "manifest.json").is_file(), reason="paquet V15 construit requis")


def test_complete_public_package_contract() -> None:
    assert validate_package(PACKAGE) == []


def test_two_known_interval_anomalies_are_corrected_without_invention() -> None:
    connection = duckdb.connect(str(PACKAGE / "morocco_elections_v15.duckdb"), read_only=True)
    mandate = connection.execute(
        "SELECT start_date, end_date FROM fact_mandate WHERE mandate_id=?",
        ["PM_2011_2016_456_68758_2013-10-03"],
    ).fetchone()
    affiliation = connection.execute(
        "SELECT valid_from, valid_to FROM bridge_person_parliamentary_affiliation WHERE affiliation_id=?",
        ["AFFILIATION_V14_1_440E693C7566E2DBAF93D806519F7701"],
    ).fetchone()
    connection.close()
    assert str(mandate[0]) == "2013-10-03" and mandate[1] is None
    assert str(affiliation[0]) == "2013-10-03" and affiliation[1] is None


def test_temporal_precision_and_known_coverage_are_explicit() -> None:
    coverage = json.loads((PACKAGE / "coverage_matrix.json").read_text(encoding="utf-8"))
    governance = {row["year"]: row for row in coverage["communal_governance"]}
    assert governance[2015]["unresolved_presidencies"] == 1538
    assert governance[2021]["unresolved_presidencies"] == 135
    assert coverage["parliamentary_question_corpus"]["status"] == "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR"
    assert all(row["missing_values_are_zero"] is False for row in coverage["analyses"])
    precision = {(row["table_name"], row["column"]): row for row in coverage["temporal_precision"]}
    assert precision[("fact_observation", "date_start")]["counts"]["YEAR"] == 78
    assert precision[("fact_observation", "publication_date")]["counts"]["MONTH"] == 18
    assert precision[("sources", "coverage_start")]["counts"]["LABEL_YEAR"] == 6


def test_all_five_reference_analyses_execute() -> None:
    connection = duckdb.connect(str(PACKAGE / "morocco_elections_v15.duckdb"), read_only=True)
    try:
        assert len(ANALYSES) == 5
        assert all(connection.execute(row["sql"]).fetchall() is not None for row in ANALYSES)
    finally:
        connection.close()
