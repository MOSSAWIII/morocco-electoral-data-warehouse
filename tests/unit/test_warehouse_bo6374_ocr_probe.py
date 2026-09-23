from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("fitz")

from morocco_elections.warehouse.ocr_probe import (
    DEFAULT_SOURCE,
    EXPECTED_SOURCE_SHA256,
    recognize_page,
    verify_pinned_source,
)


ROOT = Path(__file__).resolve().parents[2]


def test_bo6374_ocr_only_accepts_pinned_scanned_annex(tmp_path: Path) -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(
        row for row in registry["sources"]
        if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015"
    )
    assert source["sha256"] == EXPECTED_SOURCE_SHA256
    original = ROOT / DEFAULT_SOURCE
    if not original.is_file():
        pytest.skip("original official BO 6374 not acquired locally")
    assert verify_pinned_source(original) == EXPECTED_SOURCE_SHA256
    with pytest.raises(ValueError, match="annex pages"):
        asyncio.run(recognize_page(original, 33, 2.0))
    with pytest.raises(ValueError, match="render scale"):
        asyncio.run(recognize_page(original, 34, 0.5))
    modified = tmp_path / "modified.pdf"
    modified.write_bytes(b"not the official BO")
    with pytest.raises(ValueError, match="pinned SHA-256"):
        verify_pinned_source(modified)
