from __future__ import annotations

import hashlib
import json
import copy
import zipfile
from pathlib import Path

import pytest

from morocco_elections.warehouse.sources import (
    _download_pinned,
    materialize_declared_sources,
    materialize_seed_database,
    source_registry_issues,
)


ROOT = Path(__file__).resolve().parents[2]


def test_canonical_source_registry_is_unique_and_descriptor_pinned() -> None:
    payload = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    assert source_registry_issues(payload) == []
    assert payload["source_count"] == len(payload["sources"]) == 86
    assert len({row["source_id"] for row in payload["sources"]}) == 86
    assert sum(row["acquisition_status"] == "ACQUIRED_PINNED" for row in payload["sources"]) == 41
    hcp = next(
        row for row in payload["sources"]
        if row["source_id"] == "MA_HCP_RGPH2014_INDICATEURS_COMMUNAUX_INDIVIDUS"
    )
    assert "SRC_HCP_RGPH2014_INDIVIDUALS" in hcp["aliases"]
    assert not any(
        token in alias
        for row in payload["sources"] for alias in row["aliases"]
        for token in tuple(f"_V{number}" for number in range(9, 17))
    )


def test_canonical_source_registry_mutations_fail_closed() -> None:
    payload = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    mutated = copy.deepcopy(payload)
    mutated["sources"][0]["authority"] = "mutated"
    assert any("descriptor SHA-256 mismatch" in issue for issue in source_registry_issues(mutated))
    duplicate = copy.deepcopy(payload)
    duplicate["sources"][1]["sha256"] = duplicate["sources"][0]["sha256"]
    duplicate["sources"][1]["raw_path"] = duplicate["sources"][0]["raw_path"]
    duplicate["sources"][1]["bytes"] = duplicate["sources"][0]["bytes"]
    assert any("content duplicates" in issue for issue in source_registry_issues(duplicate))


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
    (metadata / "source_registry.json").write_text(json.dumps({"sources": [{
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
    (metadata / "source_registry.json").write_text(json.dumps({"sources": [{
        "source_id": "S1", "source_url": origin.as_uri(), "raw_path": "data/raw/source.bin",
        "bytes": 5, "sha256": "0" * 64,
    }]}), encoding="utf-8")

    with pytest.raises(ValueError, match="differ from pinned evidence"):
        materialize_declared_sources(tmp_path)


def test_seed_database_is_extracted_from_pinned_snapshot(tmp_path: Path) -> None:
    database_bytes = b"duckdb bytes"
    archive = tmp_path / "snapshot.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("snapshot/warehouse.duckdb", database_bytes)
    metadata = tmp_path / "metadata/warehouse"
    metadata.mkdir(parents=True)
    (metadata / "seed_snapshot.json").write_text(json.dumps({
        "download_url": archive.as_uri(), "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "database_member": "snapshot/warehouse.duckdb",
        "database_bytes": len(database_bytes),
        "database_sha256": hashlib.sha256(database_bytes).hexdigest(),
    }), encoding="utf-8")
    destination = tmp_path / "data/seed.duckdb"

    assert materialize_seed_database(tmp_path, destination) == destination.resolve()
    assert destination.read_bytes() == database_bytes

    destination.write_bytes(b"mutated local seed")
    assert materialize_seed_database(tmp_path, destination) == destination.resolve()
    assert destination.read_bytes() == database_bytes


@pytest.mark.parametrize("mutation", ["member_name", "member_size", "member_digest"])
def test_seed_database_member_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    expected = b"expected duckdb"
    member = "snapshot/warehouse.duckdb"
    archived_member = "snapshot/unexpected.duckdb" if mutation == "member_name" else member
    actual = b"altered duckdb" if mutation == "member_digest" else expected
    if mutation == "member_size":
        actual += b"!"
    archive = tmp_path / "snapshot.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(archived_member, actual)
    metadata = tmp_path / "metadata/warehouse"
    metadata.mkdir(parents=True)
    (metadata / "seed_snapshot.json").write_text(json.dumps({
        "download_url": archive.as_uri(), "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "database_member": member,
        "database_bytes": len(expected),
        "database_sha256": hashlib.sha256(expected).hexdigest(),
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="seed database member"):
        materialize_seed_database(tmp_path, tmp_path / "data/seed.duckdb")


def test_seed_database_rejects_unsafe_member_path(tmp_path: Path) -> None:
    archive = tmp_path / "snapshot.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("seed.duckdb", b"seed")
    metadata = tmp_path / "metadata/warehouse"
    metadata.mkdir(parents=True)
    (metadata / "seed_snapshot.json").write_text(json.dumps({
        "download_url": archive.as_uri(), "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "database_member": "../seed.duckdb", "database_bytes": 4,
        "database_sha256": hashlib.sha256(b"seed").hexdigest(),
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe seed database member"):
        materialize_seed_database(tmp_path, tmp_path / "data/seed.duckdb")
