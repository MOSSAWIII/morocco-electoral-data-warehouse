from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from morocco_elections.config import PROJECT_ROOT


CONTRACT_PATH = PROJECT_ROOT / "metadata" / "v15_contract.json"


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("release") != "V15" or contract.get("release_version") != "15.0.0":
        raise RuntimeError(f"Contrat canonique V15 invalide: {path}")
    return contract


CONTRACT = load_contract()


@dataclass(frozen=True)
class TableSpec:
    name: str
    source_name: str
    category: str
    grain: str
    expected_rows: int
    primary_key: tuple[str, ...]
    natural_key: tuple[str, ...]
    columns: tuple[dict[str, Any], ...]
    table_checks: tuple[str, ...]


TABLE_SPECS: tuple[TableSpec, ...] = tuple(
    TableSpec(
        name=row["table_name"],
        source_name=row["source_table"],
        category=row["category"],
        grain=row["grain"],
        expected_rows=row["expected_rows"],
        primary_key=tuple(row["primary_key"]),
        natural_key=tuple(row["natural_key"]),
        columns=tuple(row["columns"]),
        table_checks=tuple(row.get("table_checks", [])),
    )
    for row in CONTRACT["tables"]
)

TABLE_BY_NAME = {item.name: item for item in TABLE_SPECS}
SOURCE_TO_TARGET = {item.source_name: item.name for item in TABLE_SPECS}
RELATIONSHIPS: tuple[dict[str, Any], ...] = tuple(CONTRACT["relationships"])
CORRECTIONS: tuple[dict[str, Any], ...] = tuple(CONTRACT["corrections"])
PARTIAL_DATE_POLICIES: tuple[dict[str, Any], ...] = tuple(CONTRACT["partial_date_policies"])
SOURCE_DISTRIBUTION: dict[str, Any] = CONTRACT["source_distribution"]


def table_contract(spec: TableSpec) -> dict[str, Any]:
    return {
        "table_name": spec.name,
        "source_table": spec.source_name,
        "category": spec.category,
        "grain": spec.grain,
        "rows": spec.expected_rows,
        "primary_key": list(spec.primary_key),
        "natural_key": list(spec.natural_key),
        "columns": [dict(column) for column in spec.columns],
        "table_checks": list(spec.table_checks),
    }


def all_table_contracts() -> list[dict[str, Any]]:
    return [table_contract(spec) for spec in TABLE_SPECS]
