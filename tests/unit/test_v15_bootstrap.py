from __future__ import annotations

import json
import stat
import zipfile
from pathlib import Path

from morocco_elections.provenance import sha256_file
from morocco_elections.v15 import bootstrap


def _archive(path: Path, member: str = "morocco_elections_v15/manifest.json") -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(member, '{"release":"V15"}')
    return {"release": "V15", "asset_name": path.name, "download_url": path.as_uri(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _configure(monkeypatch, tmp_path: Path, publication: dict) -> None:
    path = tmp_path / "publication.json"
    path.write_text(json.dumps(publication), encoding="utf-8")
    monkeypatch.setattr(bootstrap, "PUBLICATION", path)


def test_existing_package_is_validated_before_success(monkeypatch, tmp_path: Path) -> None:
    destination = tmp_path / "exports/open/v15"
    destination.mkdir(parents=True)
    (destination / "manifest.json").write_text("{}", encoding="utf-8")
    called = []
    monkeypatch.setattr(bootstrap, "validate_package", lambda root: called.append(root) or [])
    assert bootstrap.run(tmp_path) == 0
    assert called == [destination]


def test_local_archive_is_verified_validated_and_installed(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "exports/open/releases/V15.zip"
    publication = _archive(archive)
    _configure(monkeypatch, tmp_path, publication)
    monkeypatch.setattr(bootstrap, "validate_package", lambda root: [])
    assert bootstrap.run(tmp_path) == 0
    assert (tmp_path / "exports/open/v15/manifest.json").is_file()


def test_network_only_download_path(monkeypatch, tmp_path: Path) -> None:
    remote = tmp_path / "remote.zip"
    publication = _archive(remote)
    publication["asset_name"] = "V15.zip"
    _configure(monkeypatch, tmp_path, publication)
    monkeypatch.setattr(bootstrap, "validate_package", lambda root: [])
    assert bootstrap.run(tmp_path, network_only=True) == 0


def test_bad_archive_hash_has_integrity_exit_code(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "exports/open/releases/V15.zip"
    publication = _archive(archive)
    publication["sha256"] = "0" * 64
    _configure(monkeypatch, tmp_path, publication)
    assert bootstrap.run(tmp_path) == bootstrap.EXIT_INTEGRITY


def test_missing_download_has_network_exit_code(monkeypatch, tmp_path: Path) -> None:
    publication = {
        "release": "V15", "asset_name": "V15.zip", "download_url": (tmp_path / "missing.zip").as_uri(),
        "bytes": 1, "sha256": "0" * 64,
    }
    _configure(monkeypatch, tmp_path, publication)
    assert bootstrap.run(tmp_path, network_only=True) == bootstrap.EXIT_NETWORK


def test_zip_path_traversal_has_archive_exit_code(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "exports/open/releases/V15.zip"
    publication = _archive(archive, "../escape")
    _configure(monkeypatch, tmp_path, publication)
    assert bootstrap.run(tmp_path) == bootstrap.EXIT_ARCHIVE


def test_dangerous_link_has_archive_exit_code(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "exports/open/releases/V15.zip"
    archive.parent.mkdir(parents=True)
    info = zipfile.ZipInfo("morocco_elections_v15/link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(info, "target")
    publication = {"release": "V15", "asset_name": archive.name, "download_url": archive.as_uri(), "bytes": archive.stat().st_size, "sha256": sha256_file(archive)}
    _configure(monkeypatch, tmp_path, publication)
    assert bootstrap.run(tmp_path) == bootstrap.EXIT_ARCHIVE


def test_oversized_archive_has_archive_exit_code(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "exports/open/releases/V15.zip"
    publication = _archive(archive)
    _configure(monkeypatch, tmp_path, publication)
    monkeypatch.setattr(bootstrap, "MAX_UNCOMPRESSED_BYTES", 1)
    assert bootstrap.run(tmp_path) == bootstrap.EXIT_ARCHIVE


def test_invalid_extracted_package_has_package_exit_code(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "exports/open/releases/V15.zip"
    publication = _archive(archive)
    _configure(monkeypatch, tmp_path, publication)
    monkeypatch.setattr(bootstrap, "validate_package", lambda root: ["mutation"])
    assert bootstrap.run(tmp_path) == bootstrap.EXIT_PACKAGE


def test_failed_replacement_preserves_existing_install(monkeypatch, tmp_path: Path) -> None:
    destination = tmp_path / "exports/open/v15"
    destination.mkdir(parents=True)
    marker = destination / "keep.txt"
    marker.write_text("last valid package", encoding="utf-8")
    archive = tmp_path / "exports/open/releases/V15.zip"
    publication = _archive(archive)
    publication["sha256"] = "0" * 64
    _configure(monkeypatch, tmp_path, publication)
    monkeypatch.setattr(bootstrap, "validate_package", lambda root: ["force replacement"])
    assert bootstrap.run(tmp_path) == bootstrap.EXIT_INTEGRITY
    assert marker.read_text(encoding="utf-8") == "last valid package"
