from __future__ import annotations

from morocco_elections.analysis.v12 import summarize


def test_summary_keeps_scope_denominators_and_unlinked_rows_explicit() -> None:
    rows = [
        {"question_id": "Q1", "period_raw": "P1", "person_id": "A", "response_date": "2023-01-01"},
        {"question_id": "Q2", "period_raw": "P2", "person_id": "A", "response_date": None},
        {"question_id": "Q3", "period_raw": "P2", "person_id": None, "response_date": None},
    ]
    report = summarize(rows)
    assert report["questions"] == 3
    assert report["answered"] == 1
    assert report["identity_rows_linked"] == 2
    assert report["identity_rows_unlinked"] == 1
    assert report["linked_people_by_active_segment_count"]["2"] == 1
