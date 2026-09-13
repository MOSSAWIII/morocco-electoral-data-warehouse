from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from morocco_elections.quality.v15.accuracy import planned_observation_violations
from morocco_elections.quality.v15.relationships import validate_relationships
from morocco_elections.v15.pipeline import _ddl
from morocco_elections.v15.schema import all_table_contracts


def _contract(name: str, mutation_name: str) -> dict:
    value = dict(next(row for row in all_table_contracts() if row["table_name"] == name))
    value["table_name"] = mutation_name
    return value


def test_production_ddl_rejects_result_duplicate() -> None:
    connection = duckdb.connect()
    contract = _contract("dim_geo", "mutation_dim_geo")
    connection.execute(_ddl(contract))
    connection.execute("INSERT INTO mutation_dim_geo(geo_id, geo_name, geo_type, quality_status) VALUES ('G1','A','COMMUNE','OK')")
    with pytest.raises(duckdb.ConstraintException):
        connection.execute("INSERT INTO mutation_dim_geo(geo_id, geo_name, geo_type, quality_status) VALUES ('G1','B','COMMUNE','OK')")


def test_production_relationship_validator_detects_orphan_party(tmp_path: Path) -> None:
    database = tmp_path / "morocco_elections_v15.duckdb"
    connection = duckdb.connect(str(database))
    connection.execute("CREATE TABLE dim_party(party_id VARCHAR PRIMARY KEY)")
    connection.execute("CREATE TABLE result(result_id VARCHAR PRIMARY KEY, party_id VARCHAR)")
    connection.execute("INSERT INTO result VALUES ('R1', 'MISSING')")
    connection.close()
    tables = [
        {"table_name": "dim_party", "natural_key": ["party_id"], "columns": [{"name": "party_id", "nullable": False}]},
        {"table_name": "result", "natural_key": ["result_id"], "columns": [{"name": "result_id", "nullable": False}, {"name": "party_id", "nullable": True}]},
    ]
    manifest = {
        "tables": tables,
        "relationships": [{"child_table": "result", "child_column": "party_id", "parent_table": "dim_party", "parent_column": "party_id"}],
    }
    assert any("orphelin" in error for error in validate_relationships(tmp_path, manifest))


def test_production_ddl_rejects_inverted_mandate_interval() -> None:
    connection = duckdb.connect()
    contract = _contract("dim_geo", "mutation_period")
    connection.execute(_ddl(contract))
    with pytest.raises(duckdb.ConstraintException):
        connection.execute(
            "INSERT INTO mutation_period(geo_id,geo_name,geo_type,valid_from,valid_to,quality_status) "
            "VALUES ('G1','A','COMMUNE',DATE '2021-01-02',DATE '2021-01-01','OK')"
        )


def test_production_ddl_rejects_out_of_range_rate() -> None:
    connection = duckdb.connect()
    contract = _contract("fact_electoral_mobilization", "mutation_mobilization")
    connection.execute(_ddl(contract))
    with pytest.raises(duckdb.ConstraintException):
        connection.execute(
            "INSERT INTO mutation_mobilization"
            "(contest_id,election_id,geo_id,turnout_rate,source_id,source_row,quality_status) "
            "VALUES ('C1','E1','G1',1.01,'S1',1,'OK')"
        )


def test_production_accuracy_check_detects_planned_observation() -> None:
    connection = duckdb.connect()
    connection.execute("CREATE TABLE dim_indicator(indicator_id VARCHAR, collection_status VARCHAR)")
    connection.execute("CREATE TABLE fact_observation(observation_id VARCHAR, indicator_id VARCHAR)")
    connection.execute("INSERT INTO dim_indicator VALUES ('I1', 'not_started')")
    connection.execute("INSERT INTO fact_observation VALUES ('O1', 'I1')")
    assert planned_observation_violations(connection) == 1
