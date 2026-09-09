from __future__ import annotations

import json
from pathlib import Path

import openpyxl

from morocco_elections.sources.acquisition import (
    CATALOG_PATH,
    acquire,
    build_inventory,
    load_catalog,
    profile_file,
    validate_catalog,
    validate_inventory,
)


def _catalog(tmp_path: Path) -> Path:
    catalog = {
        "schema_version": 1,
        "current_warehouse_release": "V12",
        "domains": sorted(
            {
                "elections",
                "parliament",
                "governance",
                "parties",
                "hcp",
                "finance",
                "geography",
                "contextual",
            }
        ),
        "candidates": [
            {
                "source_id": "TEST_SOURCE",
                "title": "Source synthétique",
                "domain": "elections",
                "producer": "Producteur synthétique",
                "portal_url": "https://example.test/data",
                "target_period": "2021",
                "expected_formats": ["csv", "xlsx"],
                "priority": 1,
                "state": "ACTIVE",
                "purpose": "Test sans donnée réelle",
                "reuse_status": "Synthétique",
            }
        ],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return path


def test_repository_acquisition_catalog_is_valid() -> None:
    assert validate_catalog(load_catalog(CATALOG_PATH)) == []


def test_profile_xlsx_inventories_sheets_columns_and_rows(tmp_path: Path) -> None:
    workbook_path = tmp_path / "candidate.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "données"
    sheet.append(["geo_id", "value"])
    sheet.append(["MA-TEST", 12])
    workbook.create_sheet("notes").append(["note"])
    workbook.save(workbook_path)

    profile = profile_file(workbook_path)

    assert profile["status"] == "PROFILED"
    assert profile["sheet_count"] == 2
    assert profile["sheets"][0] == {
        "name": "données",
        "rows": 1,
        "columns": 2,
        "headers": ["geo_id", "value"],
    }


def test_profile_detects_legacy_xls_magic_despite_xlsx_suffix(tmp_path: Path) -> None:
    path = tmp_path / "mislabelled.xlsx"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 24)

    profile = profile_file(path)

    assert profile["format"] == "xls"
    assert profile["status"] == "FORMAT_RECOGNIZED_PROFILE_NOT_AVAILABLE"


def test_acquire_local_file_is_immutable_profiled_and_idempotent(tmp_path: Path) -> None:
    catalog_path = _catalog(tmp_path)
    input_path = tmp_path / "candidate.csv"
    input_path.write_text("geo_id,value\nMA-TEST,12\n", encoding="utf-8")
    data_root = tmp_path / "warehouse-data"

    first = acquire(
        "TEST_SOURCE",
        input_path=input_path,
        data_dir=data_root,
        as_of="2026-09-09",
        catalog_path=catalog_path,
    )
    second = acquire(
        "TEST_SOURCE",
        input_path=input_path,
        data_dir=data_root,
        as_of="2026-09-09",
        catalog_path=catalog_path,
    )

    assert first == second == 0
    records = list(data_root.glob("raw/elections/acquisitions/TEST_SOURCE/*/acquisition.json"))
    payloads = list(data_root.glob("raw/elections/acquisitions/TEST_SOURCE/*/candidate.csv"))
    assert len(records) == len(payloads) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["profile"]["status"] == "PROFILED"
    assert record["profile"]["sheets"][0]["rows"] == 1
    assert record["classification"] == "NOT_EVALUATED"
    assert record["canonical_ingestion_authorized"] is False


def test_acquire_rejects_unknown_source(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.csv"
    candidate.write_text("a\n1\n", encoding="utf-8")
    assert acquire(
        "UNKNOWN",
        input_path=candidate,
        data_dir=tmp_path / "data",
        catalog_path=_catalog(tmp_path),
    ) == 1


def test_acquire_rejects_unexpected_format_before_raw_promotion(tmp_path: Path) -> None:
    catalog_path = _catalog(tmp_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["candidates"][0]["expected_formats"] = ["xlsx"]
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    candidate = tmp_path / "candidate.csv"
    candidate.write_text("a\n1\n", encoding="utf-8")
    data_root = tmp_path / "data"

    assert acquire(
        "TEST_SOURCE",
        input_path=candidate,
        data_dir=data_root,
        catalog_path=catalog_path,
    ) == 1
    assert not list(data_root.glob("raw/**/*"))


def test_inventory_is_deterministic_and_contains_no_raw_rows(tmp_path: Path) -> None:
    catalog_path = _catalog(tmp_path)
    candidate = tmp_path / "candidate.csv"
    candidate.write_text("geo_id,value\nMA-TEST,secret-row-value\n", encoding="utf-8")
    data_root = tmp_path / "data"
    assert acquire(
        "TEST_SOURCE",
        input_path=candidate,
        data_dir=data_root,
        as_of="2026-09-09",
        catalog_path=catalog_path,
    ) == 0

    first = build_inventory(data_root, "2026-09-09")
    second = build_inventory(data_root, "2026-09-09")

    assert first == second
    assert validate_inventory(first) == []
    assert first["record_count"] == 1
    assert first["duplicate_payloads"] == []
    assert first["profile_issues"] == []
    assert first["structural_issues"] == []
    assert first["records"][0]["tables"][0]["headers"] == ["geo_id", "value"]
    assert "secret-row-value" not in json.dumps(first)


def test_inventory_flags_identical_payload_across_source_families(tmp_path: Path) -> None:
    catalog_path = _catalog(tmp_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    second = dict(catalog["candidates"][0])
    second["source_id"] = "SECOND_SOURCE"
    catalog["candidates"].append(second)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    candidate = tmp_path / "candidate.csv"
    candidate.write_text("id\n1\n", encoding="utf-8")
    data_root = tmp_path / "data"

    for source_id in ("TEST_SOURCE", "SECOND_SOURCE"):
        assert acquire(
            source_id,
            input_path=candidate,
            data_dir=data_root,
            as_of="2026-09-09",
            catalog_path=catalog_path,
        ) == 0

    inventory = build_inventory(data_root, "2026-09-09")
    assert len(inventory["duplicate_payloads"]) == 1
    assert len(inventory["duplicate_payloads"][0]["acquisition_ids"]) == 2
