from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.provenance import sha256_file


RELEASE_REPORT = PROJECT_ROOT / "metadata" / "v11_release_report.json"
REQUIRED_COLUMNS = {
    "COMMUNE_TRANSITION_PANEL": {
        "geo_id",
        "winner_2015",
        "winner_2021",
        "turnout_change_pp",
    },
    "COUNCIL_SEAT_STATUS_V10": {
        "geo_id",
        "legal_seat_count",
        "observed_elected_count",
        "documented_vacancy_count",
        "reconciled_difference",
    },
    "LOCAL_COUNCIL_CONTROL": {
        "geo_id",
        "president_party_id",
        "president_party_same_as_largest_party",
    },
    "FACT_OBSERVATION": {"geo_id", "time_id", "metric_id", "value_numeric"},
}


class ReferenceAnalysisError(RuntimeError):
    """Raised when V11 cannot support the reference analyses safely."""


def _read_tables(workbook: Path) -> dict[str, pd.DataFrame]:
    try:
        tables = pd.read_excel(workbook, sheet_name=list(REQUIRED_COLUMNS), header=3)
    except (OSError, ValueError) as exc:
        raise ReferenceAnalysisError(f"Classeur V11 illisible: {workbook}: {exc}") from exc
    for sheet, columns in REQUIRED_COLUMNS.items():
        missing = columns - set(tables[sheet].columns)
        if missing:
            raise ReferenceAnalysisError(f"{sheet}: colonnes absentes: {sorted(missing)}")
    return tables


def _whole_number(value: Any) -> int:
    number = float(value)
    if not number.is_integer():
        raise ReferenceAnalysisError(f"Valeur attendue entière: {value}")
    return int(number)


def compute_reference_analyses(workbook: Path) -> dict[str, Any]:
    """Compute a compact, read-only analytical proof from a validated V11 workbook."""
    tables = _read_tables(workbook)
    transitions = tables["COMMUNE_TRANSITION_PANEL"]
    seats = tables["COUNCIL_SEAT_STATUS_V10"]
    control = tables["LOCAL_COUNCIL_CONTROL"]
    facts = tables["FACT_OBSERVATION"]

    winner_rows = transitions.dropna(subset=["winner_2015", "winner_2021"])
    turnout = pd.to_numeric(transitions["turnout_change_pp"], errors="coerce").dropna()
    presidency = (
        control.dropna(subset=["president_party_id"])
        .groupby("geo_id", as_index=False)
        .agg(president_among_largest=("president_party_same_as_largest_party", "max"))
    )
    hcp = facts[facts["metric_id"].isin({"population_legal", "population_municipal"})].copy()
    hcp["value_numeric"] = pd.to_numeric(hcp["value_numeric"], errors="coerce")

    seat_totals = {
        column: _whole_number(pd.to_numeric(seats[column], errors="raise").sum())
        for column in (
            "legal_seat_count",
            "observed_elected_count",
            "documented_vacancy_count",
            "reconciled_difference",
        )
    }
    hcp_groups = {
        f"{metric_id}_{_whole_number(year)}": {
            "units": int(group["geo_id"].nunique()),
            "total_persons": _whole_number(group["value_numeric"].sum()),
        }
        for (metric_id, year), group in hcp.groupby(["metric_id", "time_id"])
    }

    result = {
        "schema_version": 1,
        "release": "V11",
        "source_workbook_sha256": sha256_file(workbook),
        "analyses": [
            {
                "analysis_id": "winner_transition_2015_2021",
                "status": "CONDITIONNELLE",
                "scope_communes": int(len(winner_rows)),
                "winner_changed": int((winner_rows["winner_2015"] != winner_rows["winner_2021"]).sum()),
                "winner_retained": int((winner_rows["winner_2015"] == winner_rows["winner_2021"]).sum()),
                "limits": "Classements limités aux partis observés aux deux dates; les sièges 2015 sont absents.",
            },
            {
                "analysis_id": "reported_turnout_change_2015_2021",
                "status": "CONDITIONNELLE",
                "scope_communes": int(len(turnout)),
                "increase": int((turnout > 0).sum()),
                "decrease": int((turnout < 0).sum()),
                "unchanged": int((turnout == 0).sum()),
                "mean_change_pp": round(float(turnout.mean()), 4),
                "median_change_pp": round(float(turnout.median()), 4),
                "limits": "Taux publiés uniquement; aucun effectif d'inscrits ou de votants n'est reconstruit.",
            },
            {
                "analysis_id": "council_seats_2021",
                "status": "AUTORISÉE",
                "scope_communes": int(seats["geo_id"].nunique()),
                "occupied_seats": seat_totals["observed_elected_count"],
                "legal_seats": seat_totals["legal_seat_count"],
                "documented_vacancies": seat_totals["documented_vacancy_count"],
                "reconciled_difference": seat_totals["reconciled_difference"],
                "limits": "Les sièges occupés et les sièges légaux sont présentés séparément.",
            },
            {
                "analysis_id": "president_among_largest_parties_2021",
                "status": "CONDITIONNELLE",
                "scope_communes": int(len(presidency)),
                "president_among_largest": int((presidency["president_among_largest"] == 1).sum()),
                "president_not_among_largest": int((presidency["president_among_largest"] == 0).sum()),
                "unresolved_communes": int(seats["geo_id"].nunique() - len(presidency)),
                "limits": "Périmètre limité aux présidences résolues; les ex aequo de sièges sont admis parmi les plus grands partis.",
            },
            {
                "analysis_id": "hcp_population_context",
                "status": "CONDITIONNELLE",
                "observations": hcp_groups,
                "limits": "2014 peut contextualiser 2015 avec un décalage de -1 an; 2024 ne décrit jamais l'élection de 2015.",
            },
        ],
    }
    validate_reference_analyses(result)
    return result


def validate_reference_analyses(result: dict[str, Any]) -> None:
    analyses = {item["analysis_id"]: item for item in result["analyses"]}
    winners = analyses["winner_transition_2015_2021"]
    if winners["winner_changed"] + winners["winner_retained"] != winners["scope_communes"]:
        raise ReferenceAnalysisError("Les transitions de vainqueur ne se réconcilient pas.")
    turnout = analyses["reported_turnout_change_2015_2021"]
    if turnout["increase"] + turnout["decrease"] + turnout["unchanged"] != turnout["scope_communes"]:
        raise ReferenceAnalysisError("Les variations de participation ne se réconcilient pas.")
    councils = analyses["council_seats_2021"]
    if councils["occupied_seats"] + councils["documented_vacancies"] != councils["legal_seats"]:
        raise ReferenceAnalysisError("Les sièges occupés, vacants et légaux ne se réconcilient pas.")
    if councils["reconciled_difference"] != 0:
        raise ReferenceAnalysisError("La différence réconciliée des sièges doit être nulle.")
    presidencies = analyses["president_among_largest_parties_2021"]
    if presidencies["president_among_largest"] + presidencies["president_not_among_largest"] != presidencies["scope_communes"]:
        raise ReferenceAnalysisError("Les présidences résolues ne se réconcilient pas.")
    if presidencies["scope_communes"] + presidencies["unresolved_communes"] != councils["scope_communes"]:
        raise ReferenceAnalysisError("Le périmètre des présidences ne se réconcilie pas avec les communes.")


def render_text(result: dict[str, Any]) -> str:
    analyses = {item["analysis_id"]: item for item in result["analyses"]}
    winners = analyses["winner_transition_2015_2021"]
    turnout = analyses["reported_turnout_change_2015_2021"]
    councils = analyses["council_seats_2021"]
    presidencies = analyses["president_among_largest_parties_2021"]
    hcp = analyses["hcp_population_context"]
    lines = [
        "ANALYSES DE RÉFÉRENCE — V11",
        f"SHA-256: {result['source_workbook_sha256']}",
        "",
        "1. Alternance communale observée, 2015–2021 [CONDITIONNELLE]",
        f"   {winners['winner_changed']} changements et {winners['winner_retained']} maintiens sur {winners['scope_communes']} communes.",
        f"   Limite: {winners['limits']}",
        "",
        "2. Évolution du taux de participation publié [CONDITIONNELLE]",
        f"   Hausse: {turnout['increase']}; baisse: {turnout['decrease']}; stable: {turnout['unchanged']}.",
        f"   Variation moyenne: {turnout['mean_change_pp']:.4f} points; médiane: {turnout['median_change_pp']:.4f} points.",
        f"   Limite: {turnout['limits']}",
        "",
        "3. Sièges communaux 2021 [AUTORISÉE]",
        f"   {councils['occupied_seats']} sièges occupés + {councils['documented_vacancies']} vacances = {councils['legal_seats']} sièges légaux.",
        f"   Écart réconcilié: {councils['reconciled_difference']}.",
        "",
        "4. Présidence et plus grands partis 2021 [CONDITIONNELLE]",
        f"   Président parmi les partis ex aequo en tête: {presidencies['president_among_largest']} sur {presidencies['scope_communes']} cas résolus.",
        f"   Président hors des partis en tête: {presidencies['president_not_among_largest']}; non résolues: {presidencies['unresolved_communes']}.",
        f"   Limite: {presidencies['limits']}",
        "",
        "5. Contexte démographique HCP [CONDITIONNELLE]",
    ]
    for key, observation in sorted(hcp["observations"].items()):
        lines.append(f"   {key}: {observation['units']} unités; total {observation['total_persons']} personnes.")
    lines.extend((f"   Limite: {hcp['limits']}", ""))
    return "\n".join(lines)


def run(*, data_dir: str | Path | None = None, output_format: str = "text") -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    workbook = get_paths(data_dir).v11_workbook
    if not workbook.is_file():
        print(f"REFERENCE_ANALYSIS_FAILED fichier V11 absent: {workbook}")
        return 2
    try:
        release = json.loads(RELEASE_REPORT.read_text(encoding="utf-8"))
        expected_hash = release["workbooks"]["V11"]
        result = compute_reference_analyses(workbook)
        if result["source_workbook_sha256"] != expected_hash:
            raise ReferenceAnalysisError("L'empreinte du classeur ne correspond pas à la release V11 validée.")
    except (KeyError, OSError, json.JSONDecodeError, ReferenceAnalysisError) as exc:
        print(f"REFERENCE_ANALYSIS_FAILED {exc}")
        return 1
    if output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0
