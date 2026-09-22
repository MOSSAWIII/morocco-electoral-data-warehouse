from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from morocco_elections.config import PROJECT_ROOT
from morocco_elections.v16.validation import ValidationIssue


MANIFEST_PATH = PROJECT_ROOT / "metadata" / "v16" / "v15_immutable_checksums.json"
PUBLICATION_PATH = PROJECT_ROOT / "metadata" / "v15_publication.json"
CANONICAL_MANIFEST_BYTES = 4034
CANONICAL_MANIFEST_SHA256 = "f5558c09cdb4257b62e760563c0ac57d1d670f74ade798bd0a6f1ad14b17fec9"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("release") != "V15" or manifest.get("release_version") != "15.0.0":
        raise RuntimeError("invalid immutable V15 manifest")
    return manifest


def verify_v15_immutability(root: Path = PROJECT_ROOT, manifest_path: Path = MANIFEST_PATH) -> list[ValidationIssue]:
    issues = []
    for row in load_manifest(manifest_path)["files"]:
        relative = row["path"]
        path = (root / relative).resolve()
        if root.resolve() not in path.parents:
            issues.append(ValidationIssue("UNSAFE_IMMUTABLE_PATH", "v15_manifest", relative, "path escapes project root"))
        elif not path.is_file():
            issues.append(ValidationIssue("V15_ARTIFACT_MISSING", "v15_manifest", relative, "pinned artifact is absent"))
        elif not isinstance(row.get("bytes"), int) or path.stat().st_size != row["bytes"]:
            issues.append(ValidationIssue("V15_ARTIFACT_SIZE_CHANGED", "v15_manifest", relative, "V15.0.0 byte length differs from manifest"))
        elif sha256_file(path) != row["sha256"]:
            issues.append(ValidationIssue("V15_ARTIFACT_CHANGED", "v15_manifest", relative, "V15.0.0 is immutable; publish a distinct version"))
    return issues


def verify_v15_publication_asset(
    asset_dir: Path = PROJECT_ROOT / "data" / "exports" / "open" / "releases",
    publication_path: Path = PUBLICATION_PATH,
) -> list[ValidationIssue]:
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    path = asset_dir / publication["asset_name"]
    if not path.is_file():
        return [ValidationIssue("V15_PUBLIC_ASSET_MISSING", "v15_publication", publication["asset_name"], "pinned public release asset is absent")]
    issues = []
    if path.stat().st_size != publication["bytes"]:
        issues.append(ValidationIssue("V15_PUBLIC_ASSET_SIZE_CHANGED", "v15_publication", publication["asset_name"], "asset byte length differs"))
    if sha256_file(path) != publication["sha256"]:
        issues.append(ValidationIssue("V15_PUBLIC_ASSET_CHECKSUM_CHANGED", "v15_publication", publication["asset_name"], "asset SHA-256 differs"))
    return issues
