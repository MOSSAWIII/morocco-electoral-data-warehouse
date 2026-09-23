"""Reproducibly materialize already-declared, byte-pinned source evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


_HISTORICAL_SHADOW_IDS = {
    "SRC_HF_TAFRA_COMM2015_V6",
    "SRC_HF_TAFRA_COUNCIL2021_V6",
    "SRC_HF_TAFRA_MPS_V6",
}
_EQUIVALENT_SOURCE_IDS = {
    # The historical and institutional descriptors pin the exact same workbook.
    "SRC_HCP_RGPH2014_INDIVIDUALS": "MA_HCP_RGPH2014_INDICATEURS_COMMUNAUX_INDIVIDUS",
}
SOURCE_REGISTRY_PATH = Path("metadata/warehouse/source_registry.json")


def canonical_source_id(source_id: str) -> str:
    """Map legacy release-labelled source identities to stable functional names."""
    if source_id in _HISTORICAL_SHADOW_IDS:
        return re.sub(r"_V\d+$", "_HISTORICAL_SNAPSHOT", source_id)
    normalized = re.sub(r"_RAW_V\d+$", "", source_id)
    normalized = re.sub(r"_V\d+$", "", normalized)
    return _EQUIVALENT_SOURCE_IDS.get(normalized, normalized)


def load_source_registry(repository_root: Path) -> dict[str, Any]:
    """Load the one active registry for every source class."""
    return json.loads((repository_root / SOURCE_REGISTRY_PATH).read_text(encoding="utf-8"))


def source_registry_issues(payload: dict[str, Any]) -> list[str]:
    """Validate canonical identities, descriptor hashes, and acquisition state."""
    issues: list[str] = []
    source_ids: set[str] = set()
    identity_owners: dict[str, str] = {}
    content_hash_owners: dict[str, str] = {}
    required = {
        "source_id", "authority", "source_url", "grain", "license_status",
        "status", "usages", "acquisition_status", "descriptor_sha256",
    }
    for row in payload.get("sources", []):
        source_id = str(row.get("source_id", ""))
        if not source_id or source_id in source_ids:
            issues.append(f"duplicate or missing source_id: {source_id or '<missing>'}")
        source_ids.add(source_id)
        missing = sorted(field for field in required if row.get(field) in (None, "", []))
        if missing:
            issues.append(f"{source_id}: missing {', '.join(missing)}")
        identities = [source_id, *row.get("aliases", [])]
        for identity in identities:
            normalized = canonical_source_id(str(identity))
            owner = identity_owners.setdefault(normalized, source_id)
            if owner != source_id:
                issues.append(f"{identity}: canonical identity conflicts with {owner}")
        content = (row.get("raw_path"), row.get("bytes"), row.get("sha256"))
        pinned = all(value is not None and value != "" for value in content)
        if pinned != any(value is not None and value != "" for value in content):
            issues.append(f"{source_id}: content path, size, and SHA-256 must be atomic")
        expected_acquisition = "ACQUIRED_PINNED" if pinned else "NOT_ACQUIRED_METADATA_ONLY"
        if row.get("acquisition_status") != expected_acquisition:
            issues.append(f"{source_id}: acquisition status contradicts content evidence")
        if pinned and not row.get("acquired_at"):
            issues.append(f"{source_id}: pinned content lacks acquisition date")
        if pinned:
            digest = str(row["sha256"])
            owner = content_hash_owners.setdefault(digest, source_id)
            if owner != source_id:
                issues.append(f"{source_id}: content duplicates {owner} without alias resolution")
        descriptor = {key: value for key, value in row.items() if key != "descriptor_sha256"}
        observed = hashlib.sha256(
            json.dumps(descriptor, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()
        if row.get("descriptor_sha256") != observed:
            issues.append(f"{source_id}: descriptor SHA-256 mismatch")
    if payload.get("source_count") != len(source_ids):
        issues.append("source_count does not match unique canonical identities")
    return issues


def source_descriptors_by_id(repository_root: Path) -> dict[str, dict[str, Any]]:
    """Index canonical IDs and historical aliases to their canonical descriptor."""
    descriptors: dict[str, dict[str, Any]] = {}
    for row in load_source_registry(repository_root).get("sources", []):
        identities = [row.get("source_id"), *row.get("aliases", [])]
        for identity in identities:
            if identity:
                descriptors[canonical_source_id(str(identity))] = row
    return descriptors


def official_source_rows(repository_root: Path) -> list[dict[str, Any]]:
    """Return only entries explicitly qualified as institutional evidence."""
    return [
        row for row in load_source_registry(repository_root).get("sources", [])
        if "official_evidence" in row.get("usages", [])
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_pinned(url: str, temporary: Path, expected_bytes: int, expected_sha: str) -> None:
    """Download an immutable object, resuming official servers that close early."""
    cache_root = os.environ.get("MOROCCO_ELECTIONS_SOURCE_CACHE")
    if cache_root:
        cached = Path(cache_root).resolve() / expected_sha
        if cached.is_file() and cached.stat().st_size == expected_bytes and _sha256(cached) == expected_sha:
            shutil.copyfile(cached, temporary)
            return
    temporary.write_bytes(b"")
    last_error: BaseException | None = None
    for _ in range(8):
        offset = temporary.stat().st_size
        headers = {"User-Agent": "morocco-elections-warehouse/1"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                append = offset > 0 and response.status == 206
                if offset > 0 and not append:
                    offset = 0
                with temporary.open("ab" if append else "wb") as stream:
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            last_error = error
        observed_bytes = temporary.stat().st_size
        if observed_bytes == expected_bytes and _sha256(temporary) == expected_sha:
            return
        if observed_bytes > expected_bytes:
            temporary.write_bytes(b"")
    detail = f" after {type(last_error).__name__}" if last_error is not None else ""
    raise ValueError(f"acquired bytes differ from pinned evidence{detail}")


def _declared_downloads(repository_root: Path) -> tuple[list[dict[str, Any]], int]:
    registry = load_source_registry(repository_root)["sources"]
    rows = [
        {
            "source_id": canonical_source_id(row["source_id"]), "source_url": row["source_url"],
            "raw_path": row["raw_path"], "bytes": row["bytes"], "sha256": row["sha256"],
        }
        for row in registry
        if row.get("raw_path") and row.get("bytes") is not None and row.get("sha256")
    ]
    metadata_only = len(registry) - len(rows)
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        relative = str(row["raw_path"])
        existing = unique.get(relative)
        if existing is not None and (
            existing["bytes"] != row["bytes"] or existing["sha256"] != row["sha256"]
        ):
            raise ValueError(f"conflicting pinned descriptors for {relative}")
        unique[relative] = row
    return list(unique.values()), metadata_only


def materialize_declared_sources(repository_root: Path) -> dict[str, int]:
    """Download missing registered bytes and reject every size or digest mismatch."""
    repository_root = repository_root.resolve()
    declarations, metadata_only = _declared_downloads(repository_root)
    acquired = reused = 0
    for row in declarations:
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
            try:
                _download_pinned(str(row["source_url"]), temporary, expected_bytes, expected_sha)
            except ValueError as error:
                raise ValueError(f"{row['source_id']}: {error}") from error
            os.replace(temporary, target)
            acquired += 1
        finally:
            temporary.unlink(missing_ok=True)
    return {
        "declared": len(declarations) + metadata_only, "acquired": acquired,
        "reused": reused, "metadata_only": metadata_only,
    }


def materialize_seed_database(repository_root: Path, destination: Path) -> Path:
    """Return only a seed whose archive and extracted DuckDB match the descriptor."""
    repository_root, destination = repository_root.resolve(), destination.resolve()
    descriptor = json.loads(
        (repository_root / "metadata/warehouse/seed_snapshot.json").read_text(encoding="utf-8")
    )
    member = str(descriptor["database_member"])
    expected_database_bytes = int(descriptor["database_bytes"])
    expected_database_sha = str(descriptor["database_sha256"])
    if destination.is_file() and (
        destination.stat().st_size == expected_database_bytes
        and _sha256(destination) == expected_database_sha
    ):
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="warehouse-seed-", dir=destination.parent) as temporary_name:
        temporary_root = Path(temporary_name)
        archive = temporary_root / "snapshot.zip"
        try:
            _download_pinned(
                str(descriptor["download_url"]),
                archive,
                int(descriptor["bytes"]),
                str(descriptor["sha256"]),
            )
        except ValueError as error:
            raise ValueError("seed snapshot archive differs from pinned evidence") from error
        if member.startswith(("/", "\\")) or ".." in Path(member).parts:
            raise ValueError("unsafe seed database member")
        with zipfile.ZipFile(archive) as bundle:
            try:
                info = bundle.getinfo(member)
            except KeyError as error:
                raise ValueError("pinned seed database member is absent") from error
            if info.is_dir() or info.file_size != expected_database_bytes:
                raise ValueError("seed database member size differs from pinned evidence")
            temporary_database = temporary_root / "seed.duckdb"
            with bundle.open(info) as source, temporary_database.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
        if (
            temporary_database.stat().st_size != expected_database_bytes
            or _sha256(temporary_database) != expected_database_sha
        ):
            raise ValueError("seed database member differs from pinned evidence")
        os.replace(temporary_database, destination)
    return destination
