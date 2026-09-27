from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb


DEFAULT_PROFILE = Path(__file__).with_name("profiles") / "current_snapshot.json"


def validate_acceptance_profile(database: Path, profile: Path = DEFAULT_PROFILE) -> dict[str, Any]:
    expected = json.loads(profile.read_text(encoding="utf-8"))
    connection = duckdb.connect(str(database.resolve()), read_only=True)
    failures: list[dict[str, str]] = []
    try:
        checks = {
            "contest_results": ("mart_contest_results", "analytical_result_id", "SELECT count(*) FROM mart_contest_results"),
            "available_competitiveness": (
                "mart_contest_competitiveness", "contest_id,election_id,ballot_type",
                "SELECT count(*) FROM mart_contest_competitiveness WHERE metric_status='AVAILABLE'",
            ),
            "ballot_types": ("mart_contest_results", "ballot_type", "SELECT count(DISTINCT ballot_type) FROM mart_contest_results"),
            "unresolved_identities": ("mart_contest_results", "identity_status", "SELECT count(*) FROM mart_contest_results WHERE identity_status='UNRESOLVED'"),
        }
        for name, (table, key, sql) in checks.items():
            observed = connection.execute(sql).fetchone()[0]
            if observed != expected[name]:
                failures.append({"table": table, "key": key, "rule": f"PROFILE:{name}", "observed": str(observed), "expected": str(expected[name])})
    finally:
        connection.close()
    return {"status": "PASS" if not failures else "FAIL", "profile": str(profile), "failures": failures}
