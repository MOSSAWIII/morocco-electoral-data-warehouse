from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, env=ENV, text=True, capture_output=True, check=False)


def test_structured_cli_validation() -> None:
    result = run_command(sys.executable, "-m", "morocco_elections", "validate", "--mode", "ci")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALIDATION_OK" in result.stdout


def test_legacy_wrappers_expose_help() -> None:
    for script in ("build_v9.py", "generate_v9_documentation.py"):
        result = run_command(sys.executable, script, "--help")
        assert result.returncode == 0, result.stdout + result.stderr


def test_all_structured_commands_are_registered() -> None:
    for args in (
        ("build", "--help"),
        ("docs", "--help"),
        ("validate", "--help"),
        ("github", "publish-backlog", "--help"),
    ):
        result = run_command(sys.executable, "-m", "morocco_elections", *args)
        assert result.returncode == 0, result.stdout + result.stderr


def test_v10_versions_are_registered() -> None:
    for command in ("build", "docs"):
        result = run_command(sys.executable, "-m", "morocco_elections", command, "v10", "--help")
        assert result.returncode == 0, result.stdout + result.stderr


def test_full_mode_reports_missing_override_without_writing(tmp_path: Path) -> None:
    result = run_command(
        sys.executable,
        "-m",
        "morocco_elections",
        "validate",
        "--mode",
        "full",
        "--data-dir",
        str(tmp_path),
    )
    assert result.returncode == 1
    assert "fichier local absent" in result.stdout
