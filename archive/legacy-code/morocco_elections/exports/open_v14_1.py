from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.domains.parliament.analytical_validity import apply_analytical_validity
from morocco_elections.exports import open_v13, open_v14
from morocco_elections.provenance import sha256_file


VERSION = "V14.1"
GENERATED_ON = "2026-09-12"
DEFAULT_MANIFEST = PROJECT_ROOT / "metadata" / "v14_1_open_distribution.json"
DEFAULT_README = PROJECT_ROOT / "docs" / "publication" / "V14_1_OPEN_DATA_README.txt"
DATA_LICENSE = PROJECT_ROOT / "LICENSES" / "DATA.md"
ATTRIBUTIONS = PROJECT_ROOT / "ATTRIBUTIONS.md"
CITATION = PROJECT_ROOT / "CITATION.cff"
REFERENCE_QUERIES = PROJECT_ROOT / "examples" / "v14_1_reference_queries.sql"

NEW_KEYS = {
    "dim_legislature": ["legislature_id"],
    "dim_parliamentary_source_author": ["author_source_id"],
    "analytical_parliamentary_coverage": ["coverage_id"],
    "bridge_person_parliamentary_affiliation": ["affiliation_id"],
    "analytical_person_period_exposure": ["person_period_exposure_id"],
    "parliamentary_outlier_audit": ["outlier_audit_id"],
}
EXPECTED_ROWS = {
    "dim_legislature": 2,
    "dim_parliamentary_period": 30,
    "dim_parliamentary_source_author": 1_622,
    "analytical_parliamentary_coverage": 61,
    "bridge_person_parliamentary_affiliation": 1_654,
    "analytical_person_period_exposure": 23_424,
    "parliamentary_outlier_audit": 1,
    "fact_parliamentary_question": 65_748,
    "analytical_parliamentary_trajectory": 3_142,
}


def _keys(base_manifest: dict[str, Any], tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    result = {row["table_name"]: row["primary_key"] for row in base_manifest["tables"]}
    result.pop("dim_parliamentary_author")
    result.update(NEW_KEYS)
    return {name: result[name] for name in tables}


def _relationships(base_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    relationships = []
    for item in base_manifest["relationships"]:
        row = dict(item)
        if row["parent_table"] == "dim_parliamentary_author":
            row["parent_table"] = "dim_parliamentary_source_author"
            row["parent_column"] = "author_source_id"
        if row["child_table"] == "bridge_question_author" and row["child_column"] == "author_id":
            row["child_column"] = "author_source_id"
        relationships.append(row)
    relationships.extend(
        [
            {"child_table": "dim_parliamentary_period", "child_column": "legislature_id", "parent_table": "dim_legislature", "parent_column": "legislature_id", "nullable": False},
            {"child_table": "bridge_person_parliamentary_affiliation", "child_column": "mandate_id", "parent_table": "fact_parliamentary_mandate", "parent_column": "mandate_id", "nullable": False},
            {"child_table": "bridge_person_parliamentary_affiliation", "child_column": "person_id", "parent_table": "dim_person_public", "parent_column": "person_id", "nullable": False},
            {"child_table": "bridge_person_parliamentary_affiliation", "child_column": "party_id", "parent_table": "dim_party", "parent_column": "party_id", "nullable": True},
            {"child_table": "bridge_person_parliamentary_affiliation", "child_column": "group_id", "parent_table": "dim_parliamentary_group", "parent_column": "group_id", "nullable": True},
            {"child_table": "analytical_person_period_exposure", "child_column": "person_id", "parent_table": "dim_person_public", "parent_column": "person_id", "nullable": False},
            {"child_table": "analytical_person_period_exposure", "child_column": "period_id", "parent_table": "dim_parliamentary_period", "parent_column": "period_id", "nullable": False},
            {"child_table": "parliamentary_outlier_audit", "child_column": "author_source_id", "parent_table": "dim_parliamentary_source_author", "parent_column": "author_source_id", "nullable": False},
            {"child_table": "parliamentary_outlier_audit", "child_column": "person_id", "parent_table": "dim_person_public", "parent_column": "person_id", "nullable": False},
        ]
    )
    return relationships


def _validate_foreign_keys(tables: dict[str, list[dict[str, Any]]], relationships: list[dict[str, Any]]) -> None:
    for relation in relationships:
        parents = {row.get(relation["parent_column"]) for row in tables[relation["parent_table"]]}
        values = [row.get(relation["child_column"]) for row in tables[relation["child_table"]]]
        if not relation["nullable"] and any(value in (None, "") for value in values):
            raise RuntimeError(f"clé étrangère obligatoire vide: {relation['child_table']}.{relation['child_column']}")
        missing = {value for value in values if value not in (None, "") and value not in parents}
        if missing:
            raise RuntimeError(f"clés étrangères absentes: {relation['child_table']}.{relation['child_column']} ({len(missing)})")


def render_readme(manifest: dict[str, Any]) -> str:
    controls = manifest["controls"]
    return "\n".join(
        [
            "MOROCCO ELECTORAL DATA WAREHOUSE — PAQUET OUVERT V14.1",
            "",
            f"Généré le : {manifest['generated_on']}",
            "Baseline immuable : V14",
            "",
            "PORTÉE ANALYTIQUE",
            "",
            "V14.1 mesure le volume et le contenu des questions publiées dans les fichiers disponibles.",
            "Il ne mesure ni la performance globale d'un député, ni le taux réel de réponse gouvernementale,",
            "ni l'activité exhaustive du Parlement marocain.",
            "",
            "CORRECTIONS",
            "",
            "- Les métriques portent désormais le préfixe published_ lorsqu'elles décrivent le corpus publié.",
            "- author_source_id représente un libellé source; person_id reste une personne canonique raccordée.",
            "- Les périodes incluent la législature et les bornes observées du corpus, jamais présentées comme",
            "  dates officielles de session.",
            "- La couverture reste UNKNOWN faute de dénominateur officiel de fichiers ou de questions attendus.",
            "- La spine d'exposition inclut les personnes mandatées sans question observée dans une fenêtre couverte.",
            "- Le parti d'une question est attribué seulement lorsqu'un intervalle de mandat couvre deposit_date.",
            "",
            "LIMITES NON MASQUÉES",
            "",
            "- observed_through_date reste NULL : retrieved_at ne prouve pas la date réelle de censure.",
            "- Les fins officielles des sessions ne sont pas déduites des seules dates de questions.",
            "- La correspondance historique groupe-mandat n'est pas démontrée; aucun member-day de groupe n'est publié.",
            "- Les coauteurs ne sont pas séparés sans convention source explicite.",
            "- Les réponses textuelles, statuts riches, ministres, majorité/opposition, Chambre des conseillers,",
            "  votes, commissions et impacts exigent de nouvelles sources et ne reçoivent aucune table vide.",
            "",
            "CONTRÔLES",
            "",
            f"Questions publiées dédupliquées : {controls['published_question_count']}",
            f"Questions avec date de réponse publiée : {controls['published_response_date_count']}",
            f"Cellules d'exposition personne × période × type : {controls['person_period_exposure_rows']}",
            f"Cellules de couverture documentaire : {controls['coverage_rows']}",
            "",
        ]
    )


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1 or manifest.get("release") != VERSION:
        errors.append("racine V14.1 invalide")
    tables = {row.get("table_name"): row for row in manifest.get("tables", [])}
    if len(tables) != 31:
        errors.append("31 tables attendues")
    for name, count in EXPECTED_ROWS.items():
        if tables.get(name, {}).get("rows") != count:
            errors.append(f"volume inattendu: {name}")
    forbidden_columns = {"question_count", "answered_question_count", "response_rate_pct", "author_id"}
    exposed = {column["name"] for table in tables.values() for column in table.get("columns", [])}
    if exposed & forbidden_columns:
        errors.append("anciens noms analytiquement ambigus encore exposés")
    if manifest.get("coverage_interpretation") != "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR":
        errors.append("règle de couverture absente")
    if manifest.get("deferred_source_dependent_work") is None:
        errors.append("travaux dépendant de sources non déclarés")
    if not str(manifest.get("public_name_policy", "")).startswith("PSEUDONYMIZED"):
        errors.append("politique de publication des noms absente")
    return errors


def build_distribution(
    data_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    manifest_output: str | Path | None = None,
    readme_output: str | Path | None = None,
) -> dict[str, Any]:
    paths = get_paths(data_dir)
    destination = Path(output_dir or paths.data_root / "exports" / "open" / "v14.1").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "csv").mkdir(exist_ok=True)
    (destination / "parquet").mkdir(exist_ok=True)
    tmp_parent = paths.data_root / "tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v14_1_base_", dir=tmp_parent) as temporary:
        temp = Path(temporary)
        base_manifest = open_v14.build_distribution(
            data_dir, temp / "base", temp / "manifest.json", temp / "README.txt"
        )
        base_tables = {
            row["table_name"]: pq.read_table(
                temp / "base" / "parquet" / f"{row['table_name']}.parquet"
            ).to_pylist()
            for row in base_manifest["tables"]
        }
    tables = apply_analytical_validity(base_tables)
    keys = _keys(base_manifest, tables)
    relationships = _relationships(base_manifest)
    for name, rows in tables.items():
        open_v13._validate_primary_key(name, rows, keys[name])
    _validate_foreign_keys(tables, relationships)

    contracts = []
    for name, rows in tables.items():
        arrow = open_v13.rows_to_arrow(list(rows[0]) if rows else [], rows)
        open_v13._write_table(arrow, destination / "csv" / f"{name}.csv", destination / "parquet" / f"{name}.parquet")
        contracts.append({
            "table_name": name, "source_sheet": "V14_1_ANALYTICAL_VALIDITY",
            "rows": arrow.num_rows,
            "columns": [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in arrow.schema],
            "primary_key": keys[name],
        })

    database_path = destination / "morocco_elections_v14_1.duckdb"
    temporary_database = database_path.with_suffix(".duckdb.tmp")
    temporary_database.unlink(missing_ok=True)
    connection = duckdb.connect(str(temporary_database))
    try:
        for name in tables:
            parquet_path = (destination / "parquet" / f"{name}.parquet").as_posix().replace("'", "''")
            connection.execute(f'CREATE TABLE "{name}" AS SELECT * FROM read_parquet(\'{parquet_path}\')')
        connection.execute("CREATE TABLE warehouse_metadata AS SELECT ? AS release, ? AS generated_on, ? AS baseline_release", [VERSION, GENERATED_ON, "V14"])
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    temporary_database.replace(database_path)

    controls = {
        "published_question_count": len(tables["fact_parliamentary_question"]),
        "published_response_date_count": len(tables["fact_parliamentary_response"]),
        "person_period_exposure_rows": len(tables["analytical_person_period_exposure"]),
        "person_period_zero_question_rows": sum(row["published_question_count"] == 0 for row in tables["analytical_person_period_exposure"]),
        "coverage_rows": len(tables["analytical_parliamentary_coverage"]),
        "coverage_complete_rows": 0,
        "outlier_review_status": tables["parliamentary_outlier_audit"][0]["outlier_review_status"],
    }
    manifest: dict[str, Any] = {
        "schema_version": 1, "release": VERSION, "baseline_release": "V14",
        "generated_on": GENERATED_ON, "publication_status": "PUBLIC_BETA",
        "scope_status": "PARTIAL_PUBLISHED_RESOURCES",
        "scope": "Correction de validité analytique du corpus public V14, sans nouvelle donnée source.",
        "coverage_interpretation": "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR",
        "public_name_policy": "PSEUDONYMIZED_SOURCE_AUTHORS; REPRODUCIBLE_LINKS_REQUIRE_OFFICIAL_SOURCE_ACCESS",
        "controls": controls, "tables": contracts, "relationships": relationships,
        "source_payloads": base_manifest["source_payloads"],
        "deferred_source_dependent_work": [
            "official_corpus_exhaustiveness", "response_text_and_lifecycle", "official_session_closures",
            "dynamic_group_membership", "majority_opposition", "ministers", "house_of_councillors",
            "votes_committees_amendments_proposals", "question_effects", "group_member_days",
        ],
        "files": [],
    }
    readme = render_readme(manifest)
    assets = {
        "README.txt": readme.encode("utf-8"), "LICENSE_DATA.md": DATA_LICENSE.read_bytes(),
        "ATTRIBUTIONS.md": ATTRIBUTIONS.read_bytes(), "CITATION.cff": CITATION.read_bytes(),
        "queries.sql": REFERENCE_QUERIES.read_bytes(),
    }
    for name, payload in assets.items():
        open_v13._write_atomic(destination / name, payload)
    data_files = [
        *(destination / "csv" / f"{name}.csv" for name in tables),
        *(destination / "parquet" / f"{name}.parquet" for name in tables),
        database_path, *(destination / name for name in assets),
    ]
    logical_digest = hashlib.sha256()
    for name in tables:
        logical_digest.update(f"{name}:{sha256_file(destination / 'parquet' / f'{name}.parquet')}\n".encode("ascii"))
    for path in data_files:
        item: dict[str, Any] = {"path": path.relative_to(destination).as_posix()}
        if path == database_path:
            item.update({"binary_reproducible": False, "byte_size_reproducible": False, "content_sha256": logical_digest.hexdigest()})
        else:
            item.update({"byte_size": path.stat().st_size, "sha256": sha256_file(path)})
        manifest["files"].append(item)
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("manifeste V14.1 invalide: " + "; ".join(errors))
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    open_v13._write_atomic(destination / "manifest.json", manifest_bytes)
    open_v13._write_atomic(
        destination / "checksums.sha256",
        "".join(f"{sha256_file(path)}  {path.relative_to(destination).as_posix()}\n" for path in [*data_files, destination / "manifest.json"]).encode("utf-8"),
    )
    tracked_manifest = Path(manifest_output or DEFAULT_MANIFEST)
    tracked_readme = Path(readme_output or DEFAULT_README)
    tracked_manifest.parent.mkdir(parents=True, exist_ok=True)
    tracked_readme.parent.mkdir(parents=True, exist_ok=True)
    open_v13._write_atomic(tracked_manifest, manifest_bytes)
    open_v13._write_atomic(tracked_readme, readme.encode("utf-8"))
    return manifest


def run(**kwargs: Any) -> int:
    manifest = build_distribution(**kwargs)
    print(f"V14_1_OPEN_EXPORT_OK tables={len(manifest['tables'])} rows={sum(row['rows'] for row in manifest['tables'])}")
    return 0
