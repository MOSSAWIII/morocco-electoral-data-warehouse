from pathlib import Path

import pandas as pd

from morocco_elections.analysis.v11 import compute_reference_analyses, render_text


def _write_sheet(writer, name: str, frame: pd.DataFrame) -> None:
    frame.to_excel(writer, sheet_name=name, index=False, startrow=3)


def test_reference_analyses_reconcile_and_expose_limits(tmp_path: Path) -> None:
    workbook = tmp_path / "v11.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        _write_sheet(
            writer,
            "COMMUNE_TRANSITION_PANEL",
            pd.DataFrame(
                {
                    "geo_id": ["G1", "G2"],
                    "winner_2015": ["P1", "P2"],
                    "winner_2021": ["P1", "P3"],
                    "turnout_change_pp": [2.0, -1.0],
                }
            ),
        )
        _write_sheet(
            writer,
            "COUNCIL_SEAT_STATUS_V10",
            pd.DataFrame(
                {
                    "geo_id": ["G1", "G2"],
                    "legal_seat_count": [10, 10],
                    "observed_elected_count": [10, 9],
                    "documented_vacancy_count": [0, 1],
                    "reconciled_difference": [0, 0],
                }
            ),
        )
        _write_sheet(
            writer,
            "LOCAL_COUNCIL_CONTROL",
            pd.DataFrame(
                {
                    "geo_id": ["G1", "G1", "G2"],
                    "president_party_id": ["P1", "P1", None],
                    "president_party_same_as_largest_party": [1, 0, None],
                }
            ),
        )
        _write_sheet(
            writer,
            "FACT_OBSERVATION",
            pd.DataFrame(
                {
                    "geo_id": ["G1", "G2", "G1", "G2"],
                    "time_id": [2014, 2014, 2024, 2024],
                    "metric_id": ["population_legal", "population_legal", "population_municipal", "population_municipal"],
                    "value_numeric": [100, 200, 110, 210],
                }
            ),
        )

    result = compute_reference_analyses(workbook)
    analyses = {item["analysis_id"]: item for item in result["analyses"]}
    assert analyses["winner_transition_2015_2021"]["winner_changed"] == 1
    assert analyses["reported_turnout_change_2015_2021"]["increase"] == 1
    assert analyses["council_seats_2021"]["legal_seats"] == 20
    assert analyses["president_among_largest_parties_2021"]["unresolved_communes"] == 1
    assert analyses["hcp_population_context"]["observations"]["population_legal_2014"]["total_persons"] == 300
    assert "Limite:" in render_text(result)
