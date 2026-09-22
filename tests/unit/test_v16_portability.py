from __future__ import annotations

import hashlib
import urllib.error
from pathlib import Path

import pytest

from morocco_elections.v16.portability import (
    SourceEvidenceError,
    portability_descriptor_sha256,
    portable_evidence_root,
    validate_source_portability,
)


def _row(payload: bytes, *, category: str = "EMBEDDED_REDISTRIBUTABLE") -> dict:
    row = {
        "source_id": "SOURCE",
        "portability_category": category,
        "relative_path": "evidence/source.bin",
        "source_url": "https://official.example/source.bin",
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "license_status": "CC-BY-4.0",
        "embedded": category == "EMBEDDED_REDISTRIBUTABLE",
        "gate_consumers": ["OFFICIAL_UNIVERSE_DECLARED"],
    }
    row["descriptor_sha256"] = portability_descriptor_sha256(row)
    return row


def test_embedded_source_is_exact_and_modified_or_missing_bytes_fail(tmp_path: Path) -> None:
    payload = b"official"
    row = _row(payload)
    path = tmp_path / row["relative_path"]
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    with portable_evidence_root([row], {"SOURCE"}, package_root=tmp_path, repository_root=None) as root:
        assert (root / row["relative_path"]).read_bytes() == payload
    path.write_bytes(b"modified")
    with pytest.raises(SourceEvidenceError, match="absent or modified"):
        with portable_evidence_root([row], {"SOURCE"}, package_root=tmp_path, repository_root=None):
            pass
    path.unlink()
    with pytest.raises(SourceEvidenceError, match="absent or modified"):
        with portable_evidence_root([row], {"SOURCE"}, package_root=tmp_path, repository_root=None):
            pass


def test_portability_rejects_absolute_path_and_mutated_url_or_sha() -> None:
    row = _row(b"official", category="REPRODUCIBLY_ACQUIRABLE")
    absolute = {**row, "relative_path": "C:/private/source.bin"}
    assert any("relative" in failure for failure in validate_source_portability([absolute]))
    changed_url = {**row, "source_url": "https://attacker.example/source.bin"}
    assert any("modified" in failure for failure in validate_source_portability([changed_url]))
    changed_sha = {**row, "sha256": "0" * 64}
    assert any("modified" in failure for failure in validate_source_portability([changed_sha]))


def test_reproducible_acquisition_rejects_changed_remote_bytes(tmp_path: Path, monkeypatch) -> None:
    payload = b"official"
    row = _row(payload, category="REPRODUCIBLY_ACQUIRABLE")

    class Response:
        sent = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, size: int = -1) -> bytes:
            del size
            if self.sent:
                return b""
            self.sent = True
            return b"changed"

    monkeypatch.setattr("morocco_elections.v16.portability.urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(SourceEvidenceError, match="differ"):
        with portable_evidence_root([row], {"SOURCE"}, package_root=tmp_path, repository_root=None):
            pass


def test_reproducible_acquisition_rejects_unavailable_remote(tmp_path: Path, monkeypatch) -> None:
    row = _row(b"official", category="REPRODUCIBLY_ACQUIRABLE")

    def unavailable(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("morocco_elections.v16.portability.urllib.request.urlopen", unavailable)
    with pytest.raises(SourceEvidenceError, match="unavailable"):
        with portable_evidence_root([row], {"SOURCE"}, package_root=tmp_path, repository_root=None):
            pass
