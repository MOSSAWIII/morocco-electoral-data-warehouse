from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest

from morocco_elections.cli import build_parser, main
from morocco_elections.warehouse.auditor import _status_pair


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TEXT_ROOTS = (
    ".github", "docs", "examples", "metadata", "scripts", "src", "tests",
)
ACTIVE_TEXT_SUFFIXES = {".json", ".md", ".py", ".sql", ".toml", ".txt", ".yaml", ".yml"}


def test_cli_exposes_only_canonical_commands() -> None:
    parser = build_parser()
    actions = [action for action in parser._actions if action.dest == "command"]
    assert set(actions[0].choices) == {"build", "validate", "audit", "package", "status"}
    for command in actions[0].choices:
        with pytest.raises(SystemExit) as exit_info:
            parser.parse_args([command, "--help"])
        assert exit_info.value.code == 0


def test_current_documentation_contains_only_parseable_cli_commands() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "data/README.md",
        ROOT / ".github/pull_request_template.md",
        *(
            path
            for path in (ROOT / "docs").rglob("*.md")
            if "archive" not in path.relative_to(ROOT / "docs").parts
        ),
    ]
    parser = build_parser()
    commands: list[str] = []
    pattern = re.compile(
        r"(?:python -m morocco_elections|morocco-elections)\s+([^`\r\n]+)"
    )
    for path in paths:
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            command = match.group(1).strip()
            commands.append(command)
            parser.parse_args(shlex.split(command))

    assert commands
    assert {shlex.split(command)[0] for command in commands} == {
        "build", "validate", "audit", "package", "status",
    }


def test_active_product_has_no_intermediate_release_identity() -> None:
    # The pinned historical seed descriptor must preserve its real remote asset
    # locator. Everything else in the active product must be generation-free.
    excluded = {
        ROOT / "metadata/warehouse/seed_snapshot.json",
    }
    forbidden_names = {
        "source" + "_release",
        "v" + "15_seed",
    }
    generation_pattern = re.compile(
        r"(?i)(?<![a-z0-9])v(?:" + "|".join(str(number) for number in range(9, 17)) + r")(?:\b|_)"
    )
    findings: list[str] = []

    candidates = [
        ROOT / name
        for name in ("README.md", "CONTRIBUTING.md", "pyproject.toml", "data/README.md")
    ]
    for root_name in ACTIVE_TEXT_ROOTS:
        candidates.extend(path for path in (ROOT / root_name).rglob("*") if path.is_file())

    for path in candidates:
        if path in excluded or path.suffix.lower() not in ACTIVE_TEXT_SUFFIXES:
            continue
        relative = path.relative_to(ROOT)
        if "archive" in relative.parts or relative.parts[:2] == ("data", "exports"):
            continue
        content = path.read_text(encoding="utf-8")
        if generation_pattern.search(content) or any(name in content.lower() for name in forbidden_names):
            findings.append(relative.as_posix())

    assert findings == []


def test_status_has_stable_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing"
    assert main(["status", "--package", str(missing)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["integrity_status"] == "FAIL"
    assert report["publication_status"] == "NOT_PUBLICATION_READY"


def test_audit_forwards_historical_seed_diagnostic_separately(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[str] = []

    def fake_audit(argv: list[str]) -> int:
        received.extend(argv)
        return 0

    monkeypatch.setattr("morocco_elections.cli.audit_main", fake_audit)

    assert main([
        "audit", "--package", str(tmp_path), "--summary",
        "--historical-seed-diagnostic",
    ]) == 0
    assert received == [
        "--database", str(tmp_path / "morocco_elections.duckdb"),
        "--summary", "--historical-seed-diagnostic",
    ]


@pytest.mark.parametrize(
    ("archive_name", "extra_args"),
    [
        ("morocco-electoral-data-warehouse-v1.0.0.zip", []),
        ("development.zip", ["--require-ready"]),
    ],
)
def test_package_cannot_create_a_release_archive_before_readiness(
    archive_name: str,
    extra_args: list[str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "morocco_elections.cli.validate_package",
        lambda _path: {
            "status": "PASS",
            "integrity_status": "PASS",
            "publication_status": "NOT_PUBLICATION_READY",
        },
    )
    archive = tmp_path / archive_name

    exit_code = main([
        "package", "--package", str(tmp_path / "package"),
        "--output", str(archive), *extra_args,
    ])

    assert exit_code == 2
    assert not archive.exists()
    report = json.loads(capsys.readouterr().out)
    assert report["integrity_status"] == "PASS"
    assert report["publication_status"] == "NOT_PUBLICATION_READY"
    assert report["created"] is False


@pytest.mark.parametrize(
    ("semantic_failure", "package_status", "gate_status", "expected"),
    [
        (False, "PASS", "PUBLICATION_READY", ("PASS", "PUBLICATION_READY")),
        (False, "PASS", "NOT_PUBLICATION_READY", ("PASS", "NOT_PUBLICATION_READY")),
        (True, "PASS", "PUBLICATION_READY", ("FAIL", "NOT_PUBLICATION_READY")),
        (False, "FAIL", "PUBLICATION_READY", ("FAIL", "NOT_PUBLICATION_READY")),
        (False, None, "NOT_PUBLICATION_READY", ("PASS", "NOT_PUBLICATION_READY")),
    ],
)
def test_integrity_and_publication_statuses_are_independent(
    semantic_failure: bool,
    package_status: str | None,
    gate_status: str,
    expected: tuple[str, str],
) -> None:
    assert _status_pair(
        semantic_failure=semantic_failure,
        package_integrity_status=package_status,
        gate_publication_status=gate_status,
    ) == expected
