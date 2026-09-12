from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import openpyxl
import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.legacy.v9.build import rows_from_sheet
from morocco_elections.provenance import sha256_file


VERSION = "V13"
GENERATED_ON = "2026-09-11"
DEFAULT_OUTPUT = get_paths().data_root / "exports" / "open" / "v13"
DEFAULT_MANIFEST = PROJECT_ROOT / "metadata" / "v13_open_distribution.json"
DEFAULT_README = PROJECT_ROOT / "docs" / "publication" / "V13_OPEN_DATA_README.txt"
RELEASE_REPORT = PROJECT_ROOT / "metadata" / "v13_release_report.json"
DATA_LICENSE = PROJECT_ROOT / "LICENSES" / "DATA.md"
REFERENCE_QUERIES = PROJECT_ROOT / "examples" / "v13_reference_queries.sql"

TABLES = {
    "dim_geo": {"sheet": "DIM_GEO", "key": ["geo_id"]},
    "dim_party": {"sheet": "DIM_PARTY", "key": ["party_id"]},
    "dim_time": {"sheet": "DIM_TIME", "key": ["time_id"]},
    "dim_election": {"sheet": "DIM_ELECTION", "key": ["election_id"]},
    "dim_electoral_contest": {"sheet": "DIM_ELECTORAL_CONTEST", "key": ["contest_id"]},
    "dim_person_public": {
        "sheet": "DIM_PERSON",
        "key": ["person_id"],
        "columns": [
            "person_id", "gender", "birth_year", "party_id", "role", "incumbent_flag",
            "first_elected_year", "mandates_count", "valid_from", "valid_to", "source_id",
            "quality_status", "notes",
        ],
    },
    "fact_election_result": {"sheet": "FACT_ELECTION_RESULT", "key": ["result_id"]},
    "fact_electoral_mobilization": {
        "sheet": "FACT_ELECTORAL_MOBILIZATION",
        "key": ["contest_id"],
    },
    "fact_communal_election_result": {
        "sheet": "ANALYTICAL_PANEL",
        "key": ["contest_id", "party_id"],
        "columns": [
            "contest_id", "geo_id", "election_id", "year", "party_id", "party_votes", "vote_share",
            "rank", "winner", "seats", "seat_share", "previous_vote_share", "swing_pp",
            "vote_change", "seat_change", "source_id", "fact_status", "quality_status", "notes",
        ],
        "rename": {"party_votes": "votes", "winner": "winner_flag"},
    },
    "fact_commune_election_summary": {
        "sheet": "COMMUNE_ELECTION_PANEL",
        "key": ["contest_id"],
        "rename": {
            "turnout": "turnout_rate",
            "winner": "winner_party_id",
            "winning_share": "winning_vote_share",
            "runner_up": "runner_up_party_id",
            "margin_votes": "victory_margin_votes",
            "margin_pp": "victory_margin_pp",
            "largest_party": "largest_party_id",
            "president_party": "president_party_id",
        },
    },
    "fact_observation": {
        "sheet": "FACT_OBSERVATION",
        "key": ["observation_id"],
        "rename": {"metric_id": "indicator_id"},
    },
    "fact_parliamentary_mandate": {
        "sheet": "PARLIAMENTARY_MANDATES",
        "key": ["mandate_id"],
        "columns": [
            "mandate_id", "person_id", "gender", "legislature", "source_seat_id",
            "source_constituency_id", "constituency", "region", "province", "party_id",
            "parliamentary_group", "start_date", "end_date", "entry_reason", "exit_reason",
            "replacement_procedure", "active_at_source_date", "source_id", "quality_status", "notes",
        ],
    },
    "fact_parliamentary_activity": {
        "sheet": "PARLIAMENTARY_QUESTIONS",
        "key": ["question_id"],
        "columns": [
            "question_id", "source_question_number", "question_type", "legislature", "period_raw",
            "deposit_date", "person_id", "party_id", "ministry_ar_raw", "response_date",
            "response_status", "source_id", "source_url", "source_row", "identity_match_method",
            "quality_status", "notes",
        ],
    },
    "sources": {"sheet": "SOURCES", "key": ["source_id"]},
    "dim_indicator": {
        "sheet": "DATA_DICTIONARY",
        "key": ["indicator_id"],
        "rename": {"metric_id": "indicator_id"},
    },
    "data_dictionary": {"sheet": "DATA_DICTIONARY", "key": ["metric_id"]},
}
ROW_FILTERS = {
    "dim_person_public": lambda row: str(row.get("person_id", "")).startswith("TAFRA_MP_"),
}
EXPECTED_ROWS = {
    "dim_geo": 1_825,
    "dim_party": 57,
    "dim_time": 17,
    "dim_election": 9,
    "dim_electoral_contest": 3_715,
    "dim_person_public": 1_185,
    "fact_election_result": 10_883,
    "fact_electoral_mobilization": 639,
    "fact_communal_election_result": 22_054,
    "fact_commune_election_summary": 3_076,
    "fact_observation": 3_203,
    "fact_parliamentary_mandate": 1_654,
    "fact_parliamentary_activity": 5_589,
    "sources": 61,
    "dim_indicator": 335,
    "data_dictionary": 292,
}
RELATIONSHIPS = [
    ("dim_electoral_contest", "geo_id", "dim_geo", "geo_id", False),
    ("dim_electoral_contest", "election_id", "dim_election", "election_id", False),
    ("fact_election_result", "contest_id", "dim_electoral_contest", "contest_id", False),
    ("fact_election_result", "geo_id", "dim_geo", "geo_id", False),
    ("fact_election_result", "party_id", "dim_party", "party_id", False),
    ("fact_election_result", "source_id", "sources", "source_id", False),
    ("fact_electoral_mobilization", "contest_id", "dim_electoral_contest", "contest_id", False),
    ("fact_electoral_mobilization", "source_id", "sources", "source_id", False),
    ("fact_communal_election_result", "contest_id", "dim_electoral_contest", "contest_id", False),
    ("fact_communal_election_result", "geo_id", "dim_geo", "geo_id", False),
    ("fact_communal_election_result", "election_id", "dim_election", "election_id", False),
    ("fact_communal_election_result", "party_id", "dim_party", "party_id", False),
    ("fact_communal_election_result", "source_id", "sources", "source_id", False),
    ("fact_commune_election_summary", "geo_id", "dim_geo", "geo_id", False),
    ("fact_commune_election_summary", "contest_id", "dim_electoral_contest", "contest_id", False),
    ("fact_commune_election_summary", "election_id", "dim_election", "election_id", False),
    ("fact_commune_election_summary", "winner_party_id", "dim_party", "party_id", True),
    ("fact_commune_election_summary", "runner_up_party_id", "dim_party", "party_id", True),
    ("fact_commune_election_summary", "largest_party_id", "dim_party", "party_id", True),
    ("fact_commune_election_summary", "president_party_id", "dim_party", "party_id", True),
    ("fact_commune_election_summary", "source_id", "sources", "source_id", False),
    ("fact_observation", "indicator_id", "dim_indicator", "indicator_id", False),
    ("fact_observation", "geo_id", "dim_geo", "geo_id", True),
    ("fact_observation", "time_id", "dim_time", "time_id", False),
    ("fact_observation", "election_id", "dim_election", "election_id", True),
    ("fact_observation", "source_id", "sources", "source_id", False),
    ("fact_parliamentary_mandate", "person_id", "dim_person_public", "person_id", False),
    ("fact_parliamentary_mandate", "party_id", "dim_party", "party_id", True),
    ("fact_parliamentary_mandate", "source_id", "sources", "source_id", False),
    ("fact_parliamentary_activity", "person_id", "dim_person_public", "person_id", True),
    ("fact_parliamentary_activity", "party_id", "dim_party", "party_id", True),
    ("fact_parliamentary_activity", "source_id", "sources", "source_id", False),
]


def _normalize(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _arrow_array(values: list[object]) -> pa.Array:
    normalized = [_normalize(value) for value in values]
    present = [value for value in normalized if value is not None]
    if not present:
        return pa.array(normalized, type=pa.string())
    if all(isinstance(value, bool) for value in present):
        return pa.array(normalized, type=pa.bool_())
    if all(isinstance(value, int) and not isinstance(value, bool) for value in present):
        return pa.array(normalized, type=pa.int64())
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in present):
        return pa.array(normalized, type=pa.float64())
    return pa.array([None if value is None else str(value) for value in normalized], type=pa.string())


def rows_to_arrow(headers: list[str], rows: list[dict[str, Any]]) -> pa.Table:
    arrays = [_arrow_array([row.get(header) for row in rows]) for header in headers]
    return pa.Table.from_arrays(arrays, names=headers)


def _validate_primary_key(table_name: str, rows: list[dict[str, Any]], key: list[str]) -> None:
    values = [tuple(row.get(column) for column in key) for row in rows]
    if any(any(value in (None, "") for value in item) for item in values):
        raise RuntimeError(f"{table_name}: clé primaire vide")
    if len(values) != len(set(values)):
        raise RuntimeError(f"{table_name}: clé primaire dupliquée")


def _validate_foreign_keys(tables: dict[str, list[dict[str, Any]]]) -> None:
    for child_table, child_column, parent_table, parent_column, nullable in RELATIONSHIPS:
        parent_values = {row.get(parent_column) for row in tables[parent_table]}
        child_values = [row.get(child_column) for row in tables[child_table]]
        if not nullable and any(value in (None, "") for value in child_values):
            raise RuntimeError(f"{child_table}.{child_column}: clé étrangère vide")
        missing = {value for value in child_values if value not in (None, "") and value not in parent_values}
        if missing:
            raise RuntimeError(
                f"{child_table}.{child_column}: {len(missing)} clé(s) absente(s) de "
                f"{parent_table}.{parent_column}"
            )


def _complete_indicator_dimension(
    headers: list[str],
    dictionary_rows: list[dict[str, Any]],
    observation_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing = {str(row["metric_id"]) for row in dictionary_rows}
    observations_by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in observation_rows:
        observations_by_metric.setdefault(str(row["metric_id"]), []).append(row)
    completed = list(dictionary_rows)
    for metric_id in sorted(set(observations_by_metric) - existing):
        observations = observations_by_metric[metric_id]
        units = sorted({str(row["unit"]) for row in observations if row.get("unit") not in (None, "")})
        sources = sorted({str(row["source_id"]) for row in observations if row.get("source_id")})
        has_numeric = any(row.get("value_numeric") is not None for row in observations)
        has_text = any(row.get("value_text") not in (None, "") for row in observations)
        record = {header: None for header in headers}
        record.update(
            {
                "metric_id": metric_id,
                "domain": "undocumented",
                "metric_name": metric_id,
                "definition": None,
                "data_type": "mixed" if has_numeric and has_text else "numeric" if has_numeric else "text",
                "unit": units[0] if len(units) == 1 else "mixed" if units else None,
                "primary_fact_sheet": "FACT_OBSERVATION",
                "required_keys": "metric_id",
                "candidate_sources": ";".join(sources),
                "collection_status": "OBSERVED_UNDOCUMENTED",
                "quality_rule": "Définition obligatoire avant interprétation analytique.",
                "notes": "Entrée de conformance dérivée; identifiant observé absent du DATA_DICTIONARY V13.",
            }
        )
        completed.append(record)
    return completed


def _communal_contest_id(row: dict[str, Any]) -> str:
    return f"CONTEST_{row['election_id']}_COMMUNE_{row['geo_id']}"


def _complete_contest_dimension(
    headers: list[str],
    contest_rows: list[dict[str, Any]],
    commune_election_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    completed = list(contest_rows)
    existing = {str(row["contest_id"]) for row in contest_rows}
    source_by_election = {
        "COMM2015": "SRC_TAFRA_COMM2015_RAW_V9",
        "COMM2021": "SRC_TAFRA_COMM2021_RAW_V9",
    }
    for row in commune_election_rows:
        contest_id = _communal_contest_id(row)
        if contest_id in existing:
            raise RuntimeError(f"contest communal dupliqué: {contest_id}")
        record = {header: None for header in headers}
        record.update(
            {
                "contest_id": contest_id,
                "election_id": row["election_id"],
                "geo_id": row["geo_id"],
                "list_type": "communal",
                "source_contest_id": row["geo_id"],
                "source_label": row["geo_id"],
                "normalized_label": row["geo_id"],
                "source_id": source_by_election[str(row["election_id"])],
                "identity_review_status": "canonical_geo_id",
                "notes": "Contest communal de conformance dérivé du grain commune × élection V13.",
            }
        )
        completed.append(record)
        existing.add(contest_id)
    return completed


def _write_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _write_table(table: pa.Table, csv_path: Path, parquet_path: Path) -> None:
    csv_buffer = pa.BufferOutputStream()
    pa_csv.write_csv(table, csv_buffer)
    _write_atomic(csv_path, csv_buffer.getvalue().to_pybytes())
    temporary = parquet_path.with_suffix(parquet_path.suffix + ".tmp")
    pq.write_table(
        table,
        temporary,
        compression="zstd",
        version="2.6",
        use_dictionary=True,
        write_statistics=True,
    )
    temporary.replace(parquet_path)


def render_readme(manifest: dict) -> str:
    lines = [
        "MOROCCO ELECTORAL DATA WAREHOUSE — PAQUET OUVERT V13",
        "",
        f"Release source : {manifest['release']}",
        f"Généré le : {manifest['generated_on']}",
        f"SHA-256 du classeur source : {manifest['source_workbook_sha256']}",
        "",
        "CONTENU",
        "",
        "Le paquet expose un seul modèle canonique sous trois accès: CSV, Parquet et DuckDB.",
        "Les fichiers ne sont pas trois produits différents; ils contiennent les mêmes tables et règles.",
        "",
    ]
    for table in manifest["tables"]:
        lines.append(
            f"- {table['table_name']}: {table['rows']} lignes; clé={','.join(table['primary_key'])}; "
            f"source Excel={table['source_sheet']}."
        )
    lines.extend(
        [
            "",
            "DÉMARRAGE RAPIDE",
            "",
            "DuckDB: SELECT * FROM fact_election_result LIMIT 10;",
            "Jointure: fact_election_result.contest_id = dim_electoral_contest.contest_id.",
            "Trois exemples reproductibles sont fournis dans queries.sql.",
            "Les checksums sont dans checksums.sha256; le schéma et les volumes sont dans manifest.json.",
            "La politique de licence du paquet composite est dans LICENSE_DATA.md.",
            "",
            "LIMITES ESSENTIELLES",
            "",
            "- LEG2002 n'est pas intégré.",
            "- Une cellule absente reste NULL et ne signifie jamais zéro.",
            "- Les géographies 2007/2011 restent liées à leur découpage historique.",
            "- Les agrégats doivent rester séparés par élection et type de liste.",
            "- Les conditions de réutilisation sont conservées source par source dans la table sources.",
            "- dim_indicator ajoute 43 entrées de conformance OBSERVED_UNDOCUMENTED; leur définition reste obligatoire avant interprétation.",
            "- Ce paquet ne contient ni RAW, ni noms de personnes, ni questions parlementaires nominatives.",
            "- Le fichier DuckDB porte un hash logique stable; son checksum binaire local figure dans checksums.sha256.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1 or manifest.get("release") != "V13":
        errors.append("version du manifeste de diffusion invalide")
    if manifest.get("publication_status") != "PUBLIC_BETA":
        errors.append("statut de publication invalide")
    tables = manifest.get("tables", [])
    if len(tables) != len(TABLES) or {item.get("table_name") for item in tables} != set(TABLES):
        errors.append(f"les {len(TABLES)} tables de diffusion sont requises")
    relationships = manifest.get("relationships", [])
    expected_relationships = {
        (child, child_column, parent, parent_column, nullable)
        for child, child_column, parent, parent_column, nullable in RELATIONSHIPS
    }
    observed_relationships = {
        (
            item.get("child_table"), item.get("child_column"), item.get("parent_table"),
            item.get("parent_column"), item.get("nullable"),
        )
        for item in relationships
        if isinstance(item, dict)
    }
    if observed_relationships != expected_relationships or len(relationships) != len(RELATIONSHIPS):
        errors.append("relations de clés étrangères incomplètes ou incohérentes")
    files = manifest.get("files", [])
    paths = [item.get("path") for item in files]
    expected_paths = {
        *(f"csv/{name}.csv" for name in TABLES),
        *(f"parquet/{name}.parquet" for name in TABLES),
        "morocco_elections_v13.duckdb",
        "README.txt",
        "LICENSE_DATA.md",
        "queries.sql",
    }
    if set(paths) != expected_paths or len(paths) != len(set(paths)):
        errors.append("inventaire des fichiers de diffusion incohérent")
    for item in files:
        if item.get("path") == "morocco_elections_v13.duckdb":
            if item.get("binary_reproducible") is not False:
                errors.append("le conteneur DuckDB doit déclarer sa non-reproductibilité binaire")
            if item.get("byte_size_reproducible") is not False or "byte_size" in item:
                errors.append("la taille physique DuckDB ne doit pas figurer dans le manifeste stable")
            if not isinstance(item.get("content_sha256"), str) or len(item["content_sha256"]) != 64:
                errors.append("hash logique DuckDB invalide")
        else:
            if not isinstance(item.get("byte_size"), int) or item["byte_size"] <= 0:
                errors.append(f"taille invalide: {item.get('path')}")
            if not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
                errors.append(f"SHA-256 invalide: {item.get('path')}")
    for table in tables:
        if not table.get("primary_key") or not table.get("columns") or not isinstance(table.get("rows"), int):
            errors.append(f"contrat incomplet: {table.get('table_name')}")
        elif table["rows"] != EXPECTED_ROWS.get(table["table_name"]):
            errors.append(f"volume V13 inattendu: {table['table_name']}")
    return errors


def build_distribution(
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    manifest_output: str | Path | None = None,
    readme_output: str | Path | None = None,
) -> dict:
    paths = get_paths(data_dir)
    workbook_path = paths.v13_workbook
    if not workbook_path.is_file():
        raise FileNotFoundError(workbook_path)
    release = json.loads(RELEASE_REPORT.read_text(encoding="utf-8"))
    expected_hash = release["workbooks"]["V13"]
    if sha256_file(workbook_path) != expected_hash:
        raise RuntimeError("Le classeur V13 ne correspond pas au rapport de release")

    destination = Path(output_dir) if output_dir else paths.data_root / "exports" / "open" / "v13"
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "csv").mkdir(exist_ok=True)
    (destination / "parquet").mkdir(exist_ok=True)
    allowed_existing = {
        *(destination / "csv" / f"{name}.csv" for name in TABLES),
        *(destination / "parquet" / f"{name}.parquet" for name in TABLES),
        destination / "morocco_elections_v13.duckdb",
        destination / "README.txt",
        destination / "LICENSE_DATA.md",
        destination / "queries.sql",
        destination / "manifest.json",
        destination / "checksums.sha256",
    }
    unexpected = [path for path in destination.rglob("*") if path.is_file() and path not in allowed_existing]
    if unexpected:
        raise RuntimeError(f"Fichiers inattendus dans le dossier de diffusion: {unexpected}")

    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    table_contracts = []
    table_rows: dict[str, list[dict[str, Any]]] = {}
    for table_name, contract in TABLES.items():
        sheet_name = contract["sheet"]
        key = contract["key"]
        headers, rows = rows_from_sheet(workbook[sheet_name])
        if table_name == "dim_electoral_contest":
            _, commune_election_rows = rows_from_sheet(workbook["COMMUNE_ELECTION_PANEL"])
            rows = _complete_contest_dimension(
                [str(value) for value in headers], rows, commune_election_rows
            )
        if table_name == "dim_indicator":
            _, observation_rows = rows_from_sheet(workbook["FACT_OBSERVATION"])
            rows = _complete_indicator_dimension([str(value) for value in headers], rows, observation_rows)
        if table_name in {"fact_communal_election_result", "fact_commune_election_summary"}:
            source_by_election = {
                "COMM2015": "SRC_TAFRA_COMM2015_RAW_V9",
                "COMM2021": "SRC_TAFRA_COMM2021_RAW_V9",
            }
            for row in rows:
                row["contest_id"] = _communal_contest_id(row)
                row["source_id"] = source_by_election[str(row["election_id"])]
                row["fact_status"] = "DERIVED_FROM_OBSERVED_RESULTS"
            headers = ["contest_id", *headers, "source_id", "fact_status"]
        if table_name in ROW_FILTERS:
            rows = [row for row in rows if ROW_FILTERS[table_name](row)]
        selected_columns = contract.get("columns", headers)
        unknown_columns = set(selected_columns) - set(headers)
        if unknown_columns:
            raise RuntimeError(f"{table_name}: colonnes sources absentes: {sorted(unknown_columns)}")
        rename = contract.get("rename", {})
        normalized_headers = [rename.get(str(value), str(value)) for value in selected_columns]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise RuntimeError(f"{table_name}: colonnes de sortie dupliquées après normalisation")
        rows = [
            {rename.get(str(column), str(column)): row.get(column) for column in selected_columns}
            for row in rows
        ]
        _validate_primary_key(table_name, rows, key)
        table_rows[table_name] = rows
        table = rows_to_arrow(normalized_headers, rows)
        _write_table(
            table,
            destination / "csv" / f"{table_name}.csv",
            destination / "parquet" / f"{table_name}.parquet",
        )
        table_contracts.append(
            {
                "table_name": table_name,
                "source_sheet": sheet_name,
                "rows": table.num_rows,
                "columns": [
                    {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                    for field in table.schema
                ],
                "primary_key": key,
            }
        )
    _validate_foreign_keys(table_rows)
    workbook.close()

    database_path = destination / "morocco_elections_v13.duckdb"
    temporary_database = database_path.with_suffix(".duckdb.tmp")
    temporary_database.unlink(missing_ok=True)
    connection = duckdb.connect(str(temporary_database))
    try:
        for table_name in TABLES:
            parquet_path = (destination / "parquet" / f"{table_name}.parquet").as_posix().replace("'", "''")
            connection.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM read_parquet(\'{parquet_path}\')')
        connection.execute(
            "CREATE TABLE warehouse_metadata AS SELECT ? AS release, ? AS generated_on, ? AS source_workbook_sha256",
            ["V13", GENERATED_ON, expected_hash],
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    temporary_database.replace(database_path)

    manifest = {
        "schema_version": 1,
        "release": "V13",
        "generated_on": GENERATED_ON,
        "publication_status": "PUBLIC_BETA",
        "published_on": "2026-09-12",
        "source_workbook_sha256": expected_hash,
        "scope": "Faits canoniques V13 non nominatifs: élections multi-scrutins, communes 2015–2021, observations territoriales et activité parlementaire.",
        "formats": ["CSV", "Parquet", "DuckDB"],
        "tables": table_contracts,
        "relationships": [
            {
                "child_table": child,
                "child_column": child_column,
                "parent_table": parent,
                "parent_column": parent_column,
                "nullable": nullable,
            }
            for child, child_column, parent, parent_column, nullable in RELATIONSHIPS
        ],
        "files": [],
        "license_rule": "ODbL 1.0 pour les droits originaux de structure et de compilation détenus par le projet; les contenus tiers restent régis source par source.",
    }
    readme = render_readme(manifest)
    _write_atomic(destination / "README.txt", readme.encode("utf-8"))
    _write_atomic(destination / "LICENSE_DATA.md", DATA_LICENSE.read_bytes())
    _write_atomic(destination / "queries.sql", REFERENCE_QUERIES.read_bytes())
    data_files = [
        *(destination / "csv" / f"{name}.csv" for name in TABLES),
        *(destination / "parquet" / f"{name}.parquet" for name in TABLES),
        database_path,
        destination / "README.txt",
        destination / "LICENSE_DATA.md",
        destination / "queries.sql",
    ]
    logical_digest = hashlib.sha256()
    for table_name in TABLES:
        parquet_path = destination / "parquet" / f"{table_name}.parquet"
        logical_digest.update(f"{table_name}:{sha256_file(parquet_path)}\n".encode("ascii"))
    for path in data_files:
        item = {
            "path": path.relative_to(destination).as_posix(),
            "byte_size": path.stat().st_size,
        }
        if path == database_path:
            item.pop("byte_size")
            item.update(
                {
                    "binary_reproducible": False,
                    "byte_size_reproducible": False,
                    "content_sha256": logical_digest.hexdigest(),
                }
            )
        else:
            item["sha256"] = sha256_file(path)
        manifest["files"].append(item)
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("Manifeste de diffusion invalide: " + "; ".join(errors))
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write_atomic(destination / "manifest.json", manifest_bytes)
    checksummed = [*data_files, destination / "manifest.json"]
    checksum_text = "".join(
        f"{sha256_file(path)}  {path.relative_to(destination).as_posix()}\n" for path in checksummed
    )
    _write_atomic(destination / "checksums.sha256", checksum_text.encode("utf-8"))

    tracked_manifest = Path(manifest_output) if manifest_output else DEFAULT_MANIFEST
    tracked_readme = Path(readme_output) if readme_output else DEFAULT_README
    tracked_manifest.parent.mkdir(parents=True, exist_ok=True)
    tracked_readme.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(tracked_manifest, manifest_bytes)
    _write_atomic(tracked_readme, readme.encode("utf-8"))
    return manifest


def run(
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    manifest_output: str | Path | None = None,
    readme_output: str | Path | None = None,
) -> int:
    manifest = build_distribution(data_dir, output_dir, manifest_output, readme_output)
    print(
        f"V13_OPEN_EXPORT_OK tables={len(manifest['tables'])} files={len(manifest['files'])} "
        f"rows={sum(item['rows'] for item in manifest['tables'])}"
    )
    return 0
