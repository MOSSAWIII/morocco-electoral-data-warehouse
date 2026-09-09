from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import openpyxl

from morocco_elections.config import get_paths
from morocco_elections.legacy.v9.build import rows_from_sheet


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    answered = sum(row.get("response_date") not in (None, "") for row in rows)
    linked = [row for row in rows if row.get("person_id") not in (None, "")]
    by_period: dict[str, dict[str, int | float]] = {}
    for period in sorted({str(row["period_raw"]) for row in rows}):
        selected = [row for row in rows if str(row["period_raw"]) == period]
        period_answered = sum(row.get("response_date") not in (None, "") for row in selected)
        by_period[period] = {
            "questions": len(selected),
            "answered": period_answered,
            "response_rate_pct": round(100 * period_answered / len(selected), 4),
        }
    person_counts = Counter(str(row["person_id"]) for row in linked)
    person_periods: dict[str, set[str]] = defaultdict(set)
    for row in linked:
        person_periods[str(row["person_id"])].add(str(row["period_raw"]))
    active_segment_distribution = Counter(len(periods) for periods in person_periods.values())
    return {
        "release": "V12",
        "scope": "questions écrites; quatre segments officiels du cycle 2023–2024",
        "questions": total,
        "answered": answered,
        "response_rate_pct": round(100 * answered / total, 4) if total else None,
        "identity_rows_linked": len(linked),
        "identity_rows_unlinked": total - len(linked),
        "linked_people": len(person_counts),
        "question_count_per_linked_person": {
            "minimum": min(person_counts.values()) if person_counts else None,
            "median": statistics.median(person_counts.values()) if person_counts else None,
            "maximum": max(person_counts.values()) if person_counts else None,
        },
        "linked_people_by_active_segment_count": {
            str(segment_count): active_segment_distribution.get(segment_count, 0) for segment_count in range(1, 5)
        },
        "periods": by_period,
        "limitations": [
            "Les 136 lignes sans person_id sont exclues des trajectoires individuelles.",
            "Un nombre de questions ne mesure ni la présence, ni l'assiduité, ni la qualité du mandat.",
            "Les taux de réponse décrivent uniquement les dates publiées dans ces quatre ressources.",
        ],
    }


def _render(report: dict[str, Any]) -> str:
    lines = [
        "V12 — TESTS MÉTIER DE L'ACTIVITÉ PARLEMENTAIRE",
        f"Périmètre: {report['scope']}",
        f"Questions: {report['questions']}; avec réponse: {report['answered']} ({report['response_rate_pct']:.4f} %)",
        f"Raccordement identité: {report['identity_rows_linked']} lignes; non raccordées: {report['identity_rows_unlinked']}",
        f"Députés raccordés actifs: {report['linked_people']}",
        "Trajectoire — nombre de segments actifs par député raccordé: "
        + ", ".join(f"{key}={value}" for key, value in report["linked_people_by_active_segment_count"].items()),
        "Limites:",
        *[f"- {item}" for item in report["limitations"]],
    ]
    return "\n".join(lines)


def run(data_dir: str | Path | None = None, output_format: str = "text") -> int:
    workbook_path = get_paths(data_dir).v12_workbook
    if not workbook_path.is_file():
        raise FileNotFoundError(workbook_path)
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    _, rows = rows_from_sheet(workbook["PARLIAMENTARY_QUESTIONS"])
    workbook.close()
    report = summarize(rows)
    print(json.dumps(report, ensure_ascii=False, indent=2) if output_format == "json" else _render(report))
    return 0
