from __future__ import annotations

import json
from pathlib import Path

import pytest

from morocco_elections.cli import build_parser, main
from morocco_elections.warehouse.auditor import _status_pair


def test_cli_exposes_only_canonical_commands() -> None:
    parser = build_parser()
    actions = [action for action in parser._actions if action.dest == "command"]
    assert set(actions[0].choices) == {"build", "validate", "audit", "package", "status"}
    for command in actions[0].choices:
        with pytest.raises(SystemExit) as exit_info:
            parser.parse_args([command, "--help"])
        assert exit_info.value.code == 0


def test_status_has_stable_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing"
    assert main(["status", "--package", str(missing)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["integrity_status"] == "FAIL"
    assert report["publication_status"] == "NOT_PUBLICATION_READY"


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
