"""Guard single-review visual BO 6374 transcriptions from becoming official universes."""

from __future__ import annotations

from typing import Any, Mapping


def validate_visual_candidate(payload: Mapping[str, Any], source: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("status") != "VISUAL_SINGLE_REVIEW_CANDIDATE_ONLY" or payload.get("official_universe_allowed") is not False:
        issues.append("single-review visual transcription cannot claim an official universe")
    if payload.get("source_id") != source.get("source_id") or payload.get("source_sha256") != source.get("sha256"):
        issues.append("visual transcription does not match its pinned official source")
    page_index = payload.get("pdf_page_index")
    if not isinstance(page_index, int) or not 34 <= page_index <= 65 or payload.get("printed_page") != page_index + 6071:
        issues.append("visual transcription references a page outside the original decree annex")
    rows = [row for group in payload.get("groups", []) for row in group.get("rows", [])]
    if not rows or [row.get("row") for row in rows] != list(range(1, len(rows) + 1)):
        issues.append("visual transcription row ordinals are missing or discontinuous")
    for group in payload.get("groups", []):
        if not group.get("prefecture_province_ar") or not group.get("rows"):
            issues.append("visual transcription group lacks parent or rows")
    for row in rows:
        seats = row.get("council_members")
        if not row.get("commune_name_ar") or not isinstance(seats, int) or isinstance(seats, bool) or seats <= 0:
            issues.append(f"visual transcription row {row.get('row')} lacks a name or positive member count")
        if any(key in row for key in ("official_contest_id", "official_council_id", "universe_id")):
            issues.append(f"visual transcription row {row.get('row')} cannot assert an official electoral identifier")
    return issues
