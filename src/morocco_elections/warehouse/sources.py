"""Reproducibly materialize already-declared, byte-pinned source evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_declared_sources(repository_root: Path) -> dict[str, int]:
    """Download missing registered bytes and reject every size or digest mismatch."""
    repository_root = repository_root.resolve()
    registry_path = repository_root / "metadata/warehouse/official_source_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    acquired = reused = metadata_only = 0
    for row in registry["sources"]:
        if not row.get("raw_path"):
            metadata_only += 1
            continue
        relative = Path(str(row["raw_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe source path: {relative}")
        target = (repository_root / relative).resolve()
        if repository_root not in target.parents:
            raise ValueError(f"source escapes repository: {relative}")
        expected_bytes, expected_sha = int(row["bytes"]), str(row["sha256"])
        if target.is_file() and target.stat().st_size == expected_bytes and _sha256(target) == expected_sha:
            reused += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            request = urllib.request.Request(str(row["source_url"]), headers={"User-Agent": "morocco-elections-warehouse/1"})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            if temporary.stat().st_size != expected_bytes or _sha256(temporary) != expected_sha:
                raise ValueError(f"{row['source_id']}: acquired bytes differ from pinned evidence")
            os.replace(temporary, target)
            acquired += 1
        finally:
            temporary.unlink(missing_ok=True)
    return {
        "declared": len(registry["sources"]), "acquired": acquired,
        "reused": reused, "metadata_only": metadata_only,
    }


def materialize_seed_database(repository_root: Path, destination: Path) -> Path:
    """Extract only the pinned DuckDB seed from its immutable snapshot archive."""
    repository_root, destination = repository_root.resolve(), destination.resolve()
    descriptor = json.loads(
        (repository_root / "metadata/warehouse/seed_snapshot.json").read_text(encoding="utf-8")
    )
    if destination.is_file():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="warehouse-seed-", dir=destination.parent) as temporary_name:
        temporary_root = Path(temporary_name)
        archive = temporary_root / "snapshot.zip"
        request = urllib.request.Request(str(descriptor["download_url"]), headers={"User-Agent": "morocco-elections-warehouse/1"})
        with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        if archive.stat().st_size != int(descriptor["bytes"]) or _sha256(archive) != descriptor["sha256"]:
            raise ValueError("seed snapshot archive differs from pinned evidence")
        member = str(descriptor["database_member"])
        if member.startswith(("/", "\\")) or ".." in Path(member).parts:
            raise ValueError("unsafe seed database member")
        with zipfile.ZipFile(archive) as bundle:
            info = bundle.getinfo(member)
            temporary_database = temporary_root / "seed.duckdb"
            with bundle.open(info) as source, temporary_database.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
        os.replace(temporary_database, destination)
    return destination
