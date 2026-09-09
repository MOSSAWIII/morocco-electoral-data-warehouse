from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from morocco_elections.quality import validation as validate_project  # noqa: E402


def test_manifest_contract() -> None:
    manifest = validate_project.load_manifest()
    assert validate_project.validate_manifest(manifest) == []
    assert len(manifest["sources"]) == 12
    assert len(manifest["artifacts"]) == 5
    assert len(manifest["physical_files"]) == 30
    assert len(manifest["evidence"]) == 2


def test_documentation_contract() -> None:
    assert validate_project.validate_documentation() == []
    assert validate_project._recorded_documentation_date(validate_project.DOCUMENTATION_DIRS["v10"]) == "2026-09-07"


def test_v10_release_report_contract() -> None:
    manifest = validate_project.load_manifest()
    assert validate_project.validate_v10_release_report(manifest) == []


def test_v11_release_report_contract() -> None:
    manifest = validate_project.load_manifest()
    assert validate_project.validate_v11_release_report(manifest) == []


def test_v12_release_and_qualification_contracts() -> None:
    manifest = validate_project.load_manifest()
    assert validate_project.validate_v12_qualification(manifest) == []
    assert validate_project.validate_v12_release_report(manifest) == []


def test_v11a_artifact_contract() -> None:
    assert validate_project.validate_v11a_artifacts() == []


def test_smiig_artifact_contract() -> None:
    assert validate_project.validate_smiig_artifacts() == []


def test_quality_baseline_contract() -> None:
    assert validate_project.validate_quality_baseline_artifacts() == []


def test_electoral_denominators_contract() -> None:
    assert validate_project.validate_electoral_denominator_artifacts() == []


def test_hcp_indicators_contract() -> None:
    assert validate_project.validate_hcp_indicator_artifacts() == []


def test_v11_quality_baseline_contract() -> None:
    assert validate_project.validate_v11_quality_baseline_artifacts() == []


def test_github_backlog_contract() -> None:
    assert validate_project.validate_backlog() == []
    backlog = validate_project.json.loads(validate_project.BACKLOG_PATH.read_text(encoding="utf-8"))
    assert len(backlog["milestones"]) == 4
    assert len(backlog["labels"]) == 8
    assert len(backlog["issues"]) == 8


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
