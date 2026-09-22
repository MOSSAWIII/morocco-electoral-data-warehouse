from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.config import get_paths
from morocco_elections.v15.queries import ANALYSES


def run(data_dir: str | Path | None = None, output_format: str = "text") -> int:
    package = get_paths(data_dir).data_root / "exports" / "open" / "v15"
    database = package / "morocco_elections_v15.duckdb"
    if not database.is_file():
        print(f"V15_ANALYSIS_MISSING_PACKAGE path={database}; exécutez `python -m morocco_elections bootstrap`")
        return 2
    try:
        coverage_rows = json.loads((package / "coverage_matrix.json").read_text(encoding="utf-8"))["analyses"]
        coverage_by_analysis = {row["analysis_id"]: row for row in coverage_rows}
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"V15_ANALYSIS_INVALID_COVERAGE detail={exc}")
        return 3
    connection = duckdb.connect(str(database), read_only=True)
    results: list[dict[str, Any]] = []
    try:
        for analysis in ANALYSES:
            cursor = connection.execute(analysis["sql"])
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
            results.append(
                {
                    **{key: value for key, value in analysis.items() if key != "sql"},
                    "coverage": coverage_by_analysis[analysis["id"]],
                    "rows": rows,
                }
            )
    finally:
        connection.close()
    if output_format == "json":
        print(json.dumps({"release": "V15", "analyses": results}, ensure_ascii=False, indent=2, default=str))
    else:
        print("V15 — CINQ ANALYSES DE RÉFÉRENCE")
        for result in results:
            print(f"\n{result['title']} [{result['id']}]")
            print("Tables: " + ", ".join(result["tables"]))
            print("Filtres: " + result["filters"])
            print("Unités: " + json.dumps(result["units"], ensure_ascii=False))
            coverage = result["coverage"]
            print(
                f"Couverture: {coverage['coverage_id']}; numérateur={coverage['numerator']}; "
                f"dénominateur={coverage['denominator']}; statut={coverage['status']}"
            )
            print("Limites: " + result["limitations"])
            print(json.dumps(result["rows"], ensure_ascii=False, default=str))
    return 0
