from __future__ import annotations

import json
from pathlib import Path

from morocco_elections.exports import open_v14_1


ROOT = Path(__file__).resolve().parents[2]


def _manifest() -> dict:
    return json.loads((ROOT / "metadata/v14_1_open_distribution.json").read_text(encoding="utf-8"))


def test_tracked_v14_1_contract_is_valid_and_readme_is_generated() -> None:
    manifest = _manifest()

    assert open_v14_1.validate_manifest(manifest) == []
    assert len(manifest["tables"]) == 31
    assert manifest["controls"]["published_question_count"] == 65_748
    assert manifest["controls"]["person_period_zero_question_rows"] > 0
    assert manifest["controls"]["coverage_complete_rows"] == 0
    assert (ROOT / "docs/publication/V14_1_OPEN_DATA_README.txt").read_text(
        encoding="utf-8"
    ) == open_v14_1.render_readme(manifest)


def test_public_schema_uses_precise_parliamentary_semantics() -> None:
    tables = {row["table_name"]: row for row in _manifest()["tables"]}
    columns = {
        column["name"]
        for table in tables.values()
        for column in table["columns"]
    }

    assert "dim_parliamentary_author" not in tables
    assert "dim_parliamentary_source_author" in tables
    assert "author_id" not in columns
    assert "question_count" not in columns
    assert "response_rate_pct" not in columns
    assert {
        "published_question_count",
        "published_response_date_count",
        "published_response_date_rate_pct",
    } <= columns


def test_source_dependent_structures_are_deferred_not_empty() -> None:
    manifest = _manifest()
    tables = {row["table_name"] for row in manifest["tables"]}

    assert "analytical_parliamentary_group_exposure" not in tables
    assert "group_member_days" in manifest["deferred_source_dependent_work"]
    assert "response_text_and_lifecycle" in manifest["deferred_source_dependent_work"]
