from __future__ import annotations

import json
import re
from pathlib import Path

from morocco_elections.config import get_paths
from morocco_elections.provenance import sha256_file
from morocco_elections.quality.v15.accuracy import validate_accuracy
from morocco_elections.quality.v15.relationships import validate_relationships
from morocco_elections.quality.v15.schema import validate_schema


REQUIRED_ASSETS = {
    "README.md", "DATA_DICTIONARY.md", "LICENSE_DATA.md", "LICENSE_DOCUMENTATION.md",
    "ATTRIBUTIONS.md", "CITATION.cff", "queries.sql", "manifest.json", "checksums.sha256",
    "coverage_matrix.json", "morocco_elections_v15.duckdb",
}


def _safe_relative(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "\\" not in value


def _safe_file(root: Path, relative: str) -> Path | None:
    path = root / relative
    try:
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            return None
    except OSError:
        return None
    return path


def validate_package(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return [f"paquet: manifeste absent: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"paquet: manifeste illisible: {exc}"]
    if (
        manifest.get("release") != "V15"
        or manifest.get("release_version") != "15.0.0"
        or manifest.get("schema_version") != 1
    ):
        errors.append("paquet: racine de manifeste V15 invalide")
    missing_assets = sorted(name for name in REQUIRED_ASSETS if not (root / name).is_file())
    if missing_assets:
        errors.append("paquet: fichiers obligatoires absents: " + ", ".join(missing_assets))

    announced: set[str] = set()
    for row in manifest.get("files", []):
        relative = row.get("path")
        if not isinstance(relative, str) or not _safe_relative(relative):
            errors.append(f"paquet: chemin de manifeste non sûr: {relative!r}")
            continue
        announced.add(relative)
        path = _safe_file(root, relative)
        if path is None:
            errors.append(f"paquet: cible de manifeste non sûre: {relative!r}")
        elif not path.is_file():
            errors.append(f"paquet: fichier annoncé absent: {relative}")
        elif path.stat().st_size != row.get("bytes") or sha256_file(path) != row.get("sha256"):
            errors.append(f"paquet: empreinte invalide: {relative}")
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "checksums.sha256"}
    }
    if announced != actual:
        errors.append("paquet: manifeste de fichiers incomplet ou surnuméraire")

    checksum_path = root / "checksums.sha256"
    if checksum_path.is_file():
        checksum_entries: set[str] = set()
        try:
            lines = checksum_path.read_text(encoding="ascii").splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append(f"paquet: checksums illisibles: {exc}")
            lines = []
        for number, line in enumerate(lines, start=1):
            if not re.fullmatch(r"[0-9a-f]{64}  .+", line):
                errors.append(f"paquet: ligne de checksum mal formée: {number}")
                continue
            digest, relative = line.split("  ", 1)
            if not _safe_relative(relative):
                errors.append(f"paquet: chemin de checksum non sûr: {relative!r}")
                continue
            checksum_entries.add(relative)
            path = _safe_file(root, relative)
            if path is None or not path.is_file() or sha256_file(path) != digest:
                errors.append(f"paquet: checksum SHA-256 invalide: {relative}")
        if checksum_entries != announced | {"manifest.json"}:
            errors.append("paquet: index de checksums incomplet ou surnuméraire")

    if not errors:
        errors.extend(validate_schema(root, manifest))
    if not errors:
        errors.extend(validate_relationships(root, manifest))
    if not errors:
        errors.extend(validate_accuracy(root, manifest))
    return errors


def report(data_dir: str | Path | None = None) -> int:
    root = get_paths(data_dir).data_root / "exports" / "open" / "v15"
    errors = validate_package(root)
    if errors:
        print("V15_PUBLIC_VALIDATION_FAILED")
        for error in errors:
            print(f"- {error}")
        if not root.exists():
            print("Exécutez d'abord: python -m morocco_elections bootstrap")
        return 1
    print(f"V15_PUBLIC_VALIDATION_OK path={root}")
    return 0
