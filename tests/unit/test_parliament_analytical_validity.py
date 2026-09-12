from __future__ import annotations

from morocco_elections.domains.parliament.analytical_validity import apply_analytical_validity


def _base_tables() -> dict[str, list[dict]]:
    return {
        "dim_parliamentary_period": [{"period_id": "OLD", "period_label_ar": "دورة أبريل 2022", "period_key": "x"}],
        "dim_parliamentary_author": [{"author_id": "AUTHOR_V14_A", "legislature": "2021-2026", "person_id": "P1", "identity_match_method": "unicode_exact_legislature"}],
        "dim_parliamentary_source": [{"source_id": "S1", "source_family_id": "WRITTEN_APRIL", "retrieved_at": "2026-01-01"}],
        "dim_parliamentary_group": [{"group_id": "G1", "legislature": "2021-2026", "group_name_ar_raw": "مجموعة", "group_key": "مجموعة"}],
        "fact_parliamentary_question": [{"question_id": "Q1", "question_type": "written", "source_question_number": "1", "deposit_date": "2022-04-10", "legislature": "2021-2026", "period_id": "OLD", "question_text_ar": "سؤال", "response_status": "unanswered_as_published", "quality_status": "verified_source_deduplicated"}],
        "fact_parliamentary_response": [],
        "bridge_question_author": [{"question_author_id": "QA1", "question_id": "Q1", "author_id": "AUTHOR_V14_A", "person_id": "P1", "party_id": "PTY", "group_id": "G1", "affiliation_method": "mandate_party_same_legislature"}],
        "bridge_question_source": [{"question_source_id": "QS1", "question_id": "Q1", "source_id": "S1", "source_row": 2, "source_sha256": "a" * 64}],
        "analytical_parliamentary_trajectory": [{"trajectory_id": "T1", "person_id": "P1", "party_id": "PTY", "legislature": "2021-2026", "period_id": "OLD", "question_type": "written", "question_count": 1, "answered_question_count": 0, "response_rate_pct": 0.0, "first_deposit_date": "2022-04-10", "last_deposit_date": "2022-04-10", "derivation_status": "DERIVED_FROM_PUBLISHED_QUESTIONS"}],
        "fact_parliamentary_mandate": [{"mandate_id": "M1", "person_id": "P1", "legislature": "2021-2026", "party_id": "PTY", "parliamentary_group": "مجموعة", "start_date": "2021-10-08", "end_date": None, "source_id": "MS1"}],
        "dim_person_public": [{"person_id": "P1"}],
        "dim_party": [{"party_id": "PTY"}],
    }


def test_validity_layer_renames_semantics_and_keeps_zero_capable_spine() -> None:
    model = apply_analytical_validity(_base_tables())
    question = model["fact_parliamentary_question"][0]
    trajectory = model["analytical_parliamentary_trajectory"][0]
    exposure = model["analytical_person_period_exposure"][0]

    assert question["response_status"] == "no_response_date_published"
    assert question["quality_status"] == "source_integrity_verified"
    assert trajectory["published_question_count"] == 1
    assert "response_rate_pct" not in trajectory
    assert exposure["observed_mandate_days"] == 1
    assert exposure["published_question_count"] == 1


def test_author_source_is_not_claimed_as_human_identity() -> None:
    model = apply_analytical_validity(_base_tables())
    author = model["dim_parliamentary_source_author"][0]
    link = model["bridge_question_author"][0]

    assert author["author_source_id"].startswith("AUTHOR_SOURCE_V14_1_")
    assert author["identity_scope"] == "SOURCE_LABEL_NOT_CERTAIN_HUMAN_IDENTITY"
    assert link["author_role"] == "published_author_source_unit"
    assert link["affiliation_method"] == "MANDATE_INTERVAL_AT_DEPOSIT_DATE"


def test_coverage_never_becomes_complete_without_official_denominator() -> None:
    model = apply_analytical_validity(_base_tables())

    assert model["dim_parliamentary_source"][0]["observed_through_date"] is None
    assert model["analytical_parliamentary_coverage"][0]["expected_file_count"] is None
    assert model["analytical_parliamentary_coverage"][0]["coverage_status"] == "UNKNOWN"
