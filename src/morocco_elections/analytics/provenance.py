from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_identity(source: Path) -> tuple[str | None, str | None]:
    manifest = source.parent / "package-manifest.json"
    if not manifest.is_file():
        return None, None
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    release_id = payload.get("release_id")
    return (str(release_id) if release_id is not None else None), sha256(manifest)
