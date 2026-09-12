from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from typing import Any


LEGISLATURES = (
    {
        "legislature_id": "LEGISLATURE_10",
        "legislature": "2016-2021",
        "chamber": "house_of_representatives",
        "start_date": "2016-10-14",
        "end_date": "2021-10-07",
        "boundary_status": "OFFICIAL_OPENING_DATES",
        "source_url": "https://www.chambredesrepresentants.ma/fr/node/238313",
    },
    {
        "legislature_id": "LEGISLATURE_11",
        "legislature": "2021-2026",
        "chamber": "house_of_representatives",
        "start_date": "2021-10-08",
        "end_date": None,
        "boundary_status": "OFFICIAL_START_ONGOING_AT_SNAPSHOT",
        "source_url": "https://www.chambredesrepresentants.ma/fr/taxonomy/term/10833?page=1",
    },
)


def _text(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).strip().split())


def _key(value: Any) -> str:
    return _text(value).casefold()


def _stable_id(prefix: str, *values: Any) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:32].upper()}"


def _period_type(label: str) -> str:
    normalized = _key(label)
    if "بين دورتي" in normalized:
        return "intersession"
    if "دورة" in normalized or "أكتوبر" in normalized or "أبريل" in normalized:
        return "ordinary_session_label"
    return "unknown"


def _source_session_type(source_family_id: str) -> str:
    source = source_family_id.upper()
    if "APR_OCT" in source:
        return "april_to_october_intersession"
    if "OCT_APR" in source:
        return "october_to_april_intersession"
    if "APRIL" in source:
        return "april_session"
    if "OCTOBER" in source:
        return "october_session"
    return "mixed_or_undocumented"


def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]


def _legislature_for_date(value: str) -> str:
    matches = [
        row["legislature"] for row in LEGISLATURES
        if row["start_date"] <= value and (row["end_date"] is None or value <= row["end_date"])
    ]
    if len(matches) != 1:
        raise RuntimeError(f"date hors des législatures officielles V14.1: {value}")
    return matches[0]


def apply_analytical_validity(
    base_tables: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Return a V14.1 model without mutating the immutable V14 tables."""
    tables = {
        name: [dict(row) for row in rows]
        for name, rows in base_tables.items()
        if name != "dim_parliamentary_author"
    }
    questions = tables["fact_parliamentary_question"]
    for row in questions:
        row["legislature"] = _legislature_for_date(row["deposit_date"])
    question_by_id = {row["question_id"]: row for row in questions}
    old_periods = {row["period_id"]: row for row in tables["dim_parliamentary_period"]}

    period_questions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in questions:
        period_questions[(row["legislature"], row["period_id"])].append(row)
    period_map: dict[tuple[str, str], str] = {}
    periods: list[dict[str, Any]] = []
    for (legislature, old_id), rows in sorted(period_questions.items()):
        label = old_periods[old_id]["period_label_ar"]
        period_type = _period_type(label)
        observed_start = min(row["deposit_date"] for row in rows)
        observed_end = max(row["deposit_date"] for row in rows)
        period_id = _stable_id(
            "PERIOD_V14_1", legislature, period_type, observed_start, observed_end
        )
        period_map[(legislature, old_id)] = period_id
        periods.append(
            {
                "period_id": period_id,
                "legislature_id": "LEGISLATURE_10" if legislature == "2016-2021" else "LEGISLATURE_11",
                "legislature": legislature,
                "period_type": period_type,
                "period_label_ar": label,
                "start_date": observed_start,
                "end_date": observed_end,
                "date_semantics": "OBSERVED_DEPOSIT_BOUNDS",
                "observed_deposit_start": observed_start,
                "observed_deposit_end": observed_end,
                "official_start_date": None,
                "official_end_date": None,
                "boundary_method": "OBSERVED_CORPUS_BOUNDS_NOT_OFFICIAL_SESSION_DATES",
            }
        )
    for row in questions:
        row["period_id"] = period_map[(row["legislature"], row["period_id"])]
        row["response_status"] = (
            "published_response_date_present"
            if row["response_status"] == "answered"
            else "no_response_date_published"
        )
        row["quality_status"] = "source_integrity_verified"
    tables["dim_parliamentary_period"] = periods
    tables["dim_legislature"] = [dict(row) for row in LEGISLATURES]

    authors = []
    author_map: dict[str, str] = {}
    for row in base_tables["dim_parliamentary_author"]:
        source_id = row["author_id"].replace("AUTHOR_V14_", "AUTHOR_SOURCE_V14_1_")
        author_map[row["author_id"]] = source_id
        authors.append(
            {
                "author_source_id": source_id,
                "legislature": row["legislature"],
                "person_id": row["person_id"],
                "identity_match_method": row["identity_match_method"],
                "identity_scope": "SOURCE_LABEL_NOT_CERTAIN_HUMAN_IDENTITY",
            }
        )
    tables["dim_parliamentary_source_author"] = authors
    for row in tables["bridge_question_author"]:
        row["author_source_id"] = author_map[row.pop("author_id")]
        row["author_role"] = "published_author_source_unit"
        row["coauthor_parsing_status"] = "NOT_SPLIT_WITHOUT_DOCUMENTED_SOURCE_SEMANTICS"

    for row in tables["analytical_parliamentary_trajectory"]:
        row["period_id"] = period_map[(row["legislature"], row["period_id"])]
        row["published_question_count"] = row.pop("question_count")
        row["published_response_date_count"] = row.pop("answered_question_count")
        row["published_response_date_rate_pct"] = row.pop("response_rate_pct")

    links_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in tables["bridge_question_source"]:
        links_by_source[link["source_id"]].append(question_by_id[link["question_id"]])
    period_types_by_id = {row["period_id"]: row["period_type"] for row in periods}
    for source in tables["dim_parliamentary_source"]:
        linked = links_by_source[source["source_id"]]
        source["coverage_start"] = min(row["deposit_date"] for row in linked)
        source["coverage_end"] = max(row["deposit_date"] for row in linked)
        source["observed_through_date"] = None
        session_type = _source_session_type(source["source_family_id"])
        linked_period_types = {period_types_by_id[row["period_id"]] for row in linked}
        if session_type == "mixed_or_undocumented" and linked_period_types == {"intersession"}:
            session_type = "intersession"
        source["session_type"] = session_type
        source["coverage_status"] = "UNKNOWN"
        source["coverage_reason"] = "NO_OFFICIAL_EXPECTED_FILE_OR_QUESTION_DENOMINATOR"

    coverage_groups: dict[tuple[str, str, int, str, str], dict[str, set[str]]] = defaultdict(
        lambda: {"questions": set(), "sources": set()}
    )
    sources = {row["source_id"]: row for row in tables["dim_parliamentary_source"]}
    for link in tables["bridge_question_source"]:
        question = question_by_id[link["question_id"]]
        session_type = sources[link["source_id"]]["session_type"]
        grain = (
            "house_of_representatives", question["legislature"],
            int(question["deposit_date"][:4]), session_type, question["question_type"],
        )
        coverage_groups[grain]["questions"].add(question["question_id"])
        coverage_groups[grain]["sources"].add(link["source_id"])
    tables["analytical_parliamentary_coverage"] = [
        {
            "coverage_id": _stable_id("COVERAGE_V14_1", *grain),
            "chamber": grain[0], "legislature": grain[1], "calendar_year": grain[2],
            "session_type": grain[3], "question_type": grain[4],
            "expected_file_count": None,
            "found_file_count": len(values["sources"]),
            "observed_deposit_start": min(
                question_by_id[question_id]["deposit_date"] for question_id in values["questions"]
            ),
            "observed_deposit_end": max(
                question_by_id[question_id]["deposit_date"] for question_id in values["questions"]
            ),
            "published_question_count": len(values["questions"]),
            "coverage_status": "UNKNOWN",
            "justification": "OFFICIAL_DENOMINATOR_NOT_DEMONSTRATED",
        }
        for grain, values in sorted(coverage_groups.items())
    ]

    groups_by_key = {
        (row["legislature"], _key(row["group_name_ar_raw"])): row["group_id"]
        for row in tables["dim_parliamentary_group"]
    }
    affiliations = []
    for mandate in tables["fact_parliamentary_mandate"]:
        group_id = groups_by_key.get((mandate["legislature"], _key(mandate["parliamentary_group"])))
        affiliations.append(
            {
                "affiliation_id": _stable_id("AFFILIATION_V14_1", mandate["mandate_id"]),
                "mandate_id": mandate["mandate_id"], "person_id": mandate["person_id"],
                "party_id": mandate["party_id"], "group_id": group_id,
                "valid_from": _iso(mandate["start_date"]), "valid_to": _iso(mandate["end_date"]),
                "validity_method": "PARLIAMENTARY_MANDATE_INTERVAL",
                "source_id": mandate["source_id"],
            }
        )
    tables["bridge_person_parliamentary_affiliation"] = affiliations

    affiliations_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for affiliation in affiliations:
        affiliations_by_person[affiliation["person_id"]].append(affiliation)
    for link in tables["bridge_question_author"]:
        if not link["person_id"]:
            link["party_id"] = None
            link["affiliation_method"] = "NO_CANONICAL_PERSON_LINK"
            continue
        deposit_date = question_by_id[link["question_id"]]["deposit_date"]
        applicable = [
            row for row in affiliations_by_person[link["person_id"]]
            if row["valid_from"] <= deposit_date
            and (row["valid_to"] is None or deposit_date <= row["valid_to"])
        ]
        parties = {row["party_id"] for row in applicable if row["party_id"]}
        link["party_id"] = next(iter(parties)) if len(parties) == 1 else None
        link["affiliation_method"] = (
            "MANDATE_INTERVAL_AT_DEPOSIT_DATE" if len(parties) == 1
            else "UNRESOLVED_AFFILIATION_INTERVAL"
        )
    trajectory_parties: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for link in tables["bridge_question_author"]:
        if link["person_id"] and link["party_id"]:
            question = question_by_id[link["question_id"]]
            trajectory_parties[
                (link["person_id"], question["period_id"], question["question_type"])
            ].add(link["party_id"])
    for trajectory in tables["analytical_parliamentary_trajectory"]:
        parties = trajectory_parties[
            (trajectory["person_id"], trajectory["period_id"], trajectory["question_type"])
        ]
        trajectory["party_id"] = next(iter(parties)) if len(parties) == 1 else None
        trajectory["party_assignment_method"] = (
            "MANDATE_INTERVAL_AT_DEPOSIT_DATE" if len(parties) == 1
            else "UNRESOLVED_OR_MULTIPLE_WITHIN_TRAJECTORY"
        )

    author_links_by_question = defaultdict(list)
    for link in tables["bridge_question_author"]:
        author_links_by_question[link["question_id"]].append(link)
    counts: Counter[tuple[str, str, str]] = Counter()
    responses: Counter[tuple[str, str, str]] = Counter()
    for question in questions:
        for link in author_links_by_question[question["question_id"]]:
            if link["person_id"]:
                grain = (link["person_id"], question["period_id"], question["question_type"])
                counts[grain] += 1
                responses[grain] += question["response_status"] == "published_response_date_present"
    exposure_intervals: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    period_types = {
        (period["period_id"], question_type)
        for period in periods
        for question_type in {q["question_type"] for q in questions if q["period_id"] == period["period_id"]}
    }
    for mandate in tables["fact_parliamentary_mandate"]:
        start = _iso(mandate["start_date"])
        end = _iso(mandate["end_date"])
        if not start:
            continue
        for period_id, question_type in period_types:
            period = next(row for row in periods if row["period_id"] == period_id)
            if period["legislature"] != mandate["legislature"]:
                continue
            overlap_start = max(start, period["observed_deposit_start"])
            overlap_end = min(end or period["observed_deposit_end"], period["observed_deposit_end"])
            if overlap_start > overlap_end:
                continue
            grain = (mandate["person_id"], period_id, question_type)
            exposure_intervals[grain].append((overlap_start, overlap_end))
    exposure = []
    for grain, intervals in sorted(exposure_intervals.items()):
        covered_dates: set[date] = set()
        for start, end in intervals:
            cursor = date.fromisoformat(start)
            last = date.fromisoformat(end)
            while cursor <= last:
                covered_dates.add(cursor)
                cursor = date.fromordinal(cursor.toordinal() + 1)
        observed_days = len(covered_dates)
        published = counts[grain]
        exposure.append(
            {
                "person_period_exposure_id": _stable_id("EXPOSURE_V14_1", *grain),
                "person_id": grain[0], "period_id": grain[1], "question_type": grain[2],
                "observed_mandate_days": observed_days, "active_in_observed_window": True,
                "published_question_count": published,
                "published_response_date_count": responses[grain],
                "published_questions_per_100_observed_mandate_days": round(100 * published / observed_days, 6),
                "denominator_status": "OBSERVED_CORPUS_WINDOW_NOT_OFFICIAL_SESSION_DURATION",
            }
        )
    tables["analytical_person_period_exposure"] = exposure

    author_counts = Counter(link["author_source_id"] for link in tables["bridge_question_author"])
    outlier_id, outlier_count = author_counts.most_common(1)[0]
    outlier_qids = {
        link["question_id"] for link in tables["bridge_question_author"]
        if link["author_source_id"] == outlier_id
    }
    outlier_questions = [question_by_id[qid] for qid in outlier_qids]
    source_links = [
        link for link in tables["bridge_question_source"] if link["question_id"] in outlier_qids
    ]
    linked_author = next(row for row in authors if row["author_source_id"] == outlier_id)
    annual_distribution = Counter(row["deposit_date"][:4] for row in outlier_questions)
    tables["parliamentary_outlier_audit"] = [{
        "outlier_audit_id": "OUTLIER_V14_1_MAX_PUBLISHED_QUESTIONS",
        "author_source_id": outlier_id,
        "person_id": linked_author["person_id"],
        "published_question_count": outlier_count,
        "distinct_question_number_count": len({row["source_question_number"] for row in outlier_questions}),
        "distinct_question_text_count": len({row["question_text_ar"] for row in outlier_questions}),
        "duplicate_text_occurrence_count": outlier_count - len({row["question_text_ar"] for row in outlier_questions}),
        "distinct_source_count": len({row["source_id"] for row in source_links}),
        "dataset_source_count_reviewed": len(tables["dim_parliamentary_source"]),
        "annual_published_question_counts_json": json.dumps(
            dict(sorted(annual_distribution.items())), separators=(",", ":")
        ),
        "first_deposit_date": min(row["deposit_date"] for row in outlier_questions),
        "last_deposit_date": max(row["deposit_date"] for row in outlier_questions),
        "source_label_nature": "INDIVIDUAL_PUBLIC_OFFICEHOLDER_LABEL",
        "mandate_link_status": "EXACT_UNICODE_SAME_LEGISLATURE",
        "outlier_review_status": "reviewed_valid",
        "treatment": "PRESERVED_NO_REMOVAL_NO_WINSORIZATION",
    }]
    return tables
