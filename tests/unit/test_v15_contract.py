from __future__ import annotations

import json
import os
from pathlib import Path

from morocco_elections.v15 import pipeline
from morocco_elections.v15.pipeline import _ddl, _readme
from morocco_elections.v15.queries import ANALYSES, available_cubes, render_reference_queries
from morocco_elections.v15.schema import CORRECTIONS, TABLE_SPECS, all_table_contracts
from morocco_elections.provenance import sha256_file


ROOT = Path(__file__).resolve().parents[2]


def test_contract_is_autonomous_and_complete() -> None:
    assert len(TABLE_SPECS) == 31
    for table in all_table_contracts():
        assert table["primary_key"] and table["natural_key"] and table["grain"]
        assert table["columns"]
        for column in table["columns"]:
            assert {"name", "source_column", "type", "nullable", "role", "unit", "domain", "checks"} <= column.keys()


def test_ddl_is_derived_from_contract_domains_and_relationships() -> None:
    statements = "\n".join(_ddl(table) for table in all_table_contracts())
    assert "PRIMARY KEY" in statements
    assert "FOREIGN KEY" in statements
    assert "NOT NULL" in statements
    assert " BETWEEN 0 AND 1" in statements
    assert " IN (" in statements


def test_cubes_and_analyses_have_complete_contracts_and_one_registry() -> None:
    assert len(available_cubes()) == 5
    for cube in available_cubes():
        assert cube["grain"] and cube["dimensions"] and cube["measures"] and cube["reconciliation_sql"]
        assert all({"name", "unit", "formula", "denominator"} <= measure.keys() for measure in cube["measures"])
    assert len(ANALYSES) == 5
    assert all({"tables", "filters", "units", "coverage_id", "limitations", "sql"} <= row.keys() for row in ANALYSES)
    assert (ROOT / "examples/v15_reference_queries.sql").read_text(encoding="utf-8") == render_reference_queries()


def test_corrections_are_declarative_and_evidenced() -> None:
    assert {row["correction_id"] for row in CORRECTIONS} == {
        "V15_MANDATE_INTERVAL_001", "V15_AFFILIATION_INTERVAL_001"
    }
    required = {"table_name", "column", "record_key", "source_value", "published_value", "rule", "evidence_id", "source_id", "proof"}
    assert all(required <= row.keys() for row in CORRECTIONS)


def test_publication_metadata_pins_asset_integrity() -> None:
    publication = json.loads((ROOT / "metadata/v15_publication.json").read_text(encoding="utf-8"))
    assert publication["bytes"] > 100_000_000
    assert len(publication["sha256"]) == 64


def test_failed_build_swap_restores_last_valid_package(monkeypatch, tmp_path: Path) -> None:
    destination = tmp_path / "v15"
    staging = tmp_path / "staging"
    destination.mkdir()
    staging.mkdir()
    (destination / "marker").write_text("valid", encoding="utf-8")
    real_replace = os.replace

    def fail_new_package(source, target):
        if Path(source) == staging:
            raise OSError("simulated swap failure")
        return real_replace(source, target)

    monkeypatch.setattr(pipeline.os, "replace", fail_new_package)
    try:
        pipeline._replace_package(staging, destination, tmp_path)
    except OSError:
        pass
    else:
        raise AssertionError("swap failure expected")
    assert (destination / "marker").read_text(encoding="utf-8") == "valid"


def test_generated_readme_contains_executable_commands() -> None:
    manifest = {"tables": all_table_contracts()}
    text = _readme(manifest)
    assert "duckdb morocco_elections_v15.duckdb" in text
    assert "python -m morocco_elections analyze reference" in text
    assert "python -m morocco_elections validate --mode public" in text
    assert "INSTALL duckdb" not in text


def test_source_column_drift_fails_before_data_is_read(monkeypatch, tmp_path: Path) -> None:
    tables = []
    for spec in TABLE_SPECS:
        columns = [
            {"name": column["source_column"]} for column in spec.columns
            if not column.get("derived") and column.get("source_column")
        ]
        tables.append({"table_name": spec.source_name, "rows": spec.expected_rows, "columns": columns})
        parquet = tmp_path / "parquet" / f"{spec.source_name}.parquet"
        parquet.parent.mkdir(exist_ok=True)
        parquet.touch()
    tables[0]["columns"][0]["name"] = "drifted_column"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"release": "V14.1", "tables": tables}), encoding="utf-8")
    (tmp_path / "checksums.sha256").write_text("", encoding="ascii")
    monkeypatch.setitem(pipeline.SOURCE_DISTRIBUTION, "manifest_sha256", sha256_file(manifest))
    try:
        pipeline._load_seed(tmp_path)
    except RuntimeError as exc:
        assert "Dérive de colonnes" in str(exc)
    else:
        raise AssertionError("source schema drift should fail")
