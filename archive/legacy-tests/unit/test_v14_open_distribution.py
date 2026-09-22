from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from morocco_elections.exports import open_v14


ROOT = Path(__file__).resolve().parents[2]


def _manifest() -> dict:
    return json.loads(
        (ROOT / "metadata/v14_open_distribution.json").read_text(encoding="utf-8")
    )


def test_tracked_v14_distribution_contract() -> None:
    manifest = _manifest()

    assert open_v14.validate_manifest(manifest) == []
    assert len(manifest["tables"]) == 26
    assert sum(table["rows"] for table in manifest["tables"]) == 341_504
    assert len(manifest["relationships"]) == 43
    assert len(manifest["files"]) == 58
    assert len(manifest["source_payloads"]) == 59
    assert (ROOT / "docs/publication/V14_OPEN_DATA_README.txt").read_text(
        encoding="utf-8"
    ) == open_v14.render_readme(manifest)


def test_v14_parliament_scope_and_deduplication_are_explicit() -> None:
    manifest = _manifest()
    controls = manifest["controls"]

    assert controls == open_v14.EXPECTED_CONTROLS
    assert controls["source_occurrences"] - controls["duplicate_occurrences"] == controls[
        "canonical_questions"
    ]
    assert controls["written_questions"] + controls["oral_questions"] == controls[
        "canonical_questions"
    ]
    assert controls["identity_linked_questions"] + controls[
        "identity_unresolved_questions"
    ] == controls["canonical_questions"]
    assert controls["identity_ambiguous_questions"] == 0


def test_v14_replaces_partial_activity_and_exposes_trajectories_without_names() -> None:
    tables = {table["table_name"]: table for table in _manifest()["tables"]}

    assert "fact_parliamentary_activity" not in tables
    assert tables["fact_parliamentary_question"]["rows"] == 65_748
    assert tables["fact_parliamentary_response"]["rows"] == 30_257
    assert tables["analytical_parliamentary_trajectory"]["rows"] == 3_142
    assert tables["analytical_parliamentary_trajectory"]["primary_key"] == ["trajectory_id"]
    author_columns = {
        column["name"] for column in tables["dim_parliamentary_author"]["columns"]
    }
    assert author_columns == {
        "author_id", "legislature", "person_id", "identity_match_method",
    }
    assert not {"author_name_ar_raw", "author_source_key", "person_name_match_key"} & author_columns


def test_v14_has_three_reference_queries() -> None:
    queries = (ROOT / "examples/v14_reference_queries.sql").read_text(encoding="utf-8")
    assert queries.count(";") == 3
    assert {"LICENSE_DATA.md", "ATTRIBUTIONS.md", "CITATION.cff"} <= {
        item["path"] for item in _manifest()["files"]
    }


def test_v13_question_is_normalized_without_losing_provenance(
    tmp_path: Path, monkeypatch,
) -> None:
    sources = []
    descriptions = []
    for index, source_id in enumerate(open_v14.V13_SOURCE_FAMILIES, 1):
        sources.append(
            {
                "source_id": source_id,
                "source_url": f"https://example.test/{index}",
                "producer": "Producteur synthétique",
                "license": "ODbL",
                "sha256": f"{index:x}" * 64,
                "byte_size": index,
            }
        )
        descriptions.append(
            {
                "source_id": source_id,
                "source_name": f"Source synthétique {index}",
                "last_checked": "2026-09-12",
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": sources}), encoding="utf-8")
    monkeypatch.setattr(open_v14, "SOURCE_MANIFEST", manifest)
    source_id = next(iter(open_v14.V13_SOURCE_FAMILIES))

    occurrences, normalized_sources = open_v14._load_v13_question_occurrences(
        [
            {
                "source_id": source_id,
                "question_type": "written",
                "source_question_number": 42,
                "deposit_date": date(2024, 1, 2),
                "response_date": None,
                "source_row": 7,
            }
        ],
        descriptions,
    )

    assert len(normalized_sources) == 4
    assert occurrences[0]["source_question_number"] == "42"
    assert occurrences[0]["deposit_date"] == "2024-01-02"
    assert occurrences[0]["source_row"] == 7
    assert occurrences[0]["source_sha256"] == sources[0]["sha256"]
