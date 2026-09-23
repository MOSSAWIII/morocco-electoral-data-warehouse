from __future__ import annotations

from pathlib import Path

from morocco_elections.warehouse.result_universes import load_chamber_2021_seat_universe


ROOT = Path(__file__).resolve().parents[2]


def test_chamber_2021_national_seat_universe_is_source_derived() -> None:
    source = ROOT / "data/raw/elections/warehouse/results/chamber_legislative_2021.html"
    universe, members = load_chamber_2021_seat_universe(
        source, source_url="https://www.chambredesrepresentants.ma/official",
        acquired_at="2026-09-23",
    )
    assert universe["election_id"] == "LEG2021"
    assert universe["universe_type"] == "OFFICIAL_SEAT_ALLOCATIONS"
    assert universe["denominator"] == len(members) == 12
    assert sum(row["expected_value"] for row in members) == 395
    assert {row["expected_id"] for row in members} == {
        "RNI", "PAM", "PI", "USFP", "MP", "PPS", "UC", "PJD", "MDS", "FFD", "CNI", "PSU",
    }
    assert {row["unit"] for row in members} == {"seats"}
