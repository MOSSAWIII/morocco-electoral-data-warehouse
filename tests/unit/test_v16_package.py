from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import duckdb
import pytest

from morocco_elections.v16.package import (
    BUNDLE_NAME,
    CATALOG_NAME,
    CONTRACT_NAME,
    DATABASE_NAME,
    GEO_REPORT_NAME,
    MANIFEST_NAME,
    RECONCILIATION_REPORT_NAME,
    RESULT_HISTORY_REPORT_NAME,
    V15_MANIFEST_NAME,
    _manifest,
    _table_catalog,
    _write_json,
    validate_package,
)
from morocco_elections.v16.materialization import materialize_publication_inputs
from morocco_elections.v16.publication import PublicationContext, sha256_file, validate_publication, write_evidence_bundle
from morocco_elections.v16.schema import create_schema


def test_publication_inputs_are_materialized_in_duckdb(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(database))
    try:
        create_schema(connection)
    finally:
        connection.close()
    universe = {
        "universe_id": "U1", "election_id": "E1", "coverage_dimension": "TERRITORIAL",
        "universe_type": "OFFICIAL_TERRITORIES", "denominator": 1, "source_id": "S1",
        "source_url": "https://example.test/source", "acquired_at": "2026-09-21",
        "verification_status": "VERIFIED", "is_external": True,
        "member_extraction_method": "JSON_UNIVERSES_OBJECT",
    }
    matrix = {
        "release_id": "SNAPSHOT", "scope_id": "TERRITORIAL", "universe_ids_json": '["U1"]',
        "acquired": 1, "expected": 1, "covered": 1, "missing": 0, "non_comparable": 0,
        "redistribution_forbidden": 0, "status": "COMPLETE",
    }
    context = PublicationContext(
        release_id="SNAPSHOT", as_of_date="2026-09-21", files=[], coverage_matrix=[matrix],
        datasets={
            "coverage_universes": [universe],
            "coverage_universe_members": [{"universe_id": "U1", "expected_id": "G1", "source_id": "S1"}],
        }, checks={},
    )

    counts = materialize_publication_inputs(database, context)

    assert counts == {"coverage_universe": 1, "coverage_universe_member": 1, "release_coverage_matrix": 1}


def _make_package(root: Path) -> str:
    root.mkdir()
    connection = duckdb.connect(str(root / DATABASE_NAME))
    try:
        connection.execute("CREATE TABLE published (id INTEGER PRIMARY KEY, value VARCHAR)")
        connection.execute("INSERT INTO published VALUES (1, 'one')")
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    _write_json(root / CONTRACT_NAME, {"release": "V16"})
    _write_json(root / GEO_REPORT_NAME, {"remaining": 0})
    _write_json(root / RECONCILIATION_REPORT_NAME, {"missing": 0})
    _write_json(root / RESULT_HISTORY_REPORT_NAME, {
        "as_of_date": "2026-09-21", "inventory": [], "gaps": [], "diagnostic": {},
    })
    _write_json(root / V15_MANIFEST_NAME, {"release": "V15", "release_version": "15.0.0", "files": []})
    _write_json(root / CATALOG_NAME, _table_catalog(root / DATABASE_NAME))
    manifest = _manifest(root, "2026-09-21")
    _write_json(root / MANIFEST_NAME, manifest)
    license_reviews = []
    privacy_reviews = []
    claim_reviews = []
    for row in manifest["files"]:
        common = {"relative_path": row["relative_path"], "file_sha256": row["sha256"]}
        license_reviews.append({
            **common, "decision": "REDISTRIBUTABLE", "legal_basis": "ODbL-1.0",
            "evidence_url": "https://opendatacommons.org/licenses/odbl/1-0/",
            "evidence_id": "POLICY", "proof_sha256": "1" * 64,
            "reviewed_by": "reviewer", "reviewed_at": "2026-09-21",
        })
        privacy_reviews.append({
            **common, "decision": "PASS", "reviewed_by": "reviewer",
            "reviewed_at": "2026-09-21", "evidence_id": "SCAN",
        })
        claim_reviews.append({
            **common, "claim_class": row["claim_class"], "uncertainty_applicable": False,
            "reviewed_by": "reviewer", "reviewed_at": "2026-09-21", "evidence_id": "CLAIM",
        })
    context = PublicationContext(
        release_id="V16-DEVELOPMENT", as_of_date="2026-09-21", files=manifest["files"],
        coverage_matrix=[], datasets={"result_history_inventory": [], "result_history_gaps": []},
        checks={"license_reviews": license_reviews, "privacy_reviews": privacy_reviews, "claim_reviews": claim_reviews}, package_root=root,
        package_database_path=DATABASE_NAME, package_manifest_path=MANIFEST_NAME,
        package_manifest_sha256=sha256_file(root / MANIFEST_NAME),
        v15_manifest_path=root / V15_MANIFEST_NAME,
    )
    context = write_evidence_bundle(context, BUNDLE_NAME)
    assert context.evidence_bundle_sha256 is not None
    return context.evidence_bundle_sha256


@pytest.fixture()
def package(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "package"
    digest = _make_package(root)
    assert validate_package(root, expected_bundle_sha256=digest)["status"] == "PASS"
    return root, digest


def _manifest_payload(root: Path) -> dict:
    return json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))


def test_package_rejects_unmanaged_and_missing_files(package) -> None:
    root, digest = package
    (root / "unmanaged.txt").write_text("x", encoding="utf-8")
    report = validate_package(root, expected_bundle_sha256=digest)
    assert report["status"] == "FAIL"
    assert any("unmanaged file" in row["message"] for row in report["failures"])
    (root / "unmanaged.txt").unlink()
    (root / CONTRACT_NAME).unlink()
    report = validate_package(root, expected_bundle_sha256=digest)
    assert any("inventoried file is absent" in row["message"] for row in report["failures"])


def test_package_rejects_database_byte_size_and_checksum_mutations(package) -> None:
    root, digest = package
    with (root / DATABASE_NAME).open("ab") as stream:
        stream.write(b"x")
    report = validate_package(root, expected_bundle_sha256=digest)
    messages = {row["message"] for row in report["failures"]}
    assert "file size differs from manifest" in messages
    assert "file SHA-256 differs from manifest" in messages


def test_package_rejects_mutated_embedded_v15_manifest(package) -> None:
    root, digest = package
    with (root / V15_MANIFEST_NAME).open("ab") as stream:
        stream.write(b"\n")
    report = validate_package(root, expected_bundle_sha256=digest)
    assert report["status"] == "FAIL"
    failures = [row for row in report["failures"] if row["record"] == V15_MANIFEST_NAME]
    assert {row["message"] for row in failures} == {
        "file size differs from manifest", "file SHA-256 differs from manifest",
    }


@pytest.mark.parametrize("field,value", [("byte_size", 1), ("sha256", "0" * 64)])
def test_package_rejects_mutated_expected_size_or_hash(package, field: str, value) -> None:
    root, digest = package
    manifest = _manifest_payload(root)
    manifest["files"][0][field] = value
    _write_json(root / MANIFEST_NAME, manifest)
    report = validate_package(root, expected_bundle_sha256=digest)
    assert report["status"] == "FAIL"
    assert any(field.split("_")[0] in row["message"].lower() or "bundle" in row["record"] for row in report["failures"])


def test_package_rejects_duplicate_unsafe_and_omitted_manifest_paths(package) -> None:
    root, digest = package
    original = _manifest_payload(root)
    duplicate = copy.deepcopy(original)
    duplicate["files"].append(copy.deepcopy(duplicate["files"][0]))
    _write_json(root / MANIFEST_NAME, duplicate)
    assert any("duplicate manifest path" in row["message"] for row in validate_package(root)["failures"])
    for unsafe in ("C:/absolute.db", "../escape.db"):
        mutated = copy.deepcopy(original)
        mutated["files"][0]["relative_path"] = unsafe
        _write_json(root / MANIFEST_NAME, mutated)
        assert any("unsafe manifest path" in row["message"] for row in validate_package(root)["failures"])
    omitted = copy.deepcopy(original)
    omitted["files"].pop()
    _write_json(root / MANIFEST_NAME, omitted)
    report = validate_package(root, expected_bundle_sha256=digest)
    assert any("canonical package file set" in row["message"] for row in report["failures"])


def test_package_rejects_mutated_bundle_and_coordinated_manifest(package) -> None:
    root, digest = package
    bundle = json.loads((root / BUNDLE_NAME).read_text(encoding="utf-8"))
    bundle["release_id"] = "MUTATED"
    _write_json(root / BUNDLE_NAME, bundle)
    report = validate_package(root, expected_bundle_sha256=digest)
    assert any("bundle" in row["message"] for row in report["failures"])


def test_package_rejects_omitted_table_and_modified_row_count(package) -> None:
    root, _ = package
    catalog = json.loads((root / CATALOG_NAME).read_text(encoding="utf-8"))
    catalog["tables"].pop()
    catalog["table_count"] -= 1
    _write_json(root / CATALOG_NAME, catalog)
    assert any("table catalog differs" in row["message"] for row in validate_package(root)["failures"])
    _write_json(root / CATALOG_NAME, _table_catalog(root / DATABASE_NAME))
    connection = duckdb.connect(str(root / DATABASE_NAME))
    try:
        connection.execute("INSERT INTO published VALUES (2, 'two')")
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    assert any("table catalog differs" in row["message"] for row in validate_package(root)["failures"])


def test_package_rejects_coordinated_manifest_change_without_bundle_proof(package) -> None:
    root, digest = package
    (root / CONTRACT_NAME).write_text('{"release":"MUTATED"}\n', encoding="utf-8")
    manifest = _manifest_payload(root)
    entry = next(row for row in manifest["files"] if row["relative_path"] == CONTRACT_NAME)
    entry["byte_size"] = (root / CONTRACT_NAME).stat().st_size
    entry["sha256"] = sha256_file(root / CONTRACT_NAME)
    entry["evidence_id"] = "sha256:" + entry["sha256"]
    _write_json(root / MANIFEST_NAME, manifest)
    report = validate_package(root, expected_bundle_sha256=digest)
    assert any("bundle does not pin" in row["message"] or row["record"] == "EVIDENCE_BUNDLE_VERIFIED" for row in report["failures"])


@pytest.mark.parametrize("license_status", ["UNKNOWN", "FORBIDDEN"])
def test_package_rejects_raw_or_unlicensed_file_declared_redistributable(package, license_status: str) -> None:
    root, _ = package
    raw = root / "raw-source.bin"
    raw.write_bytes(b"raw")
    manifest = _manifest_payload(root)
    row = copy.deepcopy(manifest["files"][0])
    row.update({
        "relative_path": raw.name, "byte_size": 3, "sha256": sha256_file(raw),
        "evidence_id": "sha256:" + sha256_file(raw), "artifact_type": "RAW_SOURCE",
        "license_status": license_status, "redistribution_status": "REDISTRIBUTABLE",
    })
    manifest["files"].append(row)
    _write_json(root / MANIFEST_NAME, manifest)
    failures = validate_package(root)["failures"]
    assert any("RAW source" in item["message"] for item in failures)
    assert any("falsely declared redistributable" in item["message"] for item in failures)


def test_package_validation_is_location_independent_and_booleans_are_forbidden(package, tmp_path: Path) -> None:
    root, digest = package
    moved = tmp_path / "elsewhere" / "moved-package"
    moved.parent.mkdir()
    shutil.copytree(root, moved)
    assert validate_package(moved, expected_bundle_sha256=digest)["status"] == "PASS"
    with pytest.raises(TypeError, match="boolean gate maps are forbidden"):
        validate_publication({"EVIDENCE_BUNDLE_VERIFIED": True})  # type: ignore[arg-type]
