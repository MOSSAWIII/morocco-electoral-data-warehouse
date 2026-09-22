from __future__ import annotations

from typing import Any

import duckdb

from morocco_elections.warehouse.contracts import ALL_TABLE_CONTRACTS, FIELD_VOCABULARIES, TABLE_CONTRACTS, VOCABULARIES


OPTIONAL_FIELDS: dict[str, tuple[str, ...]] = {
    "fact_result_revision": ("published_at", "valid_to", "supersedes_revision_id", "decision_id", "official_value", "notes"),
    "fact_result_reconciliation": (
        "official_value", "recomputed_value", "difference", "explanation", "not_computable_reason",
        "official_source_id", "external_universe_id", "evidence_id", "calculation_method", "missing_components",
    ),
    "fact_legal_decision": ("affected_revision_id", "notes"),
    "dim_legal_regime": ("valid_to", "threshold", "district_magnitude_rule", "supporting_source_ids", "notes"),
    "bridge_election_legal_regime": ("valid_to",),
    "bridge_contest_legal_regime": ("classification_basis", "classification_source_id", "classification_value", "classification_rule"),
    "bridge_geo_official_identifier": ("geo_type",),
    "fact_seat_allocation": ("difference", "difference_explanation", "candidate_id"),
    "dim_party_version": ("valid_to", "acronym", "legal_status"),
    "bridge_party_lineage": ("notes",),
    "bridge_person_party_affiliation": ("valid_to", "evidence_id"),
    "dim_geo_version": ("valid_to", "parent_geo_version_id", "geometry_reference", "geometry_path"),
    "bridge_geo_lineage": ("notes",),
    "bridge_geo_parent": ("valid_to", "official_child_code", "supporting_source_ids", "notes"),
    "publication_file": ("fact_status", "source_url", "notes"),
    "publication_review": ("legal_basis", "evidence_url", "review_method", "proof_sha256", "claim_class", "notes"),
}


INTEGER_FIELDS = {"denominator", "position", "official_seats", "recomputed_seats", "population", "classification_value", "byte_size", "acquired", "expected", "covered", "missing", "non_comparable", "redistribution_forbidden"}
DOUBLE_FIELDS = {"official_value", "recomputed_value", "difference", "tolerance", "threshold", "confidence"}
BOOLEAN_FIELDS = {"is_external", "privacy_review_required"}
DATE_FIELDS = {"acquired_at", "valid_from", "valid_to", "published_at", "known_at", "decision_date", "effective_date", "census_date", "reviewed_at"}


def sql_type(field: str) -> str:
    if field in INTEGER_FIELDS:
        return "BIGINT"
    if field in DOUBLE_FIELDS:
        return "DOUBLE"
    if field in BOOLEAN_FIELDS:
        return "BOOLEAN"
    if field in DATE_FIELDS:
        return "DATE"
    return "VARCHAR"


def ddl(table: str) -> str:
    contract = ALL_TABLE_CONTRACTS[table]
    required = list(contract["required"])
    fields = required + [field for field in OPTIONAL_FIELDS.get(table, ()) if field not in required]
    definitions = []
    for field in fields:
        definition = f'"{field}" {sql_type(field)}' + (" NOT NULL" if field in required else "")
        vocabulary_name = FIELD_VOCABULARIES.get(field)
        if vocabulary_name:
            values = ", ".join("'" + value.replace("'", "''") + "'" for value in sorted(VOCABULARIES[vocabulary_name].values))
            definition += f' CHECK ("{field}" IN ({values}))'
        if field in INTEGER_FIELDS or field in {"confidence", "tolerance"}:
            definition += f' CHECK ("{field}" >= 0)'
        if field == "confidence":
            definition += ' CHECK ("confidence" <= 1)'
        definitions.append(definition)
    primary_key = ", ".join(f'"{field}"' for field in contract["primary_key"])
    definitions.append(f"PRIMARY KEY ({primary_key})")
    return f'CREATE TABLE "{table}" (\n  ' + ",\n  ".join(definitions) + "\n)"


def create_schema(connection: duckdb.DuckDBPyConnection) -> None:
    for table in TABLE_CONTRACTS:
        connection.execute(ddl(table))


def schema_inventory(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return [
        {"table_name": row[0], "row_count": connection.execute(f'SELECT count(*) FROM "{row[0]}"').fetchone()[0]}
        for row in connection.execute("SHOW TABLES").fetchall()
    ]
