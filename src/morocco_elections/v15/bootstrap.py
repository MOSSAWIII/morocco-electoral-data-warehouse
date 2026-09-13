from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.provenance import sha256_file
from morocco_elections.quality.v15.package import validate_package


PUBLICATION = PROJECT_ROOT / "metadata" / "v15_publication.json"
EXIT_NETWORK = 2
EXIT_INTEGRITY = 3
EXIT_ARCHIVE = 4
EXIT_PACKAGE = 5
MAX_UNCOMPRESSED_BYTES = 1_500_000_000
MAX_MEMBER_BYTES = 750_000_000
MAX_COMPRESSION_RATIO = 250


class BootstrapError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _publication() -> dict:
    try:
        value = json.loads(PUBLICATION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(EXIT_INTEGRITY, f"configuration de publication illisible: {exc}") from exc
    if not isinstance(value.get("bytes"), int) or value["bytes"] <= 0:
        raise BootstrapError(EXIT_INTEGRITY, "taille officielle V15 absente ou invalide")
    if not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", ""))):
        raise BootstrapError(EXIT_INTEGRITY, "SHA-256 officiel V15 absent ou invalide")
    return value


def _verify_archive(archive: Path, publication: dict) -> None:
    if archive.stat().st_size != publication["bytes"]:
        raise BootstrapError(EXIT_INTEGRITY, "taille de l'archive V15 différente de la valeur publiée")
    if sha256_file(archive) != publication["sha256"]:
        raise BootstrapError(EXIT_INTEGRITY, "SHA-256 de l'archive V15 invalide")


def _member_path(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
        raise BootstrapError(EXIT_ARCHIVE, f"chemin ZIP non sûr: {name!r}")
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) == stat.S_IFLNK:
        raise BootstrapError(EXIT_ARCHIVE, f"lien symbolique ZIP interdit: {name!r}")
    return path


def _extract(archive: Path, extract_root: Path) -> Path:
    try:
        with zipfile.ZipFile(archive) as bundle:
            total = 0
            members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
            for info in bundle.infolist():
                relative = _member_path(info)
                total += info.file_size
                if info.file_size > MAX_MEMBER_BYTES or total > MAX_UNCOMPRESSED_BYTES:
                    raise BootstrapError(EXIT_ARCHIVE, "archive V15 trop volumineuse après décompression")
                if info.compress_size == 0 and info.file_size:
                    raise BootstrapError(EXIT_ARCHIVE, f"ratio de compression invalide: {info.filename}")
                if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                    raise BootstrapError(EXIT_ARCHIVE, f"ratio de compression suspect: {info.filename}")
                members.append((info, relative))
            for info, relative in members:
                target = extract_root.joinpath(*relative.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except (zipfile.BadZipFile, OSError) as exc:
        raise BootstrapError(EXIT_ARCHIVE, f"archive V15 illisible: {exc}") from exc
    package = extract_root / "morocco_elections_v15"
    if not package.is_dir():
        raise BootstrapError(EXIT_ARCHIVE, "racine morocco_elections_v15 absente de l'archive")
    unexpected = [path.name for path in extract_root.iterdir() if path != package]
    if unexpected:
        raise BootstrapError(EXIT_ARCHIVE, "fichier inattendu hors de la racine du paquet")
    return package


def _install_atomically(package: Path, destination: Path, temporary_root: Path) -> None:
    backup = temporary_root / "previous"
    moved_previous = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            moved_previous = True
        os.replace(package, destination)
    except OSError as exc:
        if moved_previous and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise BootstrapError(EXIT_PACKAGE, f"installation atomique impossible: {exc}") from exc


def run(data_dir: str | Path | None = None, *, network_only: bool = False) -> int:
    paths = get_paths(data_dir)
    destination = paths.data_root / "exports" / "open" / "v15"
    if destination.is_dir():
        existing_errors = validate_package(destination)
        if not existing_errors:
            print(f"V15_BOOTSTRAP_OK mode=existing_validated path={destination}")
            return 0

    try:
        publication = _publication()
        local_archive = paths.data_root / "exports" / "open" / "releases" / publication["asset_name"]
        force_network = network_only or os.environ.get("MOROCCO_ELECTIONS_V15_FORCE_DOWNLOAD") == "1"
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="v15-bootstrap-", dir=destination.parent) as temp_name:
            temporary_root = Path(temp_name)
            archive = temporary_root / "v15.zip"
            if local_archive.is_file() and not force_network:
                shutil.copy2(local_archive, archive)
                mode = "local_archive"
            else:
                url = os.environ.get("MOROCCO_ELECTIONS_V15_URL") or publication["download_url"]
                try:
                    with urllib.request.urlopen(url, timeout=60) as response, archive.open("wb") as output:
                        shutil.copyfileobj(response, output)
                except (OSError, urllib.error.URLError) as exc:
                    raise BootstrapError(EXIT_NETWORK, f"téléchargement V15 impossible: {exc}") from exc
                mode = "download"
            _verify_archive(archive, publication)
            package = _extract(archive, temporary_root / "extract")
            errors = validate_package(package)
            if errors:
                raise BootstrapError(EXIT_PACKAGE, "paquet extrait invalide: " + "; ".join(errors[:3]))
            _install_atomically(package, destination, temporary_root)
    except BootstrapError as exc:
        print(f"V15_BOOTSTRAP_FAILED code={exc.code} detail={exc}")
        return exc.code
    print(f"V15_BOOTSTRAP_OK mode={mode} path={destination}")
    return 0
