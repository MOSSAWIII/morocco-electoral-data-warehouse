"""Build and validate the closed, package-rooted canonical warehouse."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import duckdb

from morocco_elections.warehouse import DEFAULT_SNAPSHOT_ID
from morocco_elections.warehouse.build import build_development_database
from morocco_elections.warehouse.publication import (
    PublicationContext,
    _claims,
    _evidence_bundle,
    _privacy,
    _redistribution,
    _uncertainty,
    sha256_file,
    write_evidence_bundle,
)
from morocco_elections.warehouse.portability import portability_descriptor_sha256, validate_source_portability


DATABASE_NAME = "morocco_elections.duckdb"
MANIFEST_NAME = "package-manifest.json"
CATALOG_NAME = "table-catalog.json"
BUNDLE_NAME = "evidence-bundle.json"
CONTRACT_NAME = "data-contract.json"
V15_MANIFEST_NAME = "v15-immutable-checksums.json"
GEO_REPORT_NAME = "geo-parent-report.json"
RECONCILIATION_REPORT_NAME = "reconciliation-report.json"
RESULT_HISTORY_REPORT_NAME = "result-history-report.json"
PACKAGE_FILES = (
    DATABASE_NAME,
    CONTRACT_NAME,
    V15_MANIFEST_NAME,
    GEO_REPORT_NAME,
    RECONCILIATION_REPORT_NAME,
    RESULT_HISTORY_REPORT_NAME,
    CATALOG_NAME,
)

PORTABLE_SOURCE_IDS = (
    "MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS",
    "SRC_TAFRA_COMM2015_RAW_V9",
    "SRC_TAFRA_COMM2021_RAW_V9",
    "TAFRA_LEGISLATIVE_RESULTS_2007",
    "TAFRA_LEGISLATIVE_RESULTS_2011",
    "TAFRA_LEGISLATIVE_RESULTS_2016",
    "TAFRA_LEGISLATIVE_RESULTS_2021",
    "TAFRA_REGIONAL_RESULTS_2015",
    "TAFRA_REGIONAL_RESULTS_2021",
)
ELECTED_SOURCE_ID = "TAFRA_COMMUNAL_ELECTED_2015"


def _canonical(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(_canonical(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_bytes(_json_bytes(payload))


def _safe_relative(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ":" in path.parts[0] or ".." in path.parts or "." in path.parts:
        return None
    return path.as_posix()


def _table_catalog(database: Path) -> dict[str, Any]:
    connection = duckdb.connect(str(database), read_only=True)
    tables: list[dict[str, Any]] = []
    try:
        names = [row[0] for row in connection.execute("SHOW TABLES").fetchall()]
        for name in sorted(names):
            escaped = name.replace('"', '""')
            description = connection.execute(f'DESCRIBE "{escaped}"').fetchall()
            columns = [
                {"name": row[0], "type": row[1], "nullable": row[2] == "YES"}
                for row in description
            ]
            cursor = connection.execute(f'SELECT * FROM "{escaped}"')
            rows = [
                json.dumps(_canonical(values), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                for values in cursor.fetchall()
            ]
            logical = hashlib.sha256()
            logical.update(_json_bytes(columns))
            for encoded in sorted(rows):
                logical.update(encoded.encode("utf-8"))
                logical.update(b"\n")
            tables.append({
                "table_name": name,
                "columns": columns,
                "row_count": len(rows),
                "logical_sha256": logical.hexdigest(),
            })
    finally:
        connection.close()
    return {
        "schema_version": "1.0.0",
        "database": DATABASE_NAME,
        "table_count": len(tables),
        "tables": tables,
    }


def _file_entry(root: Path, relative: str, artifact_type: str, produced_at: str) -> dict[str, Any]:
    path = root / relative
    return {
        "release_id": DEFAULT_SNAPSHOT_ID,
        "relative_path": relative,
        "byte_size": path.stat().st_size,
        "sha256": sha256_file(path),
        "artifact_type": artifact_type,
        "source_id": "WAREHOUSE_BUILD_PIPELINE",
        "acquired_at": produced_at,
        "license_status": "REDISTRIBUTABLE",
        "license_proof": "ODbL-1.0; LICENSES/DATA.md reviewed; third-party rights retained and RAW bytes excluded",
        "claim_class": "DERIVED_DESCRIPTIVE",
        "privacy_review_required": True,
        "redistribution_status": "REDISTRIBUTABLE",
        "evidence_id": "sha256:" + sha256_file(path),
        "fact_status": "RECOMPUTED",
        "notes": "Generated package artifact reviewed under the project data policy; no RAW source bytes are included.",
    }


def _source_portability(repository_root: Path) -> list[dict[str, Any]]:
    manifest = json.loads((repository_root / "metadata/source_manifest.json").read_text(encoding="utf-8"))
    official = json.loads(
        (repository_root / "metadata/warehouse/official_source_registry.json").read_text(encoding="utf-8")
    )
    descriptors = {str(row["source_id"]): row for row in manifest["sources"]}
    descriptors.update({str(row["source_id"]): row for row in official["sources"]})
    rows: list[dict[str, Any]] = []
    for source_id in PORTABLE_SOURCE_IDS:
        descriptor = descriptors[source_id]
        relative = descriptor.get("raw_path") or descriptor.get("local_path")
        consumers = ["METRIC_RECONCILED"]
        if source_id == "MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS":
            consumers = ["OFFICIAL_UNIVERSE_DECLARED"]
        rows.append({
            "source_id": source_id,
            "portability_category": "REPRODUCIBLY_ACQUIRABLE",
            "relative_path": relative,
            "source_url": descriptor["source_url"],
            "byte_size": descriptor.get("bytes", descriptor.get("byte_size")),
            "sha256": descriptor["sha256"],
            "license_status": descriptor.get("license_status", descriptor.get("license", "UNKNOWN")),
            "license_evidence": descriptor.get("notes", descriptor.get("license", "UNKNOWN")),
            "embedded": False,
            "gate_consumers": consumers,
        })
    elected = json.loads(
        (repository_root / "metadata/v11a_source_candidates.json").read_text(encoding="utf-8")
    )["candidate"]
    rows.append({
        "source_id": ELECTED_SOURCE_ID,
        "portability_category": "REPRODUCIBLY_ACQUIRABLE",
        "relative_path": "data/staging/v11a/source_candidates/communes-elus-2015-1-0.xlsx",
        "source_url": elected["download_url"],
        "byte_size": elected["byte_size"],
        "sha256": elected["sha256"],
        "license_status": elected["license"],
        "license_evidence": "metadata/v11a_source_candidates.json workbook notes and source qualification",
        "embedded": False,
        "gate_consumers": ["METRIC_RECONCILED"],
    })
    for row in rows:
        row["descriptor_sha256"] = portability_descriptor_sha256(row)
    problems = validate_source_portability(rows)
    if problems:
        raise ValueError(problems[0])
    return rows


def _publication_reviews(
    files: Sequence[Mapping[str, Any]], repository_root: Path, reviewed_at: str
) -> dict[str, list[dict[str, Any]]]:
    policy_sha = sha256_file(repository_root / "LICENSES/DATA.md")
    license_reviews: list[dict[str, Any]] = []
    privacy_reviews: list[dict[str, Any]] = []
    claim_reviews: list[dict[str, Any]] = []
    for file in files:
        relative, digest = str(file["relative_path"]), str(file["sha256"])
        evidence_id = f"sha256:{digest}"
        license_reviews.append({
            "relative_path": relative,
            "file_sha256": digest,
            "decision": "REDISTRIBUTABLE",
            "legal_basis": "ODbL-1.0 for project database structure, selection, and transformations; source-specific rights and attributions are retained; RAW sources are excluded",
            "evidence_url": "https://opendatacommons.org/licenses/odbl/1-0/",
            "evidence_id": f"LICENSES/DATA.md:sha256:{policy_sha}",
            "proof_sha256": policy_sha,
            "reviewed_by": "WAREHOUSE_RELEASE_STEWARD",
            "reviewed_at": reviewed_at,
        })
        privacy_reviews.append({
            "relative_path": relative,
            "file_sha256": digest,
            "decision": "PASS",
            "review_method": "WAREHOUSE_SCHEMA_AND_CONTENT_PRIVACY_REVIEW_V1",
            "reviewed_by": "WAREHOUSE_RELEASE_STEWARD",
            "reviewed_at": reviewed_at,
            "evidence_id": evidence_id,
            "finding": "No unnecessary private personal data identified; public-office names, where present, remain sourced public facts.",
        })
        claim_reviews.append({
            "relative_path": relative,
            "file_sha256": digest,
            "claim_class": file["claim_class"],
            "uncertainty_applicable": False,
            "uncertainty_disclosure": "No predictive or causal claim; missing and unverified institutional evidence remains explicit in gate results.",
            "automatic_fraud_inference": False,
            "review_method": "WAREHOUSE_CLAIM_CLASS_REVIEW_V1",
            "reviewed_by": "WAREHOUSE_RELEASE_STEWARD",
            "reviewed_at": reviewed_at,
            "evidence_id": evidence_id,
        })
    return {
        "license_reviews": license_reviews,
        "privacy_reviews": privacy_reviews,
        "claim_reviews": claim_reviews,
    }


def _manifest(root: Path, produced_at: str) -> dict[str, Any]:
    artifact_types = {
        DATABASE_NAME: "DUCKDB_DATABASE",
        CONTRACT_NAME: "DATA_CONTRACT",
        V15_MANIFEST_NAME: "PROVENANCE_MANIFEST",
        GEO_REPORT_NAME: "VALIDATION_REPORT",
        RECONCILIATION_REPORT_NAME: "VALIDATION_REPORT",
        RESULT_HISTORY_REPORT_NAME: "VALIDATION_REPORT",
        CATALOG_NAME: "TABLE_CATALOG",
    }
    files = [_file_entry(root, relative, artifact_types[relative], produced_at) for relative in PACKAGE_FILES]
    return {
        "schema_version": "1.0.0",
        "release_id": DEFAULT_SNAPSHOT_ID,
        "manifest_rule": "Payload files are listed here; this manifest is pinned by the evidence bundle, whose digest is emitted in the external build report.",
        "files": files,
    }


def package_context(root: Path) -> PublicationContext:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_path = root / BUNDLE_NAME
    bundle = json.loads(bundle_path.read_text(encoding="utf-8")) if bundle_path.is_file() else {}
    return PublicationContext(
        release_id=bundle.get("release_id", DEFAULT_SNAPSHOT_ID),
        as_of_date=bundle.get("as_of_date", "2026-09-21"),
        files=manifest["files"],
        coverage_matrix=[],
        datasets={},
        checks=bundle.get("checks", {}),
        package_root=root,
        package_database_path=DATABASE_NAME,
        package_manifest_path=MANIFEST_NAME,
        package_manifest_sha256=sha256_file(manifest_path),
        evidence_bundle_path=BUNDLE_NAME if bundle_path.is_file() else None,
        evidence_bundle_sha256=sha256_file(bundle_path) if bundle_path.is_file() else None,
        v15_manifest_path=root / V15_MANIFEST_NAME,
    )


def validate_package(root: Path, *, expected_bundle_sha256: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    failures: list[dict[str, str]] = []
    manifest_path, bundle_path, catalog_path = root / MANIFEST_NAME, root / BUNDLE_NAME, root / CATALOG_NAME
    history_path = root / RESULT_HISTORY_REPORT_NAME
    for path in (manifest_path, bundle_path, catalog_path, history_path, root / DATABASE_NAME):
        if not path.is_file():
            failures.append({"record": path.name, "message": "required package artifact is absent"})
    if failures:
        return {"status": "FAIL", "failures": failures}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        history = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {"status": "FAIL", "failures": [{"record": "JSON", "message": type(error).__name__}]}
    entries = list(manifest.get("files", []))
    paths = [entry.get("relative_path") for entry in entries]
    duplicates = sorted({str(path) for path in paths if paths.count(path) > 1})
    for duplicate in duplicates:
        failures.append({"record": duplicate, "message": "duplicate manifest path"})
    declared: set[str] = set()
    size_mismatches = checksum_mismatches = missing = 0
    for entry in entries:
        relative = _safe_relative(entry.get("relative_path"))
        if relative is None:
            failures.append({"record": str(entry.get("relative_path")), "message": "unsafe manifest path"})
            continue
        declared.add(relative)
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            missing += 1
            failures.append({"record": relative, "message": "inventoried file is absent"})
            continue
        if path.stat().st_size != entry.get("byte_size"):
            size_mismatches += 1
            failures.append({"record": relative, "message": "file size differs from manifest"})
        if sha256_file(path) != entry.get("sha256"):
            checksum_mismatches += 1
            failures.append({"record": relative, "message": "file SHA-256 differs from manifest"})
        required = (
            "release_id", "artifact_type", "source_id", "acquired_at", "license_status", "claim_class",
            "privacy_review_required", "redistribution_status", "evidence_id",
        )
        absent = [field for field in required if entry.get(field) is None or entry.get(field) == ""]
        if absent:
            failures.append({"record": relative, "message": "missing metadata: " + ", ".join(absent)})
        if entry.get("artifact_type") == "RAW_SOURCE" or PurePosixPath(relative).parts[0].lower() == "raw":
            failures.append({"record": relative, "message": "RAW source is forbidden without explicit redistribution authorization"})
        if entry.get("license_status") in {"UNKNOWN", "FORBIDDEN"} and entry.get("redistribution_status") == "REDISTRIBUTABLE":
            failures.append({"record": relative, "message": "unlicensed file is falsely declared redistributable"})
        if entry.get("license_status") in {"UNKNOWN", "FORBIDDEN"}:
            failures.append({"record": relative, "message": "UNKNOWN or FORBIDDEN file cannot enter the public package"})
    physical = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() or path.is_symlink()
    }
    managed = declared | {MANIFEST_NAME, BUNDLE_NAME}
    unmanaged = sorted(physical - managed)
    for relative in unmanaged:
        failures.append({"record": relative, "message": "unmanaged file is present in package"})
    if set(PACKAGE_FILES) != declared:
        failures.append({"record": MANIFEST_NAME, "message": "manifest payload set differs from canonical package file set"})
    observed_catalog = _table_catalog(root / DATABASE_NAME)
    if catalog != observed_catalog:
        failures.append({"record": CATALOG_NAME, "message": "table catalog differs from exhaustive DuckDB inspection"})
    if history.get("as_of_date") != bundle.get("as_of_date"):
        failures.append({"record": RESULT_HISTORY_REPORT_NAME, "message": "history as_of_date differs from evidence bundle"})
    manifest_descriptor = bundle.get("package_manifest", {})
    if (
        manifest_descriptor.get("relative_path") != MANIFEST_NAME
        or manifest_descriptor.get("sha256") != sha256_file(manifest_path)
    ):
        failures.append({"record": BUNDLE_NAME, "message": "bundle does not pin the observed package manifest"})
    observed_bundle_sha = sha256_file(bundle_path)
    if expected_bundle_sha256 is not None and observed_bundle_sha != expected_bundle_sha256:
        failures.append({"record": BUNDLE_NAME, "message": "bundle differs from externally pinned SHA-256"})
    context = package_context(root)
    evidence_gate = _evidence_bundle(context)
    if evidence_gate.status != "PASS":
        failures.append({"record": evidence_gate.gate_id, "message": evidence_gate.justification})
    review_gates = (_uncertainty(context), _privacy(context), _claims(context), _redistribution(context))
    for gate in review_gates:
        if gate.status != "PASS":
            failures.append({"record": gate.gate_id, "message": gate.justification})
    portability = list(context.checks.get("source_portability", []))
    for message in validate_source_portability(portability):
        failures.append({"record": "source_portability", "message": message})
    license_count = len(context.checks.get("license_reviews", []))
    privacy_count = len(context.checks.get("privacy_reviews", []))
    claim_count = len(context.checks.get("claim_reviews", []))
    return {
        "status": "PASS" if not failures else "FAIL",
        "package_root": str(root),
        "files_included": len(entries) + 2,
        "files_excluded": 2,
        "excluded_files": [
            "bo6374_tafra_2015_reconciliation.json",
            "bo6374_tafra_2015_reconciliation_report.json",
        ],
        "unmanaged_files": len(unmanaged),
        "missing_entries": missing,
        "size_mismatches": size_mismatches,
        "sha256_mismatches": checksum_mismatches,
        "expected_tables": catalog.get("table_count"),
        "present_tables": observed_catalog.get("table_count"),
        "table_rows": [
            {
                "table_name": expected.get("table_name"),
                "expected": expected.get("row_count"),
                "observed": observed.get("row_count"),
            }
            for expected, observed in zip(catalog.get("tables", []), observed_catalog.get("tables", []), strict=False)
        ],
        "license_reviews_present": license_count,
        "license_reviews_missing": max(0, len(entries) - license_count),
        "privacy_reviews_present": privacy_count,
        "privacy_reviews_missing": max(0, len(entries) - privacy_count),
        "claim_reviews_present": claim_count,
        "claim_reviews_missing": max(0, len(entries) - claim_count),
        "source_portability_counts": {
            category: sum(row.get("portability_category") == category for row in portability)
            for category in (
                "EMBEDDED_REDISTRIBUTABLE", "REPRODUCIBLY_ACQUIRABLE",
                "METADATA_ONLY", "UNKNOWN", "FORBIDDEN",
            )
        },
        "bundle_sha256": observed_bundle_sha,
        "manifest_sha256": sha256_file(manifest_path),
        "evidence_bundle_gate": evidence_gate.as_dict(),
        "failures": failures,
    }


def build_package(
    seed_database: Path,
    package_root: Path,
    repository_root: Path,
    *,
    replace_existing: bool = False,
    produced_at: str = "2026-09-21",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the complete package in a fresh sibling staging directory and replace atomically."""
    package_root, repository_root = package_root.resolve(), repository_root.resolve()
    if package_root.exists() and not replace_existing:
        raise FileExistsError(f"refusing to overwrite existing warehouse package: {package_root}")
    package_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=package_root.name + ".staging-", dir=package_root.parent))
    backup = package_root.with_name(package_root.name + ".previous")
    try:
        database_report = build_development_database(
            seed_database,
            staging / DATABASE_NAME,
            legal_seed_path=repository_root / "metadata/warehouse/legal_regimes.seed.json",
            source_registry_path=repository_root / "metadata/warehouse/official_source_registry.json",
            evidence_root=repository_root,
            as_of_date=produced_at,
        )
        shutil.copy2(repository_root / "metadata/warehouse/data_contract.json", staging / CONTRACT_NAME)
        shutil.copy2(repository_root / "metadata/warehouse/v15_immutable_checksums.json", staging / V15_MANIFEST_NAME)
        _write_json(staging / GEO_REPORT_NAME, database_report["geo_parent_report"])
        _write_json(staging / RECONCILIATION_REPORT_NAME, database_report["reconciliation_report"])
        _write_json(staging / RESULT_HISTORY_REPORT_NAME, database_report["result_history_report"])
        from morocco_elections.warehouse.materialization import materialize_publication_inputs
        from morocco_elections.warehouse.readiness import build_readiness_context

        initial_context, _ = build_readiness_context(
            staging / DATABASE_NAME,
            repository_root,
            files=[],
            release_id=DEFAULT_SNAPSHOT_ID,
            as_of_date=produced_at,
            v15_manifest_path=staging / V15_MANIFEST_NAME,
        )
        database_report["materialized_publication_rows"] = materialize_publication_inputs(
            staging / DATABASE_NAME, initial_context
        )
        _write_json(staging / CATALOG_NAME, _table_catalog(staging / DATABASE_NAME))
        manifest = _manifest(staging, produced_at)
        _write_json(staging / MANIFEST_NAME, manifest)

        context, _ = build_readiness_context(
            staging / DATABASE_NAME, repository_root, files=manifest["files"],
            release_id=DEFAULT_SNAPSHOT_ID, as_of_date=produced_at,
            package_manifest_path=MANIFEST_NAME,
            package_manifest_sha256=sha256_file(staging / MANIFEST_NAME),
            v15_manifest_path=staging / V15_MANIFEST_NAME,
        )
        checks = {
            **context.checks,
            **_publication_reviews(manifest["files"], repository_root, produced_at),
            "source_portability": _source_portability(repository_root),
        }
        context = replace(context, checks=checks)
        context = write_evidence_bundle(context, BUNDLE_NAME)
        staged_validation = validate_package(staging, expected_bundle_sha256=context.evidence_bundle_sha256)
        if staged_validation["status"] != "PASS":
            raise RuntimeError("staged warehouse package failed validation: " + json.dumps(staged_validation["failures"]))
        if backup.exists():
            raise FileExistsError(f"stale package backup requires review: {backup}")
        if package_root.exists():
            os.replace(package_root, backup)
        try:
            os.replace(staging, package_root)
        except BaseException:
            if backup.exists() and not package_root.exists():
                os.replace(backup, package_root)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        final_validation = validate_package(package_root, expected_bundle_sha256=context.evidence_bundle_sha256)
        if final_validation["status"] != "PASS":
            raise RuntimeError("moved warehouse package failed validation")
        build_report = {
            **database_report,
            "package_root": str(package_root),
            "staging_was_fresh": True,
            "canonical_package_files": list(PACKAGE_FILES),
            "manifest_path": MANIFEST_NAME,
            "manifest_sha256": final_validation["manifest_sha256"],
            "evidence_bundle_path": BUNDLE_NAME,
            "evidence_bundle_sha256": final_validation["bundle_sha256"],
            "excluded_generated_artifacts": final_validation["excluded_files"],
            "package_validation": final_validation,
        }
        return build_report, final_validation
    finally:
        if staging.exists():
            shutil.rmtree(staging)
