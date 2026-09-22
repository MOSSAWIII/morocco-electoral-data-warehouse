from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping

from morocco_elections.v16.validation import ValidationIssue, _as_date, validate_rows


STATUS_PRIORITY = {"SCHEDULED": 0, "POLL_CLOSED": 1, "PROVISIONAL": 2, "PROCLAIMED": 3, "CONTESTED": 4, "FINAL": 5, "RECTIFIED": 6, "ANNULLED": 7}

ALLOWED_TRANSITIONS = {
    "SCHEDULED": frozenset({"POLL_CLOSED", "ANNULLED"}),
    "POLL_CLOSED": frozenset({"PROVISIONAL", "PROCLAIMED", "CONTESTED", "ANNULLED"}),
    "PROVISIONAL": frozenset({"PROCLAIMED", "CONTESTED", "RECTIFIED", "ANNULLED", "FINAL"}),
    "PROCLAIMED": frozenset({"CONTESTED", "RECTIFIED", "ANNULLED", "FINAL"}),
    "CONTESTED": frozenset({"RECTIFIED", "ANNULLED", "FINAL"}),
    "FINAL": frozenset({"CONTESTED", "RECTIFIED", "ANNULLED"}),
    "RECTIFIED": frozenset({"CONTESTED", "RECTIFIED", "ANNULLED", "FINAL"}),
    "ANNULLED": frozenset(),
}


def validate_revisions(rows: Iterable[Mapping[str, Any]]) -> list[ValidationIssue]:
    rows = list(rows)
    issues = validate_rows("fact_result_revision", rows)
    by_id = {row.get("revision_id"): row for row in rows}
    ids = set(by_id)
    roots_by_result: dict[Any, list[Any]] = {}
    for row in rows:
        record_id = str(row.get("revision_id", "<unknown>"))
        parent_id = row.get("supersedes_revision_id")
        if parent_id is None:
            roots_by_result.setdefault(row.get("result_id"), []).append(row.get("revision_id"))
        if row.get("result_status") in {"RECTIFIED", "ANNULLED"} and parent_id not in ids:
            issues.append(ValidationIssue("MISSING_SUPERSEDED_REVISION", "fact_result_revision", record_id, "rectified/annulled revision must point to a retained earlier revision"))
        if row.get("decision_id") is None and row.get("result_status") == "ANNULLED":
            issues.append(ValidationIssue("ANNULMENT_DECISION_REQUIRED", "fact_result_revision", record_id, "annulled result must reference a legal decision"))
        if parent_id is not None:
            parent = by_id.get(parent_id)
            if parent is None:
                issues.append(ValidationIssue("BROKEN_REVISION_CHAIN", "fact_result_revision", record_id, "superseded revision does not exist"))
                continue
            if parent_id == row.get("revision_id"):
                issues.append(ValidationIssue("CYCLIC_REVISION_CHAIN", "fact_result_revision", record_id, "revision cannot supersede itself"))
            if parent.get("result_id") != row.get("result_id"):
                issues.append(ValidationIssue("CROSS_RESULT_REVISION_CHAIN", "fact_result_revision", record_id, "revision cannot supersede a different result"))
            previous, current = parent.get("result_status"), row.get("result_status")
            if previous in ALLOWED_TRANSITIONS and current not in ALLOWED_TRANSITIONS[previous]:
                issues.append(ValidationIssue("INVALID_RESULT_STATUS_TRANSITION", "fact_result_revision", record_id, f"{previous} -> {current} is forbidden"))
            parent_published, published = _as_date(parent.get("published_at")), _as_date(row.get("published_at"))
            parent_known, known = _as_date(parent.get("known_at")), _as_date(row.get("known_at"))
            parent_start, parent_end = _as_date(parent.get("valid_from")), _as_date(parent.get("valid_to"))
            current_start = _as_date(row.get("valid_from"))
            if parent_end is None:
                issues.append(ValidationIssue("SUPERSEDED_REVISION_STILL_OPEN", "fact_result_revision", record_id, "superseded revision must have a finite valid_to"))
            elif current_start is not None and parent_end >= current_start:
                issues.append(ValidationIssue("OVERLAPPING_RESULT_REVISIONS", "fact_result_revision", record_id, "successive revisions cannot have overlapping validity"))
            if parent_start is not None and current_start is not None and current_start <= parent_start:
                issues.append(ValidationIssue("REVISION_VALIDITY_TIME_REVERSED", "fact_result_revision", record_id, "revision valid_from must follow its predecessor"))
            if parent_published and published and published < parent_published:
                issues.append(ValidationIssue("REVISION_PUBLICATION_TIME_REVERSED", "fact_result_revision", record_id, "revision was published before its predecessor"))
            if parent_known and known and known < parent_known:
                issues.append(ValidationIssue("REVISION_KNOWLEDGE_TIME_REVERSED", "fact_result_revision", record_id, "revision was known before its predecessor"))
        published, known = _as_date(row.get("published_at")), _as_date(row.get("known_at"))
        if published and known and known < published:
            issues.append(ValidationIssue("KNOWN_BEFORE_PUBLISHED", "fact_result_revision", record_id, "known_at cannot precede published_at"))

    for result_id, roots in roots_by_result.items():
        result_rows = [row for row in rows if row.get("result_id") == result_id]
        count = len(result_rows)
        if count > 1 and len(roots) != 1:
            issues.append(ValidationIssue("MULTIPLE_REVISION_ROOTS", "fact_result_revision", str(result_id), "a result revision chain must have exactly one root"))
        for index, left in enumerate(result_rows):
            left_start, left_end = _as_date(left.get("valid_from")), _as_date(left.get("valid_to"))
            if left_start is not None and left_end is not None and left_end < left_start:
                issues.append(ValidationIssue("INVALID_REVISION_VALIDITY", "fact_result_revision", str(left.get("revision_id")), "valid_to precedes valid_from"))
            for right in result_rows[index + 1:]:
                right_start, right_end = _as_date(right.get("valid_from")), _as_date(right.get("valid_to"))
                if left_start is None or right_start is None:
                    continue
                if (left_end is None or right_start <= left_end) and (right_end is None or left_start <= right_end):
                    issues.append(ValidationIssue("OVERLAPPING_RESULT_REVISIONS", "fact_result_revision", str(result_id), "two revisions are applicable during the same period"))

    for start_id in ids:
        current, visited = start_id, set()
        while current is not None and current in by_id:
            if current in visited:
                issues.append(ValidationIssue("CYCLIC_REVISION_CHAIN", "fact_result_revision", str(start_id), "revision chain contains a cycle"))
                break
            visited.add(current)
            current = by_id[current].get("supersedes_revision_id")
    return issues


def applicable_revision(rows: Iterable[Mapping[str, Any]], result_id: str, as_of_date: date | str) -> Mapping[str, Any] | None:
    """Return the deterministic revision applicable at the end of ``as_of_date``."""
    as_of = _as_date(as_of_date)
    if as_of is None:
        raise ValueError("as_of_date must be an ISO date")
    candidates = []
    for row in rows:
        start, end = _as_date(row.get("valid_from")), _as_date(row.get("valid_to"))
        published_date, known_date = _as_date(row.get("published_at")), _as_date(row.get("known_at"))
        if (
            row.get("result_id") == result_id
            and start and start <= as_of and (end is None or as_of <= end)
            and published_date and published_date <= as_of
            and known_date and known_date <= as_of
        ):
            published = row.get("published_at")
            if isinstance(published, datetime):
                published_key = published.isoformat()
            else:
                published_key = str(published)
            candidates.append((start.isoformat(), published_key, STATUS_PRIORITY.get(str(row.get("result_status")), 0), str(row["revision_id"]), row))
    return max(candidates, default=(None, None, None, None, None))[-1]
