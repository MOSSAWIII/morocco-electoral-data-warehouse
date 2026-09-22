from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import duckdb
import pytest

from morocco_elections.provenance import sha256_file
from morocco_elections.quality.v15.accuracy import validate_accuracy
from morocco_elections.quality.v15.package import validate_package


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(os.environ.get("V15_TEST_PACKAGE", ROOT / "data/exports/open/v15"))
pytestmark = pytest.mark.skipif(not (PACKAGE / "manifest.json").is_file(), reason="paquet V15 construit requis")


@pytest.fixture
def package(tmp_path: Path) -> Path:
    destination = tmp_path / "v15"
    shutil.copytree(PACKAGE, destination)
    return destination


def _refresh_integrity(package: Path, relative: str) -> None:
    target = package / relative
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(row for row in manifest["files"] if row["path"] == relative)
    record.update(bytes=target.stat().st_size, sha256=sha256_file(target))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
    checksums = package / "checksums.sha256"
    entries = dict(line.split("  ", 1)[::-1] for line in checksums.read_text(encoding="ascii").splitlines())
    entries[relative] = sha256_file(target)
    entries["manifest.json"] = sha256_file(manifest_path)
    checksums.write_text(
        "".join(f"{entries[name]}  {name}\n" for name in sorted(entries)), encoding="ascii", newline=""
    )


@pytest.mark.parametrize("kind", ["csv", "parquet"])
def test_validator_rejects_missing_table_format(package: Path, kind: str) -> None:
    (package / kind / f"dim_party.{kind}").unlink()
    assert any("absent" in error or "incomplet" in error for error in validate_package(package))


def test_validator_rejects_cross_format_single_value_divergence(package: Path) -> None:
    target = package / "csv" / "dim_party.csv"
    content = target.read_text(encoding="utf-8")
    lines = content.splitlines()
    fields = lines[1].split(",")
    fields[1] = '"MUTATED_PARTY_NAME"'
    lines[1] = ",".join(fields)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    _refresh_integrity(package, "csv/dim_party.csv")
    assert any("contenu logique divergent" in error for error in validate_package(package))


def test_validator_rejects_extra_csv_column(package: Path) -> None:
    target = package / "csv" / "dim_party.csv"
    lines = target.read_text(encoding="utf-8").splitlines()
    lines[0] += ",unexpected_column"
    lines[1:] = [line + ",unexpected" for line in lines[1:]]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    _refresh_integrity(package, "csv/dim_party.csv")
    assert any("en-tête CSV différent" in error for error in validate_package(package))


def test_validator_rejects_malformed_checksum(package: Path) -> None:
    checksum = package / "checksums.sha256"
    checksum.write_text("not-a-checksum\n", encoding="ascii")
    assert any("mal formée" in error for error in validate_package(package))


def test_validator_rejects_checksum_path_traversal(package: Path) -> None:
    checksum = package / "checksums.sha256"
    checksum.write_text(f"{'0' * 64}  ../escape\n", encoding="ascii")
    assert any("non sûr" in error for error in validate_package(package))


def test_validator_rejects_manifest_path_traversal(package: Path) -> None:
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = "../escape"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert any("chemin de manifeste non sûr" in error for error in validate_package(package))


def test_accuracy_validator_rejects_planned_observation(package: Path) -> None:
    database = package / "morocco_elections_v15.duckdb"
    connection = duckdb.connect(str(database))
    indicator = connection.execute(
        "SELECT indicator_id FROM fact_observation ORDER BY indicator_id LIMIT 1"
    ).fetchone()[0]
    connection.execute("UPDATE dim_indicator SET collection_status='not_started' WHERE indicator_id=?", [indicator])
    connection.close()
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert any("planifiée" in error for error in validate_accuracy(package, manifest))
