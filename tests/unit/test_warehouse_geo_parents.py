from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from morocco_elections.warehouse.geo_parents import (
    _verify_manifest_sources,
    build_geo_parent_evidence,
    derive_comm2015_parent_relations,
    validate_geo_parent_relations,
)
from morocco_elections.warehouse.validation import validate_semantic_consistency


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/exports/open/v15/morocco_elections_v15.duckdb"


def _rows(connection: duckdb.DuckDBPyConnection, table: str) -> list[dict]:
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    fields = [item[0] for item in cursor.description]
    return [dict(zip(fields, values, strict=True)) for values in cursor.fetchall()]


@pytest.fixture(scope="module")
def evidence() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        relations, _ = build_geo_parent_evidence(connection, ROOT)
        return (
            relations,
            _rows(connection, "dim_geo"),
            _rows(connection, "dim_election"),
            _rows(connection, "dim_electoral_contest"),
            [
                row
                for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result")
                for row in _rows(connection, table)
            ],
        )
    finally:
        connection.close()


def test_parent_evidence_resolves_all_regional_mismatches_and_41_arrondissements(evidence) -> None:
    relations, geographies, elections, contests, facts = evidence
    assert len(relations) == 204
    council = [row for row in relations if row["relationship_type"] == "COUNCIL_PARENT"]
    assert len(council) == 41
    assert len({row["parent_geo_id"] for row in council}) == 6
    assert validate_geo_parent_relations(relations, geographies, elections) == []
    issues = validate_semantic_consistency(facts, contests, elections, geographies, relations)
    assert not [issue for issue in issues if issue.code == "REGIONAL_PARENT_MISMATCH"]


def test_parent_relation_mutations_fail_closed(evidence) -> None:
    relations, geographies, elections, _, _ = evidence
    council_index = next(index for index, row in enumerate(relations) if row["relationship_type"] == "COUNCIL_PARENT")
    direct_prefecture = copy.deepcopy(relations)
    direct_prefecture[council_index]["parent_geo_id"] = "MA-01-511"
    codes = {issue.code for issue in validate_geo_parent_relations(direct_prefecture, geographies, elections)}
    assert {"ARRONDISSEMENT_DIRECT_PREFECTURE_PARENT", "ARRONDISSEMENT_PARENT_NOT_COMMUNE"} <= codes

    duplicate = copy.deepcopy(relations)
    duplicate_row = {**duplicate[council_index], "relation_id": "DUPLICATE-RELATION"}
    duplicate.append(duplicate_row)
    assert "DUPLICATE_ACTIVE_GEO_PARENT" in {
        issue.code for issue in validate_geo_parent_relations(duplicate, geographies, elections)
    }

    invalid_date = copy.deepcopy(relations)
    invalid_date[council_index]["valid_from"] = "2016-01-01"
    assert "GEO_PARENT_NOT_APPLICABLE" in {
        issue.code for issue in validate_geo_parent_relations(invalid_date, geographies, elections)
    }


def test_comm2015_seed_rejects_deleted_or_invented_arrondissement(evidence) -> None:
    _, geographies, _, contests, _ = evidence
    seed = json.loads((ROOT / "metadata/warehouse/comm2015_geo_parents.seed.json").read_text(encoding="utf-8"))
    deleted = copy.deepcopy(seed)
    deleted["arrondissements"].pop()
    with pytest.raises(ValueError, match="six groups and 41 arrondissements"):
        derive_comm2015_parent_relations(ROOT, geographies, contests, deleted)
    invented = copy.deepcopy(seed)
    invented["arrondissements"][0]["official_child_code"] = "99.999.99.99."
    with pytest.raises(ValueError, match="invented or non-arrondissement official identifier"):
        derive_comm2015_parent_relations(ROOT, geographies, contests, invented)


def test_parent_source_hash_mutation_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"official bytes")
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "source_manifest.json").write_text(json.dumps({"sources": [{
        "source_id": "S", "local_path": "source.bin", "byte_size": source.stat().st_size,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }]}), encoding="utf-8")
    assert _verify_manifest_sources(tmp_path, {"S"})["S"]["source_id"] == "S"
    source.write_bytes(b"mutated bytes")
    with pytest.raises(ValueError, match="source bytes differ"):
        _verify_manifest_sources(tmp_path, {"S"})
