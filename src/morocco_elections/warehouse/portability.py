from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping, Sequence


PORTABILITY_CATEGORIES = {
    "EMBEDDED_REDISTRIBUTABLE",
    "REPRODUCIBLY_ACQUIRABLE",
    "METADATA_ONLY",
    "UNKNOWN",
    "FORBIDDEN",
}


def portability_descriptor_sha256(row: Mapping[str, Any]) -> str:
    fields = {
        key: row.get(key)
        for key in (
            "source_id", "portability_category", "relative_path", "source_url",
            "byte_size", "sha256", "license_status", "embedded", "gate_consumers",
        )
    }
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class SourceEvidenceError(ValueError):
    """Raised when portable source bytes cannot be resolved exactly as declared."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ":" in path.parts[0] or "." in path.parts or ".." in path.parts:
        return None
    return path.as_posix()


def validate_source_portability(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    by_id: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        source_id = str(row.get("source_id", "<unknown>"))
        by_id.setdefault(source_id, []).append(row)
        category = row.get("portability_category")
        if category not in PORTABILITY_CATEGORIES:
            failures.append(f"{source_id}: exactly one recognized portability category is required")
        if _safe_relative(row.get("relative_path")) is None:
            failures.append(f"{source_id}: source evidence path must be package-independent and relative")
        size = row.get("byte_size")
        digest = row.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            failures.append(f"{source_id}: pinned byte_size is invalid")
        if not isinstance(digest, str) or len(digest) != 64:
            failures.append(f"{source_id}: pinned SHA-256 is invalid")
        if category == "REPRODUCIBLY_ACQUIRABLE" and not str(row.get("source_url", "")).startswith(
            ("https://", "http://")
        ):
            failures.append(f"{source_id}: reproducible acquisition requires an HTTP(S) URL")
        if category == "EMBEDDED_REDISTRIBUTABLE" and row.get("license_status") in {
            None,
            "UNKNOWN",
            "FORBIDDEN",
            "METADATA_ONLY",
        }:
            failures.append(f"{source_id}: embedded bytes lack a redistribution license")
        if row.get("descriptor_sha256") != portability_descriptor_sha256(row):
            failures.append(f"{source_id}: portability descriptor URL, SHA-256, or metadata was modified")
    for source_id, matches in by_id.items():
        if len(matches) != 1:
            failures.append(f"{source_id}: source must have exactly one portability record")
    return failures


def _verified_local(root: Path, row: Mapping[str, Any]) -> Path | None:
    relative = _safe_relative(row.get("relative_path"))
    if relative is None:
        return None
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    if resolved_root not in path.parents or not path.is_file():
        return None
    if path.stat().st_size != row.get("byte_size") or _sha256(path) != row.get("sha256"):
        return None
    return path


def _download(row: Mapping[str, Any], destination: Path) -> None:
    source_id = str(row["source_id"])
    request = urllib.request.Request(str(row["source_url"]), headers={"User-Agent": "morocco-elections-warehouse/1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    except (OSError, urllib.error.URLError) as error:
        raise SourceEvidenceError(
            f"{source_id}: reproducible acquisition is unavailable ({type(error).__name__})"
        ) from error
    if destination.stat().st_size != row.get("byte_size") or _sha256(destination) != row.get("sha256"):
        raise SourceEvidenceError(f"{source_id}: acquired bytes differ from the pinned size or SHA-256")


@contextmanager
def portable_evidence_root(
    rows: Sequence[Mapping[str, Any]],
    source_ids: set[str],
    *,
    package_root: Path | None,
    repository_root: Path | None,
) -> Iterator[Path]:
    """Resolve exact source bytes locally or by pinned acquisition, never by an absolute declaration."""
    failures = validate_source_portability(rows)
    if failures:
        raise SourceEvidenceError(failures[0])
    by_id = {str(row["source_id"]): row for row in rows}
    missing = sorted(source_ids - set(by_id))
    if missing:
        raise SourceEvidenceError(f"{missing[0]}: source lacks a portability record")

    selected = [by_id[source_id] for source_id in sorted(source_ids)]
    if repository_root is not None and all(_verified_local(repository_root, row) for row in selected):
        yield repository_root.resolve()
        return

    with tempfile.TemporaryDirectory(prefix="warehouse-source-evidence-") as temporary:
        root = Path(temporary)
        descriptors: list[dict[str, Any]] = []
        for row in selected:
            source_id = str(row["source_id"])
            category = str(row["portability_category"])
            relative = str(row["relative_path"])
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if category == "EMBEDDED_REDISTRIBUTABLE":
                if package_root is None:
                    raise SourceEvidenceError(f"{source_id}: embedded source has no package root")
                source = _verified_local(package_root, row)
                if source is None:
                    raise SourceEvidenceError(f"{source_id}: embedded source bytes are absent or modified")
                shutil.copy2(source, destination)
            elif category == "REPRODUCIBLY_ACQUIRABLE":
                _download(row, destination)
            else:
                raise SourceEvidenceError(
                    f"{source_id}: required bytes are unavailable under portability category {category}"
                )
            descriptors.append({
                "source_id": source_id,
                "local_path": relative,
                "source_url": row.get("source_url"),
                "sha256": row.get("sha256"),
                "byte_size": row.get("byte_size"),
            })
        metadata = root / "metadata/warehouse"
        metadata.mkdir(parents=True, exist_ok=True)
        (metadata / "source_registry.json").write_text(
            json.dumps({"sources": [
                {
                    "source_id": row["source_id"],
                    "aliases": [],
                    "source_url": row["source_url"],
                    "raw_path": row["local_path"],
                    "bytes": row["byte_size"],
                    "sha256": row["sha256"],
                }
                for row in descriptors
            ]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        yield root
