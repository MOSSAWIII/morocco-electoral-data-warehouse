from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_project", ROOT / "tools" / "validate_project.py")
assert SPEC is not None and SPEC.loader is not None
validate_project = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_project)


def test_manifest_contract() -> None:
    manifest = validate_project.load_manifest()
    assert validate_project.validate_manifest(manifest) == []
    assert len(manifest["sources"]) == 6
    assert len(manifest["artifacts"]) == 2


def test_documentation_contract() -> None:
    assert validate_project.validate_documentation() == []


def test_github_backlog_contract() -> None:
    assert validate_project.validate_backlog() == []


def test_python_sources_parse() -> None:
    assert validate_project.validate_python_sources() == []


def test_forbidden_binary_is_rejected(tmp_path: Path) -> None:
    forbidden = tmp_path / "accidental.xlsx"
    forbidden.write_bytes(b"not an excel workbook")
    errors = validate_project.validate_repository_files([forbidden])
    assert any("hors dépôt" in error or "interdit" in error for error in errors)


def test_secret_signature_is_rejected(tmp_path: Path) -> None:
    local_dir = ROOT / ".pytest-validator-fixtures"
    local_dir.mkdir(exist_ok=True)
    secret = local_dir / "sample.txt"
    try:
        fake_token = "token=" + "gh" + "p_abcdefghijklmnopqrstuvwxyz123456"
        secret.write_text(fake_token, encoding="utf-8")
        errors = validate_project.validate_repository_files([secret])
        assert any("Secret potentiel" in error for error in errors)
    finally:
        secret.unlink(missing_ok=True)
        local_dir.rmdir()
