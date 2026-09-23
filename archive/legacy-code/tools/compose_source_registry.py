"""One-time deterministic composition of the canonical source registry."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.warehouse.sources import canonical_source_id


ROOT = Path(__file__).resolve().parents[3]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        default=lambda item: item.isoformat() if isinstance(item, (date, datetime)) else str(item),
    ).encode("utf-8")


def _seed_rows() -> list[dict[str, Any]]:
    database = ROOT / "data/seeds/historical/morocco_elections.duckdb"
    connection = duckdb.connect(str(database), read_only=True)
    try:
        cursor = connection.execute("SELECT * FROM sources ORDER BY source_id")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]
    finally:
        connection.close()


def compose() -> dict[str, Any]:
    official_payload = json.loads(
        (ROOT / "archive/legacy-metadata/official_source_registry.json").read_text(encoding="utf-8")
    )
    acquired_payload = json.loads(
        (ROOT / "archive/legacy-metadata/source_manifest.json").read_text(encoding="utf-8")
    )
    elected_payload = json.loads(
        (ROOT / "archive/legacy-metadata/elected_2015_source.json").read_text(encoding="utf-8")
    )
    seed_rows = _seed_rows()
    rows: dict[str, dict[str, Any]] = {}

    def base(source_id: str) -> dict[str, Any]:
        canonical_id = canonical_source_id(source_id)
        row = rows.setdefault(canonical_id, {
            "source_id": canonical_id,
            "aliases": [],
            "title": canonical_id,
            "authority": "UNKNOWN",
            "source_url": None,
            "acquired_at": None,
            "raw_path": None,
            "bytes": None,
            "sha256": None,
            "grain": "UNKNOWN",
            "format": None,
            "reliability_score": None,
            "license_status": "UNKNOWN",
            "verification_status": "METADATA_ONLY",
            "public_package_disposition": "METADATA_ONLY",
            "status": "historical_metadata",
            "usages": [],
            "notes": None,
        })
        if source_id != canonical_id and source_id not in row["aliases"]:
            row["aliases"].append(source_id)
        return row

    for seed in seed_rows:
        row = base(str(seed["source_id"]))
        row.update({
            "title": seed.get("source_name") or row["title"],
            "authority": seed.get("publisher") or row["authority"],
            "source_url": seed.get("url") or row["source_url"],
            "grain": seed.get("geo_granularity") or row["grain"],
            "format": seed.get("format") or row["format"],
            "reliability_score": seed.get("reliability_score"),
            "license_status": seed.get("license") or row["license_status"],
            "status": seed.get("status") or row["status"],
            "notes": seed.get("notes") or row["notes"],
        })
        row["usages"].append("historical_seed")

    for acquired in acquired_payload["sources"]:
        row = base(str(acquired["source_id"]))
        row.update({
            "title": row["title"],
            "authority": acquired.get("producer") or row["authority"],
            "source_url": acquired.get("source_url") or row["source_url"],
            "acquired_at": acquired_payload.get("last_verified"),
            "raw_path": acquired.get("local_path"),
            "bytes": acquired.get("byte_size"),
            "sha256": acquired.get("sha256"),
            "grain": acquired.get("grain") or row["grain"],
            "license_status": acquired.get("license") or row["license_status"],
            "verification_status": "PINNED_BYTES",
            "public_package_disposition": "REPRODUCIBLY_ACQUIRABLE",
            "status": acquired.get("status") or row["status"],
        })
        row["usages"].append("acquired_source")

    for official in official_payload["sources"]:
        row = base(str(official["source_id"]))
        row.update({
            key: value for key, value in official.items()
            if key not in {"source_id", "title", "authority", "source_url", "acquired_at", "raw_path", "bytes", "sha256", "license_status", "verification_status", "public_package_disposition", "notes"}
        })
        row.update({
            "title": official.get("title") or row["title"],
            "authority": official.get("authority") or row["authority"],
            "source_url": official.get("source_url") or row["source_url"],
            "acquired_at": official.get("acquired_at") or row["acquired_at"],
            "raw_path": official.get("raw_path") or row["raw_path"],
            "bytes": official.get("bytes") if official.get("bytes") is not None else row["bytes"],
            "sha256": official.get("sha256") or row["sha256"],
            "license_status": official.get("license_status") or row["license_status"],
            "verification_status": official.get("verification_status") or row["verification_status"],
            "public_package_disposition": official.get("public_package_disposition") or row["public_package_disposition"],
            "status": "active",
            "notes": official.get("notes") or row["notes"],
        })
        row["usages"].append("official_evidence")

    elected = elected_payload["candidate"]
    row = base("TAFRA_COMMUNAL_ELECTED_2015")
    row.update({
        "title": "Composition des conseils communaux 2015",
        "authority": elected["producer"],
        "source_url": elected["download_url"],
        "acquired_at": elected["retrieved_on"],
        "raw_path": elected["local_path"],
        "bytes": elected["byte_size"],
        "sha256": elected["sha256"],
        "grain": "one elected person per communal mandate",
        "license_status": elected["license"],
        "verification_status": "PINNED_BYTES",
        "public_package_disposition": "REPRODUCIBLY_ACQUIRABLE",
        "status": "qualified_secondary_copy",
        "notes": elected_payload["scope"],
    })
    row["usages"].append("descriptive_reconciliation")

    output_rows = []
    pipeline = base("WAREHOUSE_BUILD_PIPELINE")
    pipeline.update({
        "title": "Morocco Electoral Data Warehouse canonical build pipeline",
        "authority": "Morocco Electoral Data Warehouse maintainers",
        "source_url": "https://github.com/MOSSAWIII/morocco-electoral-data-warehouse",
        "grain": "one deterministic build process",
        "license_status": "ODC-ODbL",
        "verification_status": "REPOSITORY_CODE",
        "public_package_disposition": "INCLUDE",
        "status": "active",
        "notes": "Internal provenance identity for files generated by the canonical build.",
    })
    pipeline["usages"].append("canonical_build")
    chamber = base("SRC_CHAMBER_2021")
    chamber.update({
        "acquired_at": "2026-09-23",
        "raw_path": "data/raw/elections/warehouse/results/chamber_legislative_2021.html",
        "bytes": 227975,
        "sha256": "7949301d7cdd4b615245777f1c68ea3b16ee9ba67c5a6efc3041166c1bb9ba01",
        "license_status": "UNKNOWN",
        "verification_status": "VERIFIED_AUTHORITY_AND_BYTES",
        "public_package_disposition": "METADATA_ONLY",
        "status": "active",
        "notes": "Official national party seat allocation, plus regional and local constituency seat totals; raw HTML excluded from the public package pending redistribution review.",
    })
    chamber["usages"].append("official_evidence")
    for source_id, row in sorted(rows.items()):
        aliases = {
            alias for alias in row["aliases"]
            if not re.search(r"_V(?:9|10|11|12|13|14|15|16)(?:_|$)", alias, flags=re.IGNORECASE)
        }
        if source_id == "MA_HCP_RGPH2014_INDICATEURS_COMMUNAUX_INDIVIDUS":
            aliases.add("SRC_HCP_RGPH2014_INDIVIDUALS")
        row["aliases"] = sorted(aliases)
        row["usages"] = sorted(set(row["usages"]))
        if row.get("notes"):
            row["notes"] = re.sub(
                r"\bV(?:9|10|11|12|13|14|15|16)(?:[-_][A-Z0-9]+)*\b",
                "revue historique", str(row["notes"]), flags=re.IGNORECASE,
            )
        row["acquisition_status"] = (
            "ACQUIRED_PINNED"
            if row.get("raw_path") and row.get("bytes") is not None and row.get("sha256")
            else "NOT_ACQUIRED_METADATA_ONLY"
        )
        row["descriptor_sha256"] = hashlib.sha256(_canonical_bytes(row)).hexdigest()
        output_rows.append(row)
    return {
        "schema_version": "1.0.0",
        "as_of_date": official_payload["as_of_date"],
        "product": "Morocco Electoral Data Warehouse",
        "input_counts": {
            "official": len(official_payload["sources"]),
            "acquired": len(acquired_payload["sources"]),
            "elected": 1,
            "historical_seed": len(seed_rows),
        },
        "source_count": len(output_rows),
        "sources": output_rows,
    }


if __name__ == "__main__":
    destination = ROOT / "metadata/warehouse/source_registry.json"
    destination.write_text(
        json.dumps(
            compose(), ensure_ascii=False, indent=2, sort_keys=True,
            default=lambda item: item.isoformat() if isinstance(item, (date, datetime)) else str(item),
        ) + "\n",
        encoding="utf-8",
    )
