from __future__ import annotations

import csv
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import openpyxl

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.provenance import sha256_file


CATALOG_PATH = PROJECT_ROOT / "metadata" / "acquisition_catalog.json"
DOMAINS = {
    "elections",
    "parliament",
    "governance",
    "parties",
    "hcp",
    "finance",
    "geography",
    "contextual",
}
STATES = {"ACTIVE", "COLLECTING", "WATCHLIST"}
CLASSIFICATIONS = {
    "CANONICAL_CANDIDATE",
    "REFERENCE",
    "CONTEXTUAL",
    "PILOT",
    "BLOCKED",
    "ARCHIVE_ONLY",
    "NOT_EVALUATED",
}


class AcquisitionError(RuntimeError):
    pass


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"Catalogue d'acquisition illisible: {path}: {exc}") from exc


def validate_catalog(catalog: dict) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != 1:
        errors.append("schema_version doit valoir 1")
    if catalog.get("current_warehouse_release") != "V12":
        errors.append("current_warehouse_release doit valoir V12")

    domains = catalog.get("domains")
    if not isinstance(domains, list) or set(domains) != DOMAINS:
        errors.append(f"domains doit contenir exactement {sorted(DOMAINS)}")

    candidates = catalog.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return [*errors, "candidates doit être une liste non vide"]

    required = {
        "source_id",
        "title",
        "domain",
        "producer",
        "portal_url",
        "target_period",
        "expected_formats",
        "priority",
        "state",
        "purpose",
        "reuse_status",
    }
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        label = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{label}: objet attendu")
            continue
        missing = sorted(required - candidate.keys())
        if missing:
            errors.append(f"{label}: champs absents: {', '.join(missing)}")
        source_id = candidate.get("source_id")
        if not isinstance(source_id, str) or not re.fullmatch(r"[A-Z0-9_]+", source_id) or source_id in seen:
            errors.append(f"{label}: source_id invalide ou dupliqué")
        else:
            seen.add(source_id)
        if candidate.get("domain") not in DOMAINS:
            errors.append(f"{label}: domaine inconnu")
        if candidate.get("state") not in STATES:
            errors.append(f"{label}: état inconnu")
        if candidate.get("priority") not in {1, 2, 3}:
            errors.append(f"{label}: priorité attendue entre 1 et 3")
        formats = candidate.get("expected_formats")
        if not isinstance(formats, list) or not formats or not all(isinstance(item, str) and item for item in formats):
            errors.append(f"{label}: expected_formats invalide")
        portal_url = candidate.get("portal_url")
        if not isinstance(portal_url, str) or urlparse(portal_url).scheme not in {"http", "https"}:
            errors.append(f"{label}: portal_url HTTP(S) attendu")
    return errors


def catalog_summary(catalog_path: str | Path | None = None) -> int:
    path = Path(catalog_path) if catalog_path else CATALOG_PATH
    try:
        catalog = load_catalog(path)
    except AcquisitionError as exc:
        print(f"SOURCE_CATALOG_FAILED: {exc}")
        return 1
    errors = validate_catalog(catalog)
    if errors:
        print("SOURCE_CATALOG_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    candidates = catalog["candidates"]
    by_state = {state: sum(item["state"] == state for item in candidates) for state in sorted(STATES)}
    print(
        "SOURCE_CATALOG_OK "
        f"candidates={len(candidates)} "
        + " ".join(f"{state.lower()}={count}" for state, count in by_state.items())
    )
    return 0


def _safe_filename(value: str) -> str:
    name = Path(value).name
    if name in {"", ".", ".."} or name != value or any(character in name for character in '<>:"/\\|?*'):
        raise AcquisitionError(f"Nom de fichier invalide: {value!r}")
    return name


def _candidate(catalog: dict, source_id: str) -> dict:
    matches = [item for item in catalog["candidates"] if item["source_id"] == source_id]
    if not matches:
        raise AcquisitionError(f"Source absente du catalogue: {source_id}")
    return matches[0]


def _detect_format(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {"xlsm": "xlsx", "tsv": "csv"}.get(suffix, suffix or "binary")


def _profile_xlsx(path: Path) -> dict:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets: list[dict] = []
    try:
        for worksheet in workbook.worksheets:
            iterator = worksheet.iter_rows(values_only=True)
            first = next(iterator, ())
            columns = [str(value).strip() if value is not None else "" for value in first]
            rows = sum(1 for row in iterator if any(value is not None for value in row))
            sheets.append({"name": worksheet.title, "rows": rows, "columns": len(first), "headers": columns})
    finally:
        workbook.close()
    return {"status": "PROFILED", "sheet_count": len(sheets), "sheets": sheets}


def _profile_csv(path: Path) -> dict:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter=delimiter)
        headers = next(reader, [])
        rows = sum(1 for row in reader if any(value != "" for value in row))
    return {
        "status": "PROFILED",
        "sheet_count": 1,
        "sheets": [{"name": path.name, "rows": rows, "columns": len(headers), "headers": headers}],
    }


def _profile_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        headers = sorted({str(key) for row in data if isinstance(row, dict) for key in row})
        rows = len(data)
    elif isinstance(data, dict):
        headers = sorted(str(key) for key in data)
        rows = 1
    else:
        headers, rows = [], 1
    return {
        "status": "PROFILED",
        "sheet_count": 1,
        "sheets": [{"name": path.name, "rows": rows, "columns": len(headers), "headers": headers}],
    }


def _profile_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        members = [item.filename for item in archive.infolist() if not item.is_dir()]
    return {"status": "PROFILED_ARCHIVE", "member_count": len(members), "members": members}


def profile_file(path: Path) -> dict:
    detected = _detect_format(path)
    base = {"format": detected, "byte_size": path.stat().st_size, "sha256": sha256_file(path)}
    try:
        if detected == "xlsx":
            detail = _profile_xlsx(path)
        elif detected == "csv":
            detail = _profile_csv(path)
        elif detected == "json":
            detail = _profile_json(path)
        elif detected == "zip":
            detail = _profile_zip(path)
        else:
            detail = {"status": "FORMAT_RECOGNIZED_PROFILE_NOT_AVAILABLE"}
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        detail = {"status": "PROFILE_FAILED", "error": f"{type(exc).__name__}: {exc}"}
    return {**base, **detail}


def _fetch_to_temp(url: str, destination: Path) -> tuple[str, dict[str, str | None]]:
    request = urllib.request.Request(url, headers={"User-Agent": "morocco-electoral-warehouse/12"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:  # noqa: S310
        shutil.copyfileobj(response, output)
        return response.geturl(), {"etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}


def acquire(
    source_id: str,
    *,
    url: str | None = None,
    input_path: str | Path | None = None,
    filename: str | None = None,
    data_dir: str | Path | None = None,
    as_of: str | None = None,
    catalog_path: str | Path | None = None,
) -> int:
    try:
        catalog = load_catalog(Path(catalog_path) if catalog_path else CATALOG_PATH)
        errors = validate_catalog(catalog)
        if errors:
            raise AcquisitionError("; ".join(errors))
        definition = _candidate(catalog, source_id)
        if bool(url) == bool(input_path):
            raise AcquisitionError("Utiliser exactement une entrée parmi --url et --input")
        if as_of:
            date.fromisoformat(as_of)
            retrieved_at = as_of
        else:
            retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        parsed_name = unquote(Path(urlparse(url).path).name) if url else Path(input_path).name
        selected_name = _safe_filename(filename or parsed_name or f"{source_id.lower()}.bin")
        data_root = get_paths(data_dir).data_root
        temp_root = data_root / "tmp" / "acquisition"
        temp_root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f"{source_id}_", suffix=Path(selected_name).suffix, dir=temp_root)
        os.close(fd)
        temp_path = Path(temp_name)
        final_url: str | None = None
        headers: dict[str, str | None] = {"etag": None, "last_modified": None}
        try:
            if url:
                if urlparse(url).scheme not in {"http", "https"}:
                    raise AcquisitionError("Seules les URL HTTP(S) sont acceptées")
                final_url, headers = _fetch_to_temp(url, temp_path)
            else:
                local_source = Path(input_path).resolve()
                if not local_source.is_file():
                    raise AcquisitionError(f"Fichier source absent: {local_source}")
                shutil.copyfile(local_source, temp_path)

            profile = profile_file(temp_path)
            if profile["format"] in {"csv", "json"} and profile.get("sheets"):
                profile["sheets"][0]["name"] = selected_name
            if profile["format"] not in definition["expected_formats"]:
                raise AcquisitionError(
                    f"Format {profile['format']!r} absent des formats attendus {definition['expected_formats']}"
                )
            digest = profile["sha256"]
            target = data_root / "raw" / definition["domain"] / "acquisitions" / source_id / digest[:12]
            destination = target / selected_name
            record_path = target / "acquisition.json"
            target.mkdir(parents=True, exist_ok=True)
            if destination.exists() and sha256_file(destination) != digest:
                raise AcquisitionError(f"Conflit d'immuabilité: {destination}")
            if not destination.exists():
                os.replace(temp_path, destination)

            record = {
                "schema_version": 1,
                "source_id": source_id,
                "title": definition["title"],
                "domain": definition["domain"],
                "producer": definition["producer"],
                "catalog_portal_url": definition["portal_url"],
                "target_period": definition["target_period"],
                "reuse_status": definition["reuse_status"],
                "retrieved_at": retrieved_at,
                "initial_url": url,
                "final_url": final_url,
                "etag": headers["etag"],
                "last_modified": headers["last_modified"],
                "original_filename": selected_name,
                "classification": "NOT_EVALUATED",
                "canonical_ingestion_authorized": False,
                "profile": profile,
            }
            encoded = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if record_path.exists() and record_path.read_text(encoding="utf-8") != encoded:
                raise AcquisitionError(f"Enregistrement existant différent: {record_path}")
            if not record_path.exists():
                record_path.write_text(encoded, encoding="utf-8")
        finally:
            temp_path.unlink(missing_ok=True)
    except (AcquisitionError, OSError, ValueError) as exc:
        print(f"SOURCE_ACQUISITION_FAILED: {exc}")
        return 1

    print(
        f"SOURCE_ACQUIRED source_id={source_id} sha256={digest} "
        f"file={destination} profile={profile['status']}"
    )
    return 0
