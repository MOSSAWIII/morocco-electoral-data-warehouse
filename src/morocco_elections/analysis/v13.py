from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import openpyxl

from morocco_elections.config import get_paths
from morocco_elections.legacy.v9.build import rows_from_sheet


def summarize(
    contests: list[dict[str, Any]],
    results: list[dict[str, Any]],
    mobilization: list[dict[str, Any]],
) -> dict[str, Any]:
    contest_by_id = {str(item["contest_id"]): item for item in contests}
    if len(contest_by_id) != len(contests):
        raise ValueError("contest_id dupliqué")
    result_grain = [(str(item["contest_id"]), str(item["party_id"])) for item in results]
    if len(result_grain) != len(set(result_grain)):
        raise ValueError("grain contest_id × party_id dupliqué")
    mobilization_ids = [str(item["contest_id"]) for item in mobilization]
    if len(mobilization_ids) != len(set(mobilization_ids)) or set(mobilization_ids) != set(contest_by_id):
        raise ValueError("mobilisation non conforme au grain contest_id")

    grouped_results: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_contest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for contest in contests:
        grouped_results[(str(contest["election_id"]), str(contest["list_type"]))]
    for row in results:
        contest = contest_by_id[str(row["contest_id"])]
        if str(row["election_id"]) != str(contest["election_id"]):
            raise ValueError("election_id du résultat incompatible avec son contest")
        key = (str(row["election_id"]), str(contest["list_type"]))
        grouped_results[key].append(row)
        by_contest[str(row["contest_id"])].append(row)

    mobilization_by_id = {str(item["contest_id"]): item for item in mobilization}
    scope_rows = []
    top_parties: dict[str, list[dict[str, Any]]] = {}
    competition: dict[str, dict[str, Any]] = {}
    for election_id, list_type in sorted(grouped_results):
        key = f"{election_id}|{list_type}"
        selected = grouped_results[(election_id, list_type)]
        selected_contests = sorted(
            str(item["contest_id"])
            for item in contests
            if str(item["election_id"]) == election_id and str(item["list_type"]) == list_type
        )
        party_totals: Counter[str] = Counter()
        for row in selected:
            party_totals[str(row["party_id"])] += int(row["votes"])
        top_parties[key] = [
            {"party_id": party_id, "observed_votes": votes}
            for party_id, votes in sorted(party_totals.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]

        enp_values: list[float] = []
        margins: list[int] = []
        ties = 0
        for contest_id in selected_contests:
            votes = sorted((int(item["votes"]) for item in by_contest[contest_id]), reverse=True)
            total = sum(votes)
            if total > 0:
                hhi = sum((value / total) ** 2 for value in votes)
                if hhi > 0:
                    enp_values.append(1 / hhi)
            if len(votes) >= 2:
                margins.append(votes[0] - votes[1])
                ties += votes[0] == votes[1]
        competition[key] = {
            "contests": len(selected_contests),
            "mean_enp_observed_votes": round(mean(enp_values), 4) if enp_values else None,
            "mean_top_two_margin_votes": round(mean(margins), 2) if margins else None,
            "top_vote_ties": ties,
        }
        selected_mobilization = [mobilization_by_id[item] for item in selected_contests]
        scope_rows.append(
            {
                "scope_id": key,
                "election_id": election_id,
                "list_type": list_type,
                "contests": len(selected_contests),
                "result_rows": len(selected),
                "parties": len(party_totals),
                "observed_votes": sum(party_totals.values()),
                "registered_voters_available": sum(item.get("registered_voters") is not None for item in selected_mobilization),
                "turnout_rate_available": sum(item.get("turnout_rate") is not None for item in selected_mobilization),
                "valid_votes_available": sum(item.get("valid_votes") is not None for item in selected_mobilization),
                "invalid_vote_rate_available": sum(item.get("invalid_vote_rate") is not None for item in selected_mobilization),
                "historical_boundary_contests": sum(
                    contest_by_id[item]["identity_review_status"] == "boundary_bridge_required"
                    for item in selected_contests
                ),
            }
        )

    return {
        "release": "V13",
        "scope": "six archives qualifiées; législatives 2007–2021 et régionales 2015–2021",
        "counts": {
            "contests": len(contests),
            "results": len(results),
            "mobilization": len(mobilization),
            "elections": len({item["election_id"] for item in contests}),
            "analysis_scopes": len(scope_rows),
        },
        "coverage_by_election_and_list_type": scope_rows,
        "top_parties_by_observed_votes": top_parties,
        "competition": competition,
        "limitations": [
            "Les agrégats de voix sont séparés par élection et type de liste; des électorats différents ne sont jamais additionnés.",
            "Les cellules partisanes absentes de la source sont exclues et ne valent jamais zéro.",
            "ENP et marges sont dérivés uniquement des voix non nulles observées; ils ne sont pas des indicateurs officiels.",
            "Les contests 2007/2011 restent sur leur découpage historique et ne sont pas comparés automatiquement aux territoires actuels.",
            "LEG2002 est exclu du canonique et de ces analyses.",
        ],
    }


def _render(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "V13 — TESTS MÉTIER DU CŒUR ÉLECTORAL",
        f"Périmètre : {report['scope']}",
        (
            f"Volumes : {counts['contests']} contests; {counts['results']} résultats; "
            f"{counts['mobilization']} lignes de mobilisation; {counts['analysis_scopes']} périmètres analytiques."
        ),
        "",
        "COUVERTURE PAR ÉLECTION ET TYPE DE LISTE",
    ]
    for item in report["coverage_by_election_and_list_type"]:
        lines.append(
            f"- {item['scope_id']}: contests={item['contests']}; résultats={item['result_rows']}; "
            f"partis={item['parties']}; voix observées={item['observed_votes']}; "
            f"inscrits={item['registered_voters_available']}/{item['contests']}; "
            f"participation={item['turnout_rate_available']}/{item['contests']}; "
            f"frontières historiques={item['historical_boundary_contests']}."
        )
    lines.extend(["", "COMPÉTITION DÉRIVÉE SUR VOIX OBSERVÉES"])
    for scope_id, item in report["competition"].items():
        lines.append(
            f"- {scope_id}: ENP moyen={item['mean_enp_observed_votes']}; "
            f"marge moyenne={item['mean_top_two_margin_votes']}; égalités en tête={item['top_vote_ties']}."
        )
    lines.extend(["", "LIMITES", *[f"- {item}" for item in report["limitations"]]])
    return "\n".join(lines)


def run(data_dir: str | Path | None = None, output_format: str = "text") -> int:
    workbook_path = get_paths(data_dir).v13_workbook
    if not workbook_path.is_file():
        raise FileNotFoundError(workbook_path)
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    _, contests = rows_from_sheet(workbook["DIM_ELECTORAL_CONTEST"])
    _, results = rows_from_sheet(workbook["FACT_ELECTION_RESULT"])
    _, mobilization = rows_from_sheet(workbook["FACT_ELECTORAL_MOBILIZATION"])
    workbook.close()
    report = summarize(contests, results, mobilization)
    print(json.dumps(report, ensure_ascii=False, indent=2) if output_format == "json" else _render(report))
    return 0
