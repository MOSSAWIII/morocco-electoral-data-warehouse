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
    "dim_geo": ("DIM_GEO", ["geo_id"]),
    "dim_party": ("DIM_PARTY", ["party_id"]),
    "dim_election": ("DIM_ELECTION", ["election_id"]),
    "dim_electoral_contest": ("DIM_ELECTORAL_CONTEST", ["contest_id"]),
    "fact_election_result": ("FACT_ELECTION_RESULT", ["result_id"]),
    "fact_electoral_mobilization": ("FACT_ELECTORAL_MOBILIZATION", ["contest_id"]),
    "sources": ("SOURCES", ["source_id"]),
    "data_dictionary": ("DATA_DICTIONARY", ["metric_id"]),
}
EXPECTED_ROWS = {
    "dim_geo": 1_825,
    "dim_party": 57,
    "dim_election": 9,
    "dim_electoral_contest": 639,
    "fact_election_result": 10_883,
    "fact_electoral_mobilization": 639,
    "sources": 61,
    "data_dictionary": 292,
}


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
        errors.append("les huit tables de diffusion sont requises")
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
    for table_name, (sheet_name, key) in TABLES.items():
        headers, rows = rows_from_sheet(workbook[sheet_name])
        normalized_headers = [str(value) for value in headers]
        _validate_primary_key(table_name, rows, key)
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
        "scope": "Noyau électoral non nominatif V13 et dimensions/provenance nécessaires à ses jointures.",
        "formats": ["CSV", "Parquet", "DuckDB"],
        "tables": table_contracts,
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
