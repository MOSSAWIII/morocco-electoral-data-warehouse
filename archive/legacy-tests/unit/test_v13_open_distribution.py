from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pytest

from morocco_elections.exports import open_v13


ROOT = Path(__file__).resolve().parents[2]


def test_rows_to_arrow_preserves_nulls_and_types() -> None:
    table = open_v13.rows_to_arrow(
        ["key", "count", "ratio", "empty"],
        [
            {"key": "A", "count": 1, "ratio": 1.5, "empty": None},
            {"key": "B", "count": None, "ratio": 2, "empty": None},
        ],
    )

    assert table.schema.field("key").type == pa.string()
    assert table.schema.field("count").type == pa.int64()
    assert table.schema.field("ratio").type == pa.float64()
    assert table.schema.field("empty").type == pa.string()
    assert table.column("count").to_pylist() == [1, None]


def test_primary_key_rejects_duplicates_and_nulls() -> None:
    with pytest.raises(RuntimeError, match="dupliqu"):
        open_v13._validate_primary_key("sample", [{"id": "A"}, {"id": "A"}], ["id"])
    with pytest.raises(RuntimeError, match="vide"):
        open_v13._validate_primary_key("sample", [{"id": None}], ["id"])


def test_tracked_open_distribution_contract() -> None:
    manifest = json.loads((ROOT / "metadata/v13_open_distribution.json").read_text(encoding="utf-8"))

    assert open_v13.validate_manifest(manifest) == []
    assert len(manifest["tables"]) == 16
    assert len(manifest["relationships"]) == len(open_v13.RELATIONSHIPS)
    assert manifest["publication_status"] == "PUBLIC_BETA"
    assert {"LICENSE_DATA.md", "queries.sql"} <= {item["path"] for item in manifest["files"]}
    assert (ROOT / "docs/publication/V13_OPEN_DATA_README.txt").read_text(
        encoding="utf-8"
    ) == open_v13.render_readme(manifest)


def test_public_beta_has_three_reference_queries_and_explicit_licenses() -> None:
    queries = (ROOT / "examples/v13_reference_queries.sql").read_text(encoding="utf-8")
    assert queries.count(";") == 3
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    assert "ODbL 1.0" in (ROOT / "LICENSES/DATA.md").read_text(encoding="utf-8")
    assert "CC BY 4.0" in (ROOT / "LICENSES/DOCUMENTATION.md").read_text(encoding="utf-8")


def test_public_tables_keep_distinct_grains_and_exclude_names() -> None:
    manifest = json.loads((ROOT / "metadata/v13_open_distribution.json").read_text(encoding="utf-8"))
    tables = {table["table_name"]: table for table in manifest["tables"]}
    assert tables["fact_communal_election_result"]["primary_key"] == [
        "contest_id", "party_id"
    ]
    assert tables["fact_commune_election_summary"]["primary_key"] == ["contest_id"]
    result_columns = {column["name"] for column in tables["fact_communal_election_result"]["columns"]}
    summary_columns = {column["name"] for column in tables["fact_commune_election_summary"]["columns"]}
    observation_columns = {column["name"] for column in tables["fact_observation"]["columns"]}
    assert {"votes", "vote_share", "winner_flag"} <= result_columns
    assert "party_votes" not in result_columns
    assert {"turnout_rate", "winner_party_id", "victory_margin_pp"} <= summary_columns
    assert "indicator_id" in observation_columns and "metric_id" not in observation_columns
    for table_name in ("dim_person_public", "fact_parliamentary_mandate", "fact_parliamentary_activity"):
        columns = {column["name"] for column in tables[table_name]["columns"]}
        assert not {"full_name", "full_name_ar", "deputy_name_ar_raw", "question_text_ar"} & columns


def test_indicator_dimension_makes_observed_identifiers_explicit() -> None:
    headers = [
        "metric_id", "domain", "metric_name", "definition", "data_type", "unit",
        "primary_fact_sheet", "required_keys", "candidate_sources", "collection_status",
        "quality_rule", "notes",
    ]
    completed = open_v13._complete_indicator_dimension(
        headers,
        [{"metric_id": "documented"}],
        [
            {"metric_id": "documented", "value_numeric": 1},
            {"metric_id": "missing", "value_numeric": 2, "unit": "count", "source_id": "SRC"},
        ],
    )
    assert len(completed) == 2
    assert completed[1]["metric_id"] == "missing"
    assert completed[1]["collection_status"] == "OBSERVED_UNDOCUMENTED"
    assert completed[1]["definition"] is None


def test_foreign_key_validation_rejects_dangling_value() -> None:
    tables = {name: [] for name in open_v13.TABLES}
    for child, child_column, parent, parent_column, _ in open_v13.RELATIONSHIPS:
        tables[parent] = [{parent_column: "PARENT"}]
        tables[child] = [{child_column: "MISSING"}]
        with pytest.raises(RuntimeError, match="absente"):
            open_v13._validate_foreign_keys(tables)
        break
