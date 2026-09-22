from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from morocco_elections.warehouse.sources import materialize_declared_sources


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
