from __future__ import annotations

import json
from pathlib import Path

import pytest

from morocco_elections.cli import build_parser, main


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
    assert json.loads(capsys.readouterr().out)["status"] == "MISSING"
