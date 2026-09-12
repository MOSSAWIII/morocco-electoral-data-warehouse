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
    assert len(manifest["tables"]) == 8
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
