from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.v16.contracts import TABLE_CONTRACTS
from morocco_elections.v16.demography import load_hcp_rgph2014_individuals
from morocco_elections.v16.evidence import (
    derive_contest_legal_regime_links,
    load_json,
    validate_legal_regime_seed,
    validate_official_source_registry,
)
from morocco_elections.v16.geo_parents import build_geo_parent_evidence, geo_parent_report
from morocco_elections.v16.reconciliation import derive_reconciliation_matrix
from morocco_elections.v16.result_history import build_result_history_diagnostic
from morocco_elections.v16.schema import create_schema


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _insert_rows(connection: duckdb.DuckDBPyConnection, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = [row[0] for row in connection.execute(f"DESCRIBE {_quoted(table)}").fetchall()]
    selected = [column for column in columns if any(column in row for row in rows)]
    placeholders = ", ".join("?" for _ in selected)
    quoted_columns = ", ".join(_quoted(column) for column in selected)
    values = []
    for row in rows:
        values.append(
            [json.dumps(row.get(column), ensure_ascii=False) if isinstance(row.get(column), (list, dict)) else row.get(column) for column in selected]
        )
    connection.executemany(
        f"INSERT INTO {_quoted(table)} ({quoted_columns}) VALUES ({placeholders})",
        values,
    )


def build_development_database(
    seed_database: Path,
    output_database: Path,
    *,
    legal_seed_path: Path | None = None,
    source_registry_path: Path | None = None,
    evidence_root: Path | None = None,
    replace_existing: bool = False,
    as_of_date: str = "2026-09-21",
) -> dict[str, Any]:
    """Create an additive, non-publication-ready V16 database without changing V15."""
    seed_database = seed_database.resolve()
    output_database = output_database.resolve()
    if not seed_database.is_file():
        raise FileNotFoundError(seed_database)
    if output_database.exists() and not replace_existing:
        raise FileExistsError(f"refusing to overwrite existing V16 database: {output_database}")
    legal_payload: dict[str, Any] | None = None
    population_rows: list[dict[str, Any]] = []
    population_source: dict[str, Any] | None = None
    geo_parent_rows: list[dict[str, Any]] = []
    geo_parent_details: dict[str, Any] = {}
    parent_report: dict[str, Any] = {}
    reconciliation_rows: list[dict[str, Any]] = []
    reconciliation_report: dict[str, Any] = {}
    result_history_report: dict[str, Any] = {}
    if legal_seed_path is not None or source_registry_path is not None:
        if legal_seed_path is None or source_registry_path is None or evidence_root is None:
            raise ValueError("legal_seed_path, source_registry_path and evidence_root must be supplied together")
        legal_payload = load_json(legal_seed_path)
        source_registry = load_json(source_registry_path)
        evidence_issues = validate_official_source_registry(evidence_root, source_registry)
        evidence_issues += validate_legal_regime_seed(legal_payload, source_registry)
        if evidence_issues:
            codes = ", ".join(sorted({issue.code for issue in evidence_issues}))
            raise RuntimeError(f"refusing to seed unverified legal evidence: {codes}")
        population_source_id = legal_payload["population_link_rules"][0]["population_source_id"]
        population_source = next(row for row in source_registry["sources"] if row["source_id"] == population_source_id)
    output_database.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v16-build-", dir=output_database.parent) as temporary_name:
        temporary = Path(temporary_name) / output_database.name
        contest_count = 0
        crosswalks: list[dict[str, Any]] = []
        connection = duckdb.connect(str(temporary))
        try:
            seed_sql = str(seed_database).replace("'", "''")
            connection.execute(f"ATTACH '{seed_sql}' AS v15_seed (READ_ONLY)")
            source_tables = [
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_catalog='v15_seed' AND table_type='BASE TABLE' ORDER BY table_name"
                ).fetchall()
            ]
            collisions = set(source_tables) & TABLE_CONTRACTS.keys()
            if collisions:
                raise RuntimeError("V15/V16 table collision: " + ", ".join(sorted(collisions)))
            for table in source_tables:
                quoted = _quoted(table)
                connection.execute(f"CREATE TABLE main.{quoted} AS SELECT * FROM v15_seed.{quoted}")
            connection.execute("DETACH v15_seed")
            create_schema(connection)
            if "warehouse_metadata" not in source_tables:
                connection.execute(
                    "CREATE TABLE warehouse_metadata (release VARCHAR, schema_version BIGINT, source_release VARCHAR)"
                )
                connection.execute("INSERT INTO warehouse_metadata VALUES ('V16', 16, 'V15')")
            metadata_columns = {
                row[0] for row in connection.execute("DESCRIBE warehouse_metadata").fetchall()
            }
            if "as_of_date" not in metadata_columns:
                connection.execute("ALTER TABLE warehouse_metadata ADD COLUMN as_of_date DATE")
            connection.execute(
                "UPDATE warehouse_metadata SET release = 'V16', schema_version = 16, "
                "source_release = 'V15', as_of_date = ?",
                [as_of_date],
            )
            if evidence_root is not None:
                geo_parent_rows, geo_parent_details = build_geo_parent_evidence(connection, evidence_root)
                _insert_rows(connection, "bridge_geo_parent", geo_parent_rows)
                parent_report = geo_parent_report(connection, geo_parent_rows)
                reconciliation_rows, reconciliation_report = derive_reconciliation_matrix(connection, evidence_root)
                _insert_rows(connection, "fact_result_reconciliation", reconciliation_rows)
            contest_links: list[dict[str, Any]] = []
            if legal_payload is not None:
                _insert_rows(connection, "dim_legal_regime", list(legal_payload["legal_regimes"]))
                _insert_rows(connection, "bridge_election_legal_regime", list(legal_payload["election_links"]))
                if "dim_electoral_contest" in source_tables:
                    columns = {row[0] for row in connection.execute("DESCRIBE dim_electoral_contest").fetchall()}
                    if {"contest_id", "election_id", "list_type"} <= columns:
                        contests = [
                            {"contest_id": row[0], "election_id": row[1], "source_list_type": row[2], "geo_id": row[3]}
                            for row in connection.execute(
                                "SELECT contest_id, election_id, list_type, geo_id FROM dim_electoral_contest"
                            ).fetchall()
                        ]
                        contest_count = len(contests)
                        geographies = [
                            {"geo_id": row[0], "geo_type": row[1], "geo_name": row[2], "parent_geo_id": row[3]}
                            for row in connection.execute(
                                "SELECT geo_id, geo_type, geo_name, parent_geo_id FROM dim_geo"
                            ).fetchall()
                        ]
                        assert population_source is not None and evidence_root is not None
                        population_rows, crosswalks = load_hcp_rgph2014_individuals(
                            evidence_root / population_source["raw_path"],
                            geographies,
                            source_id=population_source["source_id"],
                            source_url=population_source["source_url"],
                        )
                        _insert_rows(connection, "fact_geo_population", population_rows)
                        trusted_ids = {row["geo_id"] for row in crosswalks if row["confidence"] == 1.0}
                        populations_by_geo = {
                            row["normalized_geo_id"]: row for row in population_rows if row["normalized_geo_id"] in trusted_ids
                        }
                        geography_types = {row["geo_id"]: row["geo_type"] for row in geographies}
                        contest_links = derive_contest_legal_regime_links(
                            contests,
                            legal_payload,
                            populations_by_geo=populations_by_geo,
                            geography_types=geography_types,
                        )
                        _insert_rows(connection, "bridge_geo_official_identifier", crosswalks)
                        _insert_rows(connection, "bridge_contest_legal_regime", contest_links)
            if evidence_root is not None:
                result_history_report = build_result_history_diagnostic(
                    connection, evidence_root, as_of_date,
                )
            connection.execute("CHECKPOINT")
        finally:
            connection.close()
        os.replace(temporary, output_database)
    return {
        "source_database": str(seed_database),
        "output_database": str(output_database),
        "copied_v15_tables": len(source_tables),
        "created_v16_tables": len(TABLE_CONTRACTS),
        "seeded_legal_regimes": len(legal_payload["legal_regimes"]) if legal_payload is not None else 0,
        "seeded_election_legal_links": len(legal_payload["election_links"]) if legal_payload is not None else 0,
        "seeded_contest_legal_links": len(contest_links),
        "seeded_geo_populations": len(population_rows),
        "seeded_geo_crosswalks": len(crosswalks),
        "seeded_geo_parent_relations": len(geo_parent_rows),
        "geo_parent_evidence": geo_parent_details,
        "geo_parent_report": parent_report,
        "seeded_result_reconciliations": len(reconciliation_rows),
        "reconciliation_report": reconciliation_report,
        "result_history_report": result_history_report,
        "as_of_date": as_of_date,
        "unmapped_contests": contest_count - len(contest_links),
        "publication_status": "NOT_PUBLICATION_READY",
    }
