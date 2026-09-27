from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MartContract:
    sql_file: str
    dependencies: tuple[str, ...]
    grain: str
    key: tuple[str, ...]


MART_CONTRACTS = {
    "mart_contest_results": MartContract("01_mart_contest_results.sql", (), "result x contest x ballot", ("analytical_result_id",)),
    "mart_contest_competitiveness": MartContract(
        "02_mart_contest_competitiveness.sql", (), "contest x election x ballot", ("contest_id", "election_id", "ballot_type")
    ),
    "mart_party_performance": MartContract(
        "03_mart_party_performance.sql", ("mart_contest_results",), "party x election x ballot", ("party_performance_id",)
    ),
    "mart_geography_profile": MartContract(
        "04_mart_geography_profile.sql", ("mart_contest_results", "mart_contest_competitiveness"),
        "geography x election x ballot", ("geography_profile_id",),
    ),
    "mart_parliamentary_activity": MartContract(
        "05_mart_parliamentary_activity.sql", (), "person x party x legislature x period x question type",
        ("parliamentary_activity_id",),
    ),
}

METRIC_STATUSES = frozenset({"AVAILABLE", "LIMITED", "NOT_AVAILABLE"})
SQL_DIRECTORY = Path(__file__).with_name("sql")
