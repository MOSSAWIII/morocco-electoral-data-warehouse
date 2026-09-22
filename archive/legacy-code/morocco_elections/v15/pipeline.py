from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.provenance import sha256_file
from morocco_elections.quality.v15.logical import duckdb_digest
from morocco_elections.v15.coverage import coverage_matrix
from morocco_elections.v15.schema import (
    CORRECTIONS,
    PARTIAL_DATE_POLICIES,
    RELATIONSHIPS,
    SOURCE_DISTRIBUTION,
    TABLE_SPECS,
    all_table_contracts,
)
from morocco_elections.v15.queries import ANALYSES, CUBES, available_cubes, render_reference_queries

VERSION = "V15"
RELEASE_VERSION = "15.0.0"
SCHEMA_VERSION = 1
GENERATED_ON = "2026-09-13"
DEFAULT_SEED_RELEASE = "v14.1"
DATABASE_NAME = "morocco_elections_v15.duckdb"


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _date_policy(table_name: str, name: str) -> dict[str, Any] | None:
    return next(
        (row for row in PARTIAL_DATE_POLICIES if row["table_name"] == table_name and row["column"] == name),
        None,
    )


def _date_expression(table_name: str, name: str) -> str:
    quoted = _quote(name)
    policy = _date_policy(table_name, name)
    is_end = bool(policy and policy["start_or_end"] == "END")
    month_day = "12, 31" if is_end else "1, 1"
    month_value = (
        f"last_day(make_date(CAST(substr({quoted}, 1, 4) AS BIGINT), CAST(substr({quoted}, 6, 2) AS BIGINT), 1))"
        if is_end
        else f"make_date(CAST(substr({quoted}, 1, 4) AS BIGINT), CAST(substr({quoted}, 6, 2) AS BIGINT), 1)"
    )
    embedded_year = f"CAST(regexp_extract(TRIM(CAST({quoted} AS VARCHAR)), '([0-9]{{4}})', 1) AS BIGINT)"
    return (
        f"CASE WHEN regexp_full_match(TRIM(CAST({quoted} AS VARCHAR)), '[0-9]{{4}}') "
        f"THEN make_date(CAST({quoted} AS BIGINT), {month_day}) "
        f"WHEN regexp_full_match(TRIM(CAST({quoted} AS VARCHAR)), '[0-9]{{4}}-[0-9]{{2}}') THEN {month_value} "
        f"WHEN TRY_CAST(NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') AS DATE) IS NOT NULL "
        f"THEN TRY_CAST(NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') AS DATE) "
        f"WHEN regexp_matches(TRIM(CAST({quoted} AS VARCHAR)), '[0-9]{{4}}') "
        f"THEN make_date({embedded_year}, {month_day}) "
        f"ELSE NULL END"
    )


def _precision_expression(source_name: str) -> str:
    quoted = _quote(source_name)
    return (
        f"CASE WHEN NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') IS NULL THEN NULL "
        f"WHEN regexp_full_match(TRIM(CAST({quoted} AS VARCHAR)), '[0-9]{{4}}') THEN 'YEAR' "
        f"WHEN regexp_full_match(TRIM(CAST({quoted} AS VARCHAR)), '[0-9]{{4}}-[0-9]{{2}}') THEN 'MONTH' "
        f"WHEN TRY_CAST(TRIM(CAST({quoted} AS VARCHAR)) AS DATE) IS NOT NULL THEN 'DAY' "
        f"WHEN regexp_matches(TRIM(CAST({quoted} AS VARCHAR)), '[0-9]{{4}}') THEN 'LABEL_YEAR' "
        f"ELSE 'UNRESOLVED' END"
    )


def _base_expression(table_name: str, column: dict[str, Any]) -> str:
    source_name = column.get("source_column") or column["name"]
    quoted = _quote(source_name)
    derived = column.get("derived")
    if derived == "PRESERVE_SOURCE_VALUE":
        return f"CAST({quoted} AS VARCHAR)"
    if derived == "DATE_PRECISION":
        return _precision_expression(source_name)
    target_type = column["type"]
    if target_type == "VARCHAR":
        return f"CAST({quoted} AS VARCHAR)"
    if target_type == "BOOLEAN":
        return (
            f"CASE WHEN upper(TRIM(CAST({quoted} AS VARCHAR))) IN ('1', 'TRUE', 'YES', 'OUI') THEN TRUE "
            f"WHEN upper(TRIM(CAST({quoted} AS VARCHAR))) IN ('0', 'FALSE', 'NO', 'NON') THEN FALSE ELSE NULL END"
        )
    if target_type == "DATE":
        return _date_expression(table_name, source_name)
    return f"TRY_CAST(NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') AS {target_type})"


def _cast_expression(contract: dict[str, Any], column: dict[str, Any]) -> str:
    expression = _base_expression(contract["table_name"], column)
    corrections = [
        row for row in CORRECTIONS
        if row["table_name"] == contract["table_name"] and row["column"] == column["name"]
    ]
    if not corrections:
        return expression
    key_column = contract["primary_key"][0]
    clauses = []
    for correction in corrections:
        key = _sql_string(correction["record_key"])
        source_value = _sql_string(correction["source_value"])
        clauses.append(
            f"WHEN {_quote(key_column)} = {key} AND CAST({_quote(column['source_column'])} AS VARCHAR) = {source_value} THEN NULL"
        )
    return "CASE " + " ".join(clauses) + f" ELSE {expression} END"


def _safe_package_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in relative:
        raise RuntimeError(f"Chemin de paquet non sûr: {relative!r}")
    resolved = (root / candidate).resolve()
    if root.resolve() not in resolved.parents:
        raise RuntimeError(f"Chemin hors paquet: {relative!r}")
    return resolved


def _prepare_seed(seed_dir: Path) -> None:
    if (seed_dir / "manifest.json").is_file():
        return
    seed_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v14.1-source-", dir=seed_dir.parent) as temp_name:
        temporary = Path(temp_name)
        archive = temporary / SOURCE_DISTRIBUTION["asset_name"]
        with urllib.request.urlopen(SOURCE_DISTRIBUTION["download_url"], timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        if archive.stat().st_size != SOURCE_DISTRIBUTION["bytes"] or sha256_file(archive) != SOURCE_DISTRIBUTION["sha256"]:
            raise RuntimeError("Archive publique V14.1 différente de la distribution épinglée")
        extract = temporary / "extract"
        extract.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            if sum(info.file_size for info in bundle.infolist()) > 1_500_000_000:
                raise RuntimeError("Archive V14.1 trop volumineuse après décompression")
            for info in bundle.infolist():
                relative = PurePosixPath(info.filename)
                mode = info.external_attr >> 16
                if (
                    relative.is_absolute() or ".." in relative.parts or "\\" in info.filename
                    or any(":" in part for part in relative.parts) or stat.S_IFMT(mode) == stat.S_IFLNK
                ):
                    raise RuntimeError(f"Chemin non sûr dans l'archive V14.1: {info.filename!r}")
                target = extract.joinpath(*relative.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(info) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
        candidates = [path.parent for path in extract.rglob("manifest.json") if sha256_file(path) == SOURCE_DISTRIBUTION["manifest_sha256"]]
        if len(candidates) != 1:
            raise RuntimeError("Le manifeste V14.1 épinglé est absent ou ambigu dans l'archive")
        os.replace(candidates[0], seed_dir)


def _load_seed(seed_dir: Path) -> dict[str, Any]:
    manifest_path = seed_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Paquet source public absent: {manifest_path}. Exécutez `python -m morocco_elections bootstrap` "
            "ou fournissez --seed-dir vers un paquet V14.1 public vérifié."
        )
    if sha256_file(manifest_path) != SOURCE_DISTRIBUTION["manifest_sha256"]:
        raise RuntimeError("Le manifeste source V14.1 ne correspond pas à l'empreinte épinglée")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("release") != "V14.1":
        raise RuntimeError(f"Le paquet source doit être V14.1, obtenu {manifest.get('release')!r}")
    checksums = seed_dir / "checksums.sha256"
    if not checksums.is_file():
        raise FileNotFoundError(f"Checksums source absents: {checksums}")
    for line_number, line in enumerate(checksums.read_text(encoding="ascii").splitlines(), start=1):
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise RuntimeError(f"Ligne de checksum V14.1 invalide: {line_number}") from exc
        path = _safe_package_path(seed_dir, relative)
        if not path.is_file() or sha256_file(path) != digest:
            raise RuntimeError(f"Fichier source V14.1 absent ou altéré: {relative}")
    tables = {row["table_name"]: row for row in manifest.get("tables", [])}
    missing = [item.source_name for item in TABLE_SPECS if item.source_name not in tables]
    if missing:
        raise RuntimeError(f"Tables source absentes: {', '.join(missing)}")
    for item in TABLE_SPECS:
        path = seed_dir / "parquet" / f"{item.source_name}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Parquet source absent: {path}")
        source = tables[item.source_name]
        expected_columns = [
            column["source_column"] for column in item.columns
            if not column.get("derived") and column.get("source_column")
        ]
        if [column["name"] for column in source["columns"]] != expected_columns:
            raise RuntimeError(f"Dérive de colonnes V14.1 pour {item.source_name}")
        if source["rows"] != item.expected_rows:
            raise RuntimeError(f"Dérive de volume V14.1 pour {item.source_name}")
    return manifest


def _table_contracts(seed_manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del seed_manifest
    return all_table_contracts(), [dict(row) for row in RELATIONSHIPS]


def _ddl(contract: dict[str, Any], *, include_foreign_keys: bool = True) -> str:
    definitions = []
    for column in contract["columns"]:
        item = f'{_quote(column["name"])} {column["type"]}'
        if not column["nullable"]:
            item += " NOT NULL"
        for check in column["checks"]:
            item += f" CHECK ({check})"
        if column.get("domain"):
            values = ", ".join(_sql_string(value) for value in column["domain"])
            item += f" CHECK ({_quote(column['name'])} IN ({values}))"
        definitions.append(item)
    definitions.append("PRIMARY KEY (" + ", ".join(_quote(name) for name in contract["primary_key"]) + ")")
    if contract["natural_key"] != contract["primary_key"]:
        definitions.append("UNIQUE (" + ", ".join(_quote(name) for name in contract["natural_key"]) + ")")
    definitions.extend(f"CHECK ({check})" for check in contract["table_checks"])
    for relation in RELATIONSHIPS:
        if include_foreign_keys and relation["child_table"] == contract["table_name"]:
            definitions.append(
                f"FOREIGN KEY ({_quote(relation['child_column'])}) REFERENCES "
                f"{_quote(relation['parent_table'])} ({_quote(relation['parent_column'])})"
            )
    return f'CREATE TABLE {_quote(contract["table_name"])} (\n  ' + ",\n  ".join(definitions) + "\n)"


def _create_tables(connection: duckdb.DuckDBPyConnection, seed_dir: Path, contracts: list[dict[str, Any]]) -> None:
    by_name = {contract["table_name"]: contract for contract in contracts}
    dependencies = {
        name: {
            relation["parent_table"] for relation in RELATIONSHIPS
            if relation["child_table"] == name and relation["parent_table"] != name
        }
        for name in by_name
    }
    ordered: list[dict[str, Any]] = []
    pending = set(by_name)
    while pending:
        ready = sorted(name for name in pending if not dependencies[name] & pending)
        if not ready:
            raise RuntimeError("Cycle de dépendances dans le contrat V15: " + ", ".join(sorted(pending)))
        ordered.extend(by_name[name] for name in ready)
        pending.difference_update(ready)
    for contract in ordered:
        connection.execute(_ddl(contract))
    for contract in ordered:
        source_path = seed_dir / "parquet" / f'{contract["source_table"]}.parquet'
        source_sql = f"read_parquet({_sql_string(source_path.as_posix())})"
        expressions = [f'{_cast_expression(contract, column)} AS {_quote(column["name"])}' for column in contract["columns"]]
        connection.execute(
            f'INSERT INTO {_quote(contract["table_name"])} SELECT {", ".join(expressions)} FROM {source_sql}'
        )
        for column in contract["columns"]:
            if column["type"] == "VARCHAR" or column.get("derived"):
                continue
            source_name = column.get("source_column") or column["name"]
            source_nonempty, target_nonnull = connection.execute(
                f"SELECT "
                f"(SELECT count(*) FROM {source_sql} WHERE NULLIF(TRIM(CAST({_quote(source_name)} AS VARCHAR)), '') IS NOT NULL "
                f"AND upper(TRIM(CAST({_quote(source_name)} AS VARCHAR))) NOT IN ('UNKNOWN', 'UNRESOLVED', 'N/A', 'NA')), "
                f"(SELECT count({_quote(column['name'])}) FROM {_quote(contract['table_name'])})"
            ).fetchone()
            allowed_loss = sum(
                correction["table_name"] == contract["table_name"] and correction["column"] == column["name"]
                for correction in CORRECTIONS
            )
            if source_nonempty - target_nonnull != allowed_loss:
                raise RuntimeError(
                    f"Conversion avec perte: {contract['table_name']}.{column['name']} "
                    f"({source_nonempty - target_nonnull} valeur(s) non convertible(s))"
                )


def _create_cubes(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    for definition in available_cubes():
        connection.execute(definition["view_sql"])
    return [
        {key: value for key, value in definition.items() if key != "view_sql"}
        for definition in CUBES
    ]


def _arrow_type(name: str) -> pa.DataType:
    return {
        "VARCHAR": pa.string(),
        "BIGINT": pa.int64(),
        "DOUBLE": pa.float64(),
        "BOOLEAN": pa.bool_(),
        "DATE": pa.date32(),
    }[name]


def _write_exports(
    connection: duckdb.DuckDBPyConnection, destination: Path, contracts: list[dict[str, Any]]
) -> dict[str, str]:
    (destination / "csv").mkdir(parents=True, exist_ok=True)
    (destination / "parquet").mkdir(parents=True, exist_ok=True)
    for contract in contracts:
        name = contract["table_name"]
        order = ", ".join(_quote(column) for column in contract["primary_key"])
        query = f"SELECT * FROM {_quote(name)} ORDER BY {order}"
        connection.execute(
            f"COPY ({query}) TO {_sql_string((destination / 'csv' / f'{name}.csv').as_posix())} "
            "(HEADER, DELIMITER ',', QUOTE '\"', ESCAPE '\"')"
        )
        schema = pa.schema(
            [
                pa.field(column["name"], _arrow_type(column["type"]), nullable=column["nullable"])
                for column in contract["columns"]
            ]
        )
        table = connection.execute(query).fetch_arrow_table().cast(schema)
        pq.write_table(table, destination / "parquet" / f"{name}.parquet", compression="zstd")
    return {contract["table_name"]: duckdb_digest(connection, contract)[0] for contract in contracts}


def _readme(manifest: dict[str, Any]) -> str:
    core = [row["table_name"] for row in manifest["tables"] if row["category"] == "CORE"]
    return "\n".join(
        [
            "# Morocco Electoral Data Warehouse — V15",
            "",
            "Paquet public autonome en CSV, Parquet et DuckDB. Les trois formats exposent les mêmes tables et volumes.",
            "",
            "## Démarrage",
            "",
            "```shell",
            f"duckdb {DATABASE_NAME}",
            "```",
            "",
            "```sql",
            "SELECT * FROM cube_electoral_competitiveness LIMIT 10;",
            "```",
            "",
            "Tables CORE : " + ", ".join(f"`{name}`" for name in core) + ".",
            "",
            "Exécuter les cinq analyses : `python -m morocco_elections analyze reference`.",
            "Vérifier le paquet : `python -m morocco_elections validate --mode public`.",
            "",
            "## Portée honnête",
            "",
            "- Utilisation du paquet public : autonome, sans Excel ni chemin privé.",
            "- Reconstruction publique V15 : possible depuis le paquet public V14.1 vérifié.",
            "- Reconstruction historique complète : exige certaines sources locales non redistribuables.",
            "- La couverture des questions parlementaires est UNKNOWN sans dénominateur officiel.",
            "- Les identités ambiguës restent NULL ou UNRESOLVED; aucun classement individuel n'est publié.",
            "",
        ]
    )


def _dictionary(contracts: list[dict[str, Any]]) -> str:
    lines = ["# Dictionnaire physique V15", "", "Ce document est généré depuis le contrat canonique unique.", ""]
    for table in contracts:
        foreign_keys = [
            f"{row['child_column']} → {row['parent_table']}.{row['parent_column']}"
            for row in RELATIONSHIPS if row["child_table"] == table["table_name"]
        ]
        lines.extend(
            [
                f"## {table['table_name']} ({table['category']})", "", f"Grain : {table['grain']}.", "",
                "Clé primaire : " + ", ".join(table["primary_key"]) + ".", "",
                "Clé naturelle : " + ", ".join(table["natural_key"]) + ".", "",
                "Clés étrangères : " + ("; ".join(foreign_keys) if foreign_keys else "aucune") + ".", "",
                "| Colonne | Type | Null | Rôle | Unité | Domaine | Contraintes |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        lines.extend(
            f"| {column['name']} | {column['type']} | {'oui' if column['nullable'] else 'non'} | "
            f"{column['role']} | {column['unit'] or ''} | {', '.join(map(str, column['domain'] or []))} | "
            f"{' ; '.join(column['checks'])} |"
            for column in table["columns"]
        )
        if table["table_checks"]:
            lines.extend(["", "Contraintes de table : " + "; ".join(table["table_checks"]) + "."])
        lines.append("")
    return "\n".join(lines)


def _queries() -> str:
    return render_reference_queries()


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    reproducibility = "LOGICAL" if relative == DATABASE_NAME else "BINARY"
    return {
        "path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path),
        "reproducibility": reproducibility,
    }


def _finalize(destination: Path, manifest: dict[str, Any]) -> None:
    assets = {
        "README.md": _readme(manifest),
        "DATA_DICTIONARY.md": _dictionary(manifest["tables"]),
        "queries.sql": _queries(),
        "coverage_matrix.json": json.dumps(manifest["coverage_matrix"], ensure_ascii=False, indent=2) + "\n",
    }
    for name, text in assets.items():
        (destination / name).write_text(text, encoding="utf-8", newline="\n")
    shutil.copy2(PROJECT_ROOT / "LICENSES" / "DATA.md", destination / "LICENSE_DATA.md")
    shutil.copy2(PROJECT_ROOT / "LICENSES" / "DOCUMENTATION.md", destination / "LICENSE_DOCUMENTATION.md")
    shutil.copy2(PROJECT_ROOT / "ATTRIBUTIONS.md", destination / "ATTRIBUTIONS.md")
    shutil.copy2(PROJECT_ROOT / "CITATION.cff", destination / "CITATION.cff")
    files = sorted(
        (path for path in destination.rglob("*") if path.is_file() and path.name not in {"manifest.json", "checksums.sha256"}),
        key=lambda path: path.relative_to(destination).as_posix(),
    )
    manifest["files"] = [_file_record(path, destination) for path in files]
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    files.append(destination / "manifest.json")
    lines = [f"{sha256_file(path)}  {path.relative_to(destination).as_posix()}" for path in sorted(files, key=lambda p: p.relative_to(destination).as_posix())]
    (destination / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def _zip_package(destination: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_suffix(".zip.tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(destination.rglob("*"), key=lambda item: item.relative_to(destination).as_posix()):
            if path.is_file():
                relative = (Path("morocco_elections_v15") / path.relative_to(destination)).as_posix()
                info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                output.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    temporary.replace(archive)


def _replace_package(staging: Path, destination: Path, temporary_root: Path) -> None:
    backup = temporary_root / "previous"
    moved_previous = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            moved_previous = True
        os.replace(staging, destination)
    except OSError:
        if moved_previous and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise


def build(
    data_dir: str | Path | None = None,
    *,
    seed_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    paths = get_paths(data_dir)
    seed = Path(seed_dir).resolve() if seed_dir else paths.data_root / "exports" / "open" / DEFAULT_SEED_RELEASE
    destination = Path(output_dir).resolve() if output_dir else paths.data_root / "exports" / "open" / "v15"
    _prepare_seed(seed)
    seed_manifest = _load_seed(seed)
    contracts, relationships = _table_contracts(seed_manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v15-build-", dir=destination.parent) as temp_name:
        staging = Path(temp_name) / "package"
        staging.mkdir()
        database = staging / DATABASE_NAME
        connection = duckdb.connect(str(database))
        try:
            _create_tables(connection, seed, contracts)
            cubes = _create_cubes(connection)
            observed_indicator_ids = [
                row[0] for row in connection.execute(
                    "SELECT DISTINCT indicator_id FROM fact_observation ORDER BY indicator_id"
                ).fetchall()
            ]
            non_observed_indicators = [
                {"indicator_id": row[0], "catalog_status": row[1] or "UNSPECIFIED"}
                for row in connection.execute(
                    "SELECT indicator_id, collection_status FROM dim_indicator "
                    "WHERE indicator_id NOT IN (SELECT DISTINCT indicator_id FROM fact_observation) ORDER BY indicator_id"
                ).fetchall()
            ]
            connection.execute(
                "CREATE TABLE warehouse_metadata (release VARCHAR PRIMARY KEY, schema_version BIGINT NOT NULL, source_release VARCHAR NOT NULL)"
            )
            connection.execute("INSERT INTO warehouse_metadata VALUES ('V15', ?, 'V14.1')", [SCHEMA_VERSION])
            logical_digests = _write_exports(connection, staging, contracts)
            coverage = coverage_matrix(connection)
            connection.execute("CHECKPOINT")
        finally:
            connection.close()
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "release": VERSION,
            "release_version": RELEASE_VERSION,
            "generated_on": GENERATED_ON,
            "source_release": "V14.1",
            "pipeline": "morocco_elections.v15.pipeline",
            "publication_status": "PUBLIC",
            "coverage_interpretation": "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR",
            "core_tables": [item.name for item in TABLE_SPECS if item.category == "CORE"],
            "tables": contracts,
            "relationships": relationships,
            "corrections": list(CORRECTIONS),
            "logical_digests": logical_digests,
            "reproducibility": {
                "logical_tables": "SHA-256 over typed rows sorted by primary key",
                "duckdb_container": "LOGICAL; internal DuckDB storage identifiers may vary",
                "csv_parquet_documentation": "BINARY",
                "zip": "deterministic member order and timestamp; binary identity follows member reproducibility",
            },
            "coverage_matrix": coverage,
            "provenance": {
                "source_package": "V14.1 public package (location supplied at build time)",
                "source_manifest_sha256": sha256_file(seed / "manifest.json"),
                "source_payloads": seed_manifest.get("source_payloads", []),
            },
            "indicator_status": {
                "observed_count": len(observed_indicator_ids),
                "observed_definition": "indicator_id referenced by at least one fact_observation row",
                "observed_indicator_ids": observed_indicator_ids,
                "not_observed": non_observed_indicators,
            },
            "cubes": cubes,
            "analyses": [{key: value for key, value in row.items() if key != "sql"} for row in ANALYSES],
            "reconstruction_modes": {
                "public_package_use": "AVAILABLE",
                "public_source_rebuild": "AVAILABLE_FROM_VERIFIED_V14_1_PACKAGE",
                "complete_historical_rebuild": "REQUIRES_LOCAL_NON_REDISTRIBUTABLE_SOURCES",
            },
            "files": [],
        }
        _finalize(staging, manifest)
        from morocco_elections.quality.v15.package import validate_package

        staging_errors = validate_package(staging)
        if staging_errors:
            raise RuntimeError("Validation du build V15 en staging échouée: " + "; ".join(staging_errors[:5]))
        _replace_package(staging, destination, Path(temp_name))
    archive = paths.data_root / "exports" / "open" / "releases" / "Morocco_Electoral_Data_Warehouse_V15.zip"
    _zip_package(destination, archive)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    manifest["archive"] = {"path": str(archive), "bytes": archive.stat().st_size, "sha256": sha256_file(archive)}
    return manifest


def main(data_dir: str | Path | None = None, seed_dir: str | Path | None = None, output_dir: str | Path | None = None) -> int:
    manifest = build(data_dir, seed_dir=seed_dir, output_dir=output_dir)
    print(
        f"V15_BUILD_OK tables={len(manifest['tables'])} core={len(manifest['core_tables'])} "
        f"archive={manifest['archive']['path']} sha256={manifest['archive']['sha256']}"
    )
    return 0
