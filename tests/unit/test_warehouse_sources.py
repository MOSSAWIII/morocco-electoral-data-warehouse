from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from morocco_elections.warehouse.sources import _download_pinned, materialize_declared_sources, materialize_seed_database


def test_pinned_download_can_use_verified_content_addressed_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"cached official bytes"
    digest = hashlib.sha256(payload).hexdigest()
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / digest).write_bytes(payload)
    monkeypatch.setenv("MOROCCO_ELECTIONS_SOURCE_CACHE", str(cache))
    target = tmp_path / "download.bin"

    _download_pinned("https://unreachable.invalid/source", target, len(payload), digest)

    assert target.read_bytes() == payload


def test_declared_sources_are_acquired_once_and_verified(tmp_path: Path) -> None:
    origin = tmp_path / "origin.bin"
    origin.write_bytes(b"official bytes")
    digest = hashlib.sha256(origin.read_bytes()).hexdigest()
    metadata = tmp_path / "metadata/warehouse"
    metadata.mkdir(parents=True)
    (metadata / "official_source_registry.json").write_text(json.dumps({"sources": [{
        "source_id": "S1", "source_url": origin.as_uri(), "raw_path": "data/raw/source.bin",
        "bytes": origin.stat().st_size, "sha256": digest,
    }]}), encoding="utf-8")

    assert materialize_declared_sources(tmp_path) == {"declared": 1, "acquired": 1, "reused": 0, "metadata_only": 0}
    assert materialize_declared_sources(tmp_path) == {"declared": 1, "acquired": 0, "reused": 1, "metadata_only": 0}
    (tmp_path / "data/raw/source.bin").write_bytes(b"mutated")
    assert materialize_declared_sources(tmp_path) == {"declared": 1, "acquired": 1, "reused": 0, "metadata_only": 0}


def test_declared_source_mismatch_fails_closed(tmp_path: Path) -> None:
    origin = tmp_path / "origin.bin"
    origin.write_bytes(b"wrong")
    metadata = tmp_path / "metadata/warehouse"
    metadata.mkdir(parents=True)
    (metadata / "official_source_registry.json").write_text(json.dumps({"sources": [{
        "source_id": "S1", "source_url": origin.as_uri(), "raw_path": "data/raw/source.bin",
        "bytes": 5, "sha256": "0" * 64,
    }]}), encoding="utf-8")

    with pytest.raises(ValueError, match="differ from pinned evidence"):
        materialize_declared_sources(tmp_path)


def test_seed_database_is_extracted_from_pinned_snapshot(tmp_path: Path) -> None:
    archive = tmp_path / "snapshot.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("snapshot/warehouse.duckdb", b"duckdb bytes")
    metadata = tmp_path / "metadata/warehouse"
    metadata.mkdir(parents=True)
    (metadata / "seed_snapshot.json").write_text(json.dumps({
        "download_url": archive.as_uri(), "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "database_member": "snapshot/warehouse.duckdb",
    }), encoding="utf-8")
    destination = tmp_path / "data/seed.duckdb"

    assert materialize_seed_database(tmp_path, destination) == destination.resolve()
    assert destination.read_bytes() == b"duckdb bytes"
