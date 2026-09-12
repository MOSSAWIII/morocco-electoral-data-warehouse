from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb
import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.domains.parliament.longitudinal import (
    build_longitudinal_model,
    load_acquired_questions,
    load_source_records,
)
from morocco_elections.exports import open_v13
from morocco_elections.legacy.v9.build import rows_from_sheet
from morocco_elections.provenance import sha256_file


VERSION = "V14"
GENERATED_ON = "2026-09-12"
DEFAULT_OUTPUT = get_paths().data_root / "exports" / "open" / "v14"
DEFAULT_MANIFEST = PROJECT_ROOT / "metadata" / "v14_open_distribution.json"
DEFAULT_README = PROJECT_ROOT / "docs" / "publication" / "V14_OPEN_DATA_README.txt"
DATA_LICENSE = PROJECT_ROOT / "LICENSES" / "DATA.md"
ATTRIBUTIONS = PROJECT_ROOT / "ATTRIBUTIONS.md"
CITATION = PROJECT_ROOT / "CITATION.cff"
REFERENCE_QUERIES = PROJECT_ROOT / "examples" / "v14_reference_queries.sql"
SOURCE_MANIFEST = PROJECT_ROOT / "metadata" / "source_manifest.json"

V13_SOURCE_FAMILIES = {
    "SRC_PARLIAMENT_WRITTEN_APRIL_2023_V12": "PARLIAMENT_WRITTEN_QUESTIONS_APRIL_2017_2023",
    "SRC_PARLIAMENT_WRITTEN_APR_OCT_2023_V12": "PARLIAMENT_WRITTEN_QUESTIONS_APR_OCT_2017_2023",
    "SRC_PARLIAMENT_WRITTEN_OCTOBER_2023_V12": "PARLIAMENT_WRITTEN_QUESTIONS_OCTOBER_2016_2023",
    "SRC_PARLIAMENT_WRITTEN_OCT_APR_2023_2024_V12": "PARLIAMENT_WRITTEN_QUESTIONS_OCT_APR_2016_2024",
}

NEW_TABLE_KEYS = {
    "dim_parliamentary_period": ["period_id"],
    "dim_institution": ["institution_id"],
    "dim_parliamentary_subject": ["subject_id"],
    "dim_parliamentary_author": ["author_id"],
    "dim_parliamentary_group": ["group_id"],
    "dim_parliamentary_source": ["source_id"],
    "fact_parliamentary_question": ["question_id"],
    "fact_parliamentary_response": ["response_id"],
    "bridge_question_author": ["question_author_id"],
    "bridge_question_source": ["question_source_id"],
    "analytical_parliamentary_trajectory": ["trajectory_id"],
}
PUBLIC_COLUMNS = {
    "dim_parliamentary_author": [
        "author_id", "legislature", "person_id", "identity_match_method",
    ],
}
EXPECTED_NEW_ROWS = {
    "dim_parliamentary_period": 30,
    "dim_institution": 94,
    "dim_parliamentary_subject": 58_806,
    "dim_parliamentary_author": 1_622,
    "dim_parliamentary_group": 19,
    "dim_parliamentary_source": 59,
    "fact_parliamentary_question": 65_748,
    "fact_parliamentary_response": 30_257,
    "bridge_question_author": 65_748,
    "bridge_question_source": 66_974,
    "analytical_parliamentary_trajectory": 3_142,
}
NEW_RELATIONSHIPS = [
    ("fact_parliamentary_question", "period_id", "dim_parliamentary_period", "period_id", False),
    ("fact_parliamentary_question", "institution_id", "dim_institution", "institution_id", False),
    ("fact_parliamentary_question", "subject_id", "dim_parliamentary_subject", "subject_id", False),
    ("fact_parliamentary_response", "question_id", "fact_parliamentary_question", "question_id", False),
    ("bridge_question_author", "question_id", "fact_parliamentary_question", "question_id", False),
    ("bridge_question_author", "author_id", "dim_parliamentary_author", "author_id", False),
    ("bridge_question_author", "person_id", "dim_person_public", "person_id", True),
    ("bridge_question_author", "party_id", "dim_party", "party_id", True),
    ("bridge_question_author", "group_id", "dim_parliamentary_group", "group_id", False),
    ("bridge_question_source", "question_id", "fact_parliamentary_question", "question_id", False),
    ("bridge_question_source", "source_id", "dim_parliamentary_source", "source_id", False),
    ("analytical_parliamentary_trajectory", "person_id", "dim_person_public", "person_id", False),
    ("analytical_parliamentary_trajectory", "party_id", "dim_party", "party_id", True),
    ("analytical_parliamentary_trajectory", "period_id", "dim_parliamentary_period", "period_id", False),
]

EXPECTED_CONTROLS = {
    "registered_source_records": 60,
    "unique_source_payloads": 59,
    "duplicate_source_payloads": 1,
    "source_families": 8,
    "source_occurrences": 66_974,
    "canonical_questions": 65_748,
    "duplicate_occurrences": 1_226,
    "natural_key_conflicts": 0,
    "baseline_questions_registered": 5_589,
    "baseline_questions_preserved": 5_589,
    "written_questions": 40_225,
    "oral_questions": 25_523,
    "responses_published": 30_257,
    "canonical_authors": 1_622,
    "identity_linked_questions": 26_932,
    "identity_unresolved_questions": 38_816,
    "identity_ambiguous_questions": 0,
    "linked_people": 365,
    "party_linked_questions": 26_932,
    "trajectory_rows": 3_142,
    "max_questions_per_author": 2_446,
    "max_questions_per_trajectory": 708,
    "first_deposit_date": "2017-01-25",
    "last_deposit_date": "2024-04-24",
}


def _manifest_relationships(base_manifest: dict[str, Any]) -> list[tuple[str, str, str, str, bool]]:
    relationships = [
        (
            item["child_table"], item["child_column"], item["parent_table"],
            item["parent_column"], item["nullable"],
        )
        for item in base_manifest["relationships"]
        if item["child_table"] != "fact_parliamentary_activity"
        and item["parent_table"] != "fact_parliamentary_activity"
    ]
    return [*relationships, *NEW_RELATIONSHIPS]


def _validate_foreign_keys(
    tables: dict[str, list[dict[str, Any]]],
    relationships: list[tuple[str, str, str, str, bool]],
) -> None:
    for child, child_column, parent, parent_column, nullable in relationships:
        parents = {row.get(parent_column) for row in tables[parent]}
        values = [row.get(child_column) for row in tables[child]]
        if not nullable and any(value in (None, "") for value in values):
            raise RuntimeError(f"{child}.{child_column}: clé étrangère obligatoire vide")
        missing = {value for value in values if value not in (None, "") and value not in parents}
        if missing:
            raise RuntimeError(f"{child}.{child_column}: {len(missing)} clé(s) étrangère(s) absente(s)")


def _public_model(model: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for table_name, rows in model.items():
        columns = PUBLIC_COLUMNS.get(table_name)
        result[table_name] = (
            [{column: row.get(column) for column in columns} for row in rows]
            if columns
            else rows
        )
    return result


def _load_v13_question_occurrences(
    question_rows: list[dict[str, Any]],
    workbook_sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    physical = {
        row["source_id"]: row
        for row in manifest["sources"]
        if row["source_id"] in V13_SOURCE_FAMILIES
    }
    descriptive = {row["source_id"]: row for row in workbook_sources}
    if set(physical) != set(V13_SOURCE_FAMILIES):
        raise RuntimeError("les quatre sources parlementaires V13 ne sont pas manifestées")
    normalized_sources: list[dict[str, Any]] = []
    for source_id, family_id in V13_SOURCE_FAMILIES.items():
        source = physical[source_id]
        description = descriptive.get(source_id, {})
        normalized_sources.append(
            {
                "source_id": family_id,
                "title": description.get("source_name") or source_id,
                "producer": source["producer"],
                "initial_url": source["source_url"],
                "reuse_status": source["license"],
                "retrieved_at": description.get("last_checked") or "2026-09-09",
                "sha256": source["sha256"],
                "byte_size": source["byte_size"],
            }
        )
    sources_by_id = {
        source_id: next(row for row in normalized_sources if row["source_id"] == family_id)
        for source_id, family_id in V13_SOURCE_FAMILIES.items()
    }
    occurrences: list[dict[str, Any]] = []
    for row in question_rows:
        source = sources_by_id[str(row["source_id"])]
        deposit_date = row["deposit_date"]
        response_date = row.get("response_date")
        occurrences.append(
            {
                "question_type": str(row["question_type"]),
                "source_question_number": str(row["source_question_number"]),
                "deposit_date": deposit_date.isoformat() if hasattr(deposit_date, "isoformat") else str(deposit_date),
                "period_raw": str(row.get("period_raw") or ""),
                "deputy_name_ar_raw": str(row.get("deputy_name_ar_raw") or ""),
                "parliamentary_group_ar_raw": str(row.get("parliamentary_group_ar_raw") or ""),
                "ministry_ar_raw": str(row.get("ministry_ar_raw") or ""),
                "subject_ar": str(row.get("subject_ar") or ""),
                "question_text_ar": str(row.get("question_text_ar") or ""),
                "response_date": (
                    response_date.isoformat() if hasattr(response_date, "isoformat") else str(response_date)
                ) if response_date else None,
                "source_family_id": source["source_id"],
                "source_id": f"SRC_PARLIAMENT_{source['sha256'][:16].upper()}",
                "source_sha256": source["sha256"],
                "source_row": int(row["source_row"]),
            }
        )
    return occurrences, normalized_sources


def _build_controls(
    occurrences: list[dict[str, Any]],
    model: dict[str, list[dict[str, Any]]],
    unique_sources: list[dict[str, Any]],
    inventory_sources: list[dict[str, Any]],
    baseline_occurrences: list[dict[str, Any]],
) -> dict[str, Any]:
    questions = model["fact_parliamentary_question"]
    author_links = model["bridge_question_author"]
    authors = {row["author_id"]: row for row in model["dim_parliamentary_author"]}
    question_types = Counter(row["question_type"] for row in questions)
    author_counts = Counter(row["author_id"] for row in author_links)
    methods = Counter(authors[row["author_id"]]["identity_match_method"] for row in author_links)
    baseline_keys = {
        (
            str(row["question_type"]).strip().casefold(),
            str(row["source_question_number"]).strip().casefold(),
            row["deposit_date"],
        )
        for row in baseline_occurrences
    }
    question_keys = {
        (
            str(row["question_type"]).strip().casefold(),
            str(row["source_question_number"]).strip().casefold(),
            row["deposit_date"],
        )
        for row in questions
    }
    return {
        "registered_source_records": len(inventory_sources),
        "unique_source_payloads": len(unique_sources),
        "duplicate_source_payloads": len(inventory_sources) - len(unique_sources),
        "source_families": len({row["source_id"] for row in inventory_sources}),
        "source_occurrences": len(occurrences),
        "canonical_questions": len(questions),
        "duplicate_occurrences": len(occurrences) - len(questions),
        "natural_key_conflicts": 0,
        "baseline_questions_registered": len(baseline_keys),
        "baseline_questions_preserved": len(baseline_keys & question_keys),
        "written_questions": question_types["written"],
        "oral_questions": question_types["oral"],
        "responses_published": len(model["fact_parliamentary_response"]),
        "canonical_authors": len(authors),
        "identity_linked_questions": methods["unicode_exact_legislature"],
        "identity_unresolved_questions": methods["unresolved_no_exact_match"],
        "identity_ambiguous_questions": methods["ambiguous_unicode_exact_no_link"],
        "linked_people": len({row["person_id"] for row in author_links if row["person_id"]}),
        "party_linked_questions": sum(bool(row["party_id"]) for row in author_links),
        "trajectory_rows": len(model["analytical_parliamentary_trajectory"]),
        "max_questions_per_author": max(author_counts.values()),
        "max_questions_per_trajectory": max(
            row["question_count"] for row in model["analytical_parliamentary_trajectory"]
        ),
        "first_deposit_date": min(row["deposit_date"] for row in questions),
        "last_deposit_date": max(row["deposit_date"] for row in questions),
    }


def render_readme(manifest: dict[str, Any]) -> str:
    lines = [
        "MOROCCO ELECTORAL DATA WAREHOUSE — PAQUET OUVERT V14",
        "",
        f"Généré le : {manifest['generated_on']}",
        f"SHA-256 du classeur V13 de base : {manifest['baseline_workbook_sha256']}",
        "",
        "PÉRIMÈTRE",
        "",
        "V14 conserve les faits ouverts V13 et remplace le sous-ensemble parlementaire 2023–2024",
        "par l'union dédupliquée de ce sous-ensemble et des nouvelles questions écrites ou orales 2017–2024.",
        "La couverture décrit les 59 fichiers uniques disponibles; elle ne prouve pas l'exhaustivité de l'activité parlementaire.",
        "",
        "TABLES",
        "",
    ]
    for table in manifest["tables"]:
        lines.append(
            f"- {table['table_name']}: {table['rows']} lignes; clé={','.join(table['primary_key'])}."
        )
    lines.extend(
        [
            "",
            "DÉMARRAGE RAPIDE",
            "",
            "DuckDB: SELECT * FROM fact_parliamentary_question LIMIT 10;",
            "Trois requêtes reproductibles sont fournies dans queries.sql.",
            "Les relations sont déclarées dans manifest.json et tous les fichiers sont couverts par checksums.sha256.",
            "Les licences, attributions et informations de citation sont incluses dans le paquet.",
            "",
            "LIMITES",
            "",
            "- Une question est identifiée par type × numéro source × date de dépôt.",
            (
                f"- {manifest['controls']['source_occurrences']:,} occurrences source sont conservées pour "
                f"{manifest['controls']['canonical_questions']:,} questions dédupliquées."
            ).replace(",", " "),
            "- Les auteurs sont raccordés uniquement par identité Unicode exacte dans la même législature.",
            "- Un auteur non raccordé garde person_id=NULL; aucun rapprochement flou n'est appliqué.",
            "- Le parti est attribué seulement via un mandat de la même législature pour une identité exacte.",
            "- Les trajectoires sont dérivées uniquement pour les personnes raccordées; leur taux de réponse",
            "  vaut 100 × questions avec date de réponse / questions publiées du groupe.",
            "- Les libellés d'auteur ne sont pas diffusés dans le paquet public.",
            "- Une absence de date de réponse signifie seulement non publiée dans les fichiers disponibles.",
            "- Les textes et objets restent des champs source; aucune taxonomie thématique n'est inventée.",
            f"- Le maximum observé est de {manifest['controls']['max_questions_per_author']} questions pour un auteur source;",
            "  cette valeur répartie sur plusieurs fichiers et années est conservée, sans conclure à sa représentativité.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1 or manifest.get("release") != VERSION:
        errors.append("version du manifeste V14 invalide")
    if manifest.get("publication_status") != "PUBLIC_BETA":
        errors.append("statut de publication V14 invalide")
    if manifest.get("published_on") != GENERATED_ON or manifest.get("generated_on") != GENERATED_ON:
        errors.append("date de publication V14 invalide")
    tables = manifest.get("tables", [])
    table_names = {item.get("table_name") for item in tables if isinstance(item, dict)}
    expected_tables = (set(open_v13.TABLES) - {"fact_parliamentary_activity"}) | set(NEW_TABLE_KEYS)
    if table_names != expected_tables or len(tables) != len(expected_tables):
        errors.append("ensemble des tables V14 incohérent")
    by_name = {item.get("table_name"): item for item in tables if isinstance(item, dict)}
    for table_name, expected in EXPECTED_NEW_ROWS.items():
        if by_name.get(table_name, {}).get("rows") != expected:
            errors.append(f"volume V14 inattendu: {table_name}")
    if by_name.get("fact_parliamentary_activity"):
        errors.append("l'ancien sous-ensemble parlementaire V13 ne doit pas être dupliqué")
    author_columns = {
        item.get("name") for item in by_name.get("dim_parliamentary_author", {}).get("columns", [])
    }
    if author_columns != set(PUBLIC_COLUMNS["dim_parliamentary_author"]):
        errors.append("colonnes publiques de l'auteur parlementaire incohérentes")
    if {"author_name_ar_raw", "author_source_key", "person_name_match_key"} & author_columns:
        errors.append("un libellé nominatif d'auteur est exposé dans V14")
    relationships = manifest.get("relationships", [])
    if not relationships or any(
        item.get("child_table") not in table_names or item.get("parent_table") not in table_names
        for item in relationships
    ):
        errors.append("relations V14 invalides")
    files = manifest.get("files", [])
    expected_paths = {
        *(f"csv/{name}.csv" for name in expected_tables),
        *(f"parquet/{name}.parquet" for name in expected_tables),
        "morocco_elections_v14.duckdb", "README.txt", "LICENSE_DATA.md", "ATTRIBUTIONS.md",
        "CITATION.cff", "queries.sql",
    }
    if {item.get("path") for item in files} != expected_paths:
        errors.append("inventaire des fichiers V14 incohérent")
    controls = manifest.get("controls", {})
    for key, expected in EXPECTED_CONTROLS.items():
        if controls.get(key) != expected:
            errors.append(f"contrôle V14 inattendu: {key}")
    payloads = manifest.get("source_payloads", [])
    if len(payloads) != EXPECTED_CONTROLS["unique_source_payloads"]:
        errors.append("nombre de fichiers sources V14 incohérent")
    elif (
        len({item.get("source_id") for item in payloads}) != len(payloads)
        or len({item.get("sha256") for item in payloads}) != len(payloads)
        or any(
            not isinstance(item.get("byte_size"), int)
            or item["byte_size"] <= 0
            or not isinstance(item.get("sha256"), str)
            or len(item["sha256"]) != 64
            or not item.get("source_family_id")
            for item in payloads
        )
    ):
        errors.append("provenance des fichiers sources V14 incohérente")
    return errors


def build_distribution(
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    manifest_output: str | Path | None = None,
    readme_output: str | Path | None = None,
) -> dict[str, Any]:
    paths = get_paths(data_dir)
    destination = Path(output_dir) if output_dir else paths.data_root / "exports" / "open" / "v14"
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "csv").mkdir(exist_ok=True)
    (destination / "parquet").mkdir(exist_ok=True)

    tmp_parent = paths.data_root / "tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v14_base_", dir=tmp_parent) as temporary:
        temp = Path(temporary)
        base_manifest = open_v13.build_distribution(
            data_dir,
            temp / "base",
            temp / "manifest.json",
            temp / "README.txt",
        )
        tables: dict[str, list[dict[str, Any]]] = {}
        keys: dict[str, list[str]] = {}
        source_sheets: dict[str, str] = {}
        for contract in base_manifest["tables"]:
            table_name = contract["table_name"]
            if table_name == "fact_parliamentary_activity":
                continue
            table = pq.read_table(temp / "base" / "parquet" / f"{table_name}.parquet")
            tables[table_name] = table.to_pylist()
            keys[table_name] = contract["primary_key"]
            source_sheets[table_name] = contract["source_sheet"]

    inventory_source_records = load_source_records()
    acquired_occurrences, acquired_source_records = load_acquired_questions(data_dir)
    workbook = openpyxl.load_workbook(paths.v13_workbook, read_only=True, data_only=True)
    _, mandates = rows_from_sheet(workbook["PARLIAMENTARY_MANDATES"])
    _, baseline_questions = rows_from_sheet(workbook["PARLIAMENTARY_QUESTIONS"])
    _, workbook_sources = rows_from_sheet(workbook["SOURCES"])
    workbook.close()
    baseline_occurrences, baseline_source_records = _load_v13_question_occurrences(
        baseline_questions, workbook_sources
    )
    occurrences = [*acquired_occurrences, *baseline_occurrences]
    source_records = [*acquired_source_records, *baseline_source_records]
    model = _public_model(build_longitudinal_model(occurrences, mandates, source_records))
    controls = _build_controls(
        occurrences,
        model,
        source_records,
        [*inventory_source_records, *baseline_source_records],
        baseline_occurrences,
    )
    for table_name, rows in model.items():
        tables[table_name] = rows
        keys[table_name] = NEW_TABLE_KEYS[table_name]
        source_sheets[table_name] = "V14_LONGITUDINAL_PARLIAMENT"

    relationships = _manifest_relationships(base_manifest)
    for table_name, rows in tables.items():
        open_v13._validate_primary_key(table_name, rows, keys[table_name])
        if len(rows) != (EXPECTED_NEW_ROWS.get(table_name) or len(rows)):
            raise RuntimeError(f"volume inattendu: {table_name}")
    _validate_foreign_keys(tables, relationships)

    allowed = {
        *(destination / "csv" / f"{name}.csv" for name in tables),
        *(destination / "parquet" / f"{name}.parquet" for name in tables),
        destination / "morocco_elections_v14.duckdb", destination / "README.txt",
        destination / "LICENSE_DATA.md", destination / "ATTRIBUTIONS.md", destination / "CITATION.cff",
        destination / "queries.sql", destination / "manifest.json",
        destination / "checksums.sha256",
    }
    unexpected = [path for path in destination.rglob("*") if path.is_file() and path not in allowed]
    if unexpected:
        raise RuntimeError(f"fichiers inattendus dans le paquet V14: {unexpected}")

    table_contracts: list[dict[str, Any]] = []
    for table_name, rows in tables.items():
        headers = list(rows[0]) if rows else []
        table = open_v13.rows_to_arrow(headers, rows)
        open_v13._write_table(
            table,
            destination / "csv" / f"{table_name}.csv",
            destination / "parquet" / f"{table_name}.parquet",
        )
        table_contracts.append(
            {
                "table_name": table_name,
                "source_sheet": source_sheets[table_name],
                "rows": table.num_rows,
                "columns": [
                    {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                    for field in table.schema
                ],
                "primary_key": keys[table_name],
            }
        )

    database_path = destination / "morocco_elections_v14.duckdb"
    temporary_database = database_path.with_suffix(".duckdb.tmp")
    temporary_database.unlink(missing_ok=True)
    connection = duckdb.connect(str(temporary_database))
    try:
        for table_name in tables:
            parquet_path = (destination / "parquet" / f"{table_name}.parquet").as_posix().replace("'", "''")
            connection.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM read_parquet(\'{parquet_path}\')')
        connection.execute(
            "CREATE TABLE warehouse_metadata AS SELECT ? AS release, ? AS generated_on, ? AS baseline_release",
            [VERSION, GENERATED_ON, "V13"],
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    temporary_database.replace(database_path)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "release": VERSION,
        "baseline_release": "V13",
        "generated_on": GENERATED_ON,
        "publication_status": "PUBLIC_BETA",
        "published_on": GENERATED_ON,
        "scope_status": "PARTIAL_PUBLISHED_RESOURCES",
        "baseline_workbook_sha256": sha256_file(paths.v13_workbook),
        "scope": "Warehouse ouvert V13 et questions parlementaires écrites/orales publiées entre 2017 et 2024.",
        "controls": controls,
        "tables": table_contracts,
        "relationships": [
            {
                "child_table": child, "child_column": child_column,
                "parent_table": parent, "parent_column": parent_column, "nullable": nullable,
            }
            for child, child_column, parent, parent_column, nullable in relationships
        ],
        "source_payloads": [
            {
                "source_id": row["source_id"],
                "source_family_id": row["source_family_id"],
                "sha256": row["sha256"],
                "byte_size": row["byte_size"],
            }
            for row in model["dim_parliamentary_source"]
        ],
        "files": [],
        "license_rule": "ODbL 1.0 pour les droits détenus par le projet; contenus tiers régis source par source.",
    }
    readme = render_readme(manifest)
    open_v13._write_atomic(destination / "README.txt", readme.encode("utf-8"))
    open_v13._write_atomic(destination / "LICENSE_DATA.md", DATA_LICENSE.read_bytes())
    open_v13._write_atomic(destination / "ATTRIBUTIONS.md", ATTRIBUTIONS.read_bytes())
    open_v13._write_atomic(destination / "CITATION.cff", CITATION.read_bytes())
    open_v13._write_atomic(destination / "queries.sql", REFERENCE_QUERIES.read_bytes())
    data_files = [
        *(destination / "csv" / f"{name}.csv" for name in tables),
        *(destination / "parquet" / f"{name}.parquet" for name in tables),
        database_path, destination / "README.txt", destination / "LICENSE_DATA.md",
        destination / "ATTRIBUTIONS.md", destination / "CITATION.cff", destination / "queries.sql",
    ]
    logical_digest = hashlib.sha256()
    for table_name in tables:
        logical_digest.update(
            f"{table_name}:{sha256_file(destination / 'parquet' / f'{table_name}.parquet')}\n".encode("ascii")
        )
    for path in data_files:
        item: dict[str, Any] = {"path": path.relative_to(destination).as_posix()}
        if path == database_path:
            item.update(
                {"binary_reproducible": False, "byte_size_reproducible": False, "content_sha256": logical_digest.hexdigest()}
            )
        else:
            item.update({"byte_size": path.stat().st_size, "sha256": sha256_file(path)})
        manifest["files"].append(item)
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("manifeste V14 invalide: " + "; ".join(errors))
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    open_v13._write_atomic(destination / "manifest.json", manifest_bytes)
    checksummed = [*data_files, destination / "manifest.json"]
    open_v13._write_atomic(
        destination / "checksums.sha256",
        "".join(
            f"{sha256_file(path)}  {path.relative_to(destination).as_posix()}\n"
            for path in checksummed
        ).encode("utf-8"),
    )
    tracked_manifest = Path(manifest_output) if manifest_output else DEFAULT_MANIFEST
    tracked_readme = Path(readme_output) if readme_output else DEFAULT_README
    tracked_manifest.parent.mkdir(parents=True, exist_ok=True)
    tracked_readme.parent.mkdir(parents=True, exist_ok=True)
    open_v13._write_atomic(tracked_manifest, manifest_bytes)
    open_v13._write_atomic(tracked_readme, readme.encode("utf-8"))
    return manifest


def run(
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    manifest_output: str | Path | None = None,
    readme_output: str | Path | None = None,
) -> int:
    manifest = build_distribution(data_dir, output_dir, manifest_output, readme_output)
    print(
        f"V14_OPEN_EXPORT_OK tables={len(manifest['tables'])} "
        f"rows={sum(table['rows'] for table in manifest['tables'])}"
    )
    return 0
