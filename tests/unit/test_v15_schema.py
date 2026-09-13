from __future__ import annotations

import ast
from pathlib import Path

from morocco_elections.v15.schema import TABLE_SPECS


ROOT = Path(__file__).resolve().parents[2]


def test_v15_has_exactly_eight_core_tables() -> None:
    assert [item.name for item in TABLE_SPECS if item.category == "CORE"] == [
        "dim_geo", "dim_party", "dim_election", "dim_electoral_contest",
        "fact_election_result", "fact_electoral_mobilization", "fact_mandate", "fact_observation",
    ]
    assert {item.category for item in TABLE_SPECS} <= {"CORE", "SPECIALIZED", "BRIDGE", "METADATA", "ANALYTICAL"}


def test_v15_does_not_import_old_release_generators() -> None:
    root = ROOT / "src/morocco_elections/v15"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any("releases.v" in name or "exports.open_v" in name for name in imports), path


def test_v15_runtime_has_no_private_or_excel_dependency() -> None:
    roots = [
        ROOT / "src/morocco_elections/v15",
        ROOT / "src/morocco_elections/quality/v15",
        ROOT / "src/morocco_elections/analysis/v15.py",
    ]
    files = [roots[-1], *roots[0].glob("*.py"), *roots[1].glob("*.py")]
    forbidden = ("read_excel", ".xlsx", ".xls'", '.xls"', "private/")
    for path in files:
        source = path.read_text(encoding="utf-8").lower()
        assert not any(token in source for token in forbidden), path
