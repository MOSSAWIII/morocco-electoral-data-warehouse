"""Honest inventory of result-history evidence already present in the repository."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.v16.validation import _as_date
from morocco_elections.v16.versions import validate_revisions


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _acquisition_dates(repository_root: Path) -> dict[str, str]:
    dates: dict[str, str] = {}
    acquisitions = repository_root / "data/raw/elections/acquisitions"
    if not acquisitions.is_dir():
        return dates
    for path in acquisitions.rglob("acquisition.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        source_id, acquired_at = payload.get("source_id"), payload.get("retrieved_at")
        if isinstance(source_id, str) and isinstance(acquired_at, str):
            dates[source_id] = acquired_at
    return dates


def build_result_history_diagnostic(
    connection: duckdb.DuckDBPyConnection,
    repository_root: Path,
    as_of_date: str,
) -> dict[str, Any]:
    """Inventory result scopes without promoting archival values to official statuses."""
    acquisition_dates = _acquisition_dates(repository_root)
    elections = connection.execute(
        "SELECT election_id, election_date, official_results_date, publication_date, retrieval_date "
        "FROM dim_election ORDER BY election_date, election_id"
    ).fetchall()
    source_rows: dict[str, set[str]] = defaultdict(set)
    type_rows: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, dict[str, int]] = defaultdict(dict)
    specifications = (
        ("fact_election_result", "PARTY_RESULT"),
        ("fact_communal_election_result", "COMMUNAL_PARTY_RESULT"),
        ("fact_electoral_mobilization", "MOBILIZATION"),
    )
    for table, result_type in specifications:
        for election_id, source_id, count in connection.execute(
            f'SELECT election_id, source_id, count(*) FROM "{table}" GROUP BY ALL'
        ).fetchall():
            if source_id:
                source_rows[str(election_id)].add(str(source_id))
            type_rows[str(election_id)].add(result_type)
            counts[str(election_id)][table] = int(count)

    contest_counts = {
        str(election_id): int(count)
        for election_id, count in connection.execute(
            "SELECT election_id, count(*) FROM dim_electoral_contest GROUP BY election_id"
        ).fetchall()
    }
    inventory: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for election_id, election_date, official_results_date, publication_date, retrieval_date in elections:
        election_id = str(election_id)
        source_ids = sorted(source_rows[election_id])
        contest_count = contest_counts.get(election_id, 0)
        available_dates = {
            "official_results_date": _iso(official_results_date),
            "publication_date": _iso(publication_date),
            "election_metadata_retrieval_date": _iso(retrieval_date),
            "result_source_acquired_at": {
                source_id: acquisition_dates[source_id]
                for source_id in source_ids if source_id in acquisition_dates
            },
        }
        in_scope = contest_count > 0
        row = {
            "election_id": election_id,
            "election_date": _iso(election_date),
            "contest_count": contest_count,
            "result_row_counts": counts[election_id],
            "result_types_present": sorted(type_rows[election_id]),
            "source_ids": source_ids,
            "source_declared_result_statuses": [],
            "available_dates": available_dates,
            "history_or_rectification_available": False,
            "official_status_provable": False,
            "additional_official_source_required": in_scope,
        }
        inventory.append(row)
        if in_scope:
            gaps.append({
                "scope_type": "ELECTION",
                "scope_id": election_id,
                "contest_count": contest_count,
                "source_ids_searched": source_ids,
                "required_source": "Competent-authority result publication or decision with explicit status and dates",
                "availability_status": "VALUES_PRESENT_WITHOUT_OFFICIAL_STATUS_HISTORY",
                "publication_consequence": "Results remain unqualified; no FINAL/PROCLAIMED/RECTIFIED/ANNULLED status may be published",
                "blocking_code": "OFFICIAL_RESULT_STATUS_NOT_PROVEN",
            })

    revision_cursor = connection.execute("SELECT * FROM fact_result_revision")
    revision_columns = [item[0] for item in revision_cursor.description]
    revisions = [dict(zip(revision_columns, values, strict=True)) for values in revision_cursor.fetchall()]
    revision_count = len(revisions)
    revision_issues = validate_revisions(revisions)
    chain_error_codes = {
        "MISSING_SUPERSEDED_REVISION", "BROKEN_REVISION_CHAIN", "CYCLIC_REVISION_CHAIN",
        "CROSS_RESULT_REVISION_CHAIN", "MULTIPLE_REVISION_ROOTS", "OVERLAPPING_RESULT_REVISIONS",
        "SUPERSEDED_REVISION_STILL_OPEN", "INVALID_REVISION_VALIDITY",
    }
    broken_results = {
        row.get("result_id")
        for row in revisions
        if any(issue.record_id in {str(row.get("revision_id")), str(row.get("result_id"))} and issue.code in chain_error_codes for issue in revision_issues)
    }
    as_of = _as_date(as_of_date)
    post_as_of = sum(
        1 for row in revisions
        if any(
            value is not None and as_of is not None and value > as_of
            for value in (_as_date(row.get("valid_from")), _as_date(row.get("published_at")), _as_date(row.get("known_at")))
        )
    )
    insufficient = sum(
        1 for row in revisions
        if row.get("verification_method") != "STRUCTURED_SOURCE_CLAIM" or row.get("verification_status") != "VERIFIED"
    )
    result_rows = connection.execute("SELECT count(*) FROM fact_election_result").fetchone()[0]
    communal_rows = connection.execute("SELECT count(*) FROM fact_communal_election_result").fetchone()[0]
    return {
        "schema_version": "1.0.0",
        "as_of_date": as_of_date,
        "inventory": inventory,
        "gaps": gaps,
        "diagnostic": {
            "elections_inventoried": len(inventory),
            "contests_concerned": sum(contest_counts.values()),
            "result_rows_concerned": int(result_rows + communal_rows),
            "official_status_proven": revision_count - insufficient,
            "with_published_at": sum(row.get("published_at") is not None for row in revisions),
            "with_known_at": sum(row.get("known_at") is not None for row in revisions),
            "with_valid_from": sum(row.get("valid_from") is not None for row in revisions),
            "without_available_history": sum(contest_counts.values()) - len({row.get("contest_id") for row in revisions}),
            "complete_revision_chains": len({row.get("result_id") for row in revisions} - broken_results),
            "broken_revision_chains": len(broken_results),
            "cycles": sum(issue.code == "CYCLIC_REVISION_CHAIN" for issue in revision_issues),
            "validity_overlaps": sum(issue.code == "OVERLAPPING_RESULT_REVISIONS" for issue in revision_issues),
            "post_as_of_records": post_as_of,
            "invented_or_insufficiently_sourced_statuses": insufficient,
        },
    }
