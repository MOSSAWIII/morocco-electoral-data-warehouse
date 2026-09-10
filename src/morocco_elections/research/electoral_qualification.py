from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from morocco_elections.config import PROJECT_ROOT


PROFILE_PATH = PROJECT_ROOT / "metadata" / "v13_electoral_sources_profile.json"
REGISTRY_PATH = PROJECT_ROOT / "metadata" / "v13_identity_registry.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "metadata" / "v13_electoral_qualification.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "research" / "V13_ELECTORAL_QUALIFICATION.txt"

MEASURE_IDS = (
    "party_votes",
    "contest_seats",
    "registered_voters",
    "turnout_rate",
    "valid_votes",
    "invalid_vote_rate",
    "representative_profile",
)

# This is a qualification of the physical fields already profiled, not a repair or
# an imputation. A GO always applies only to directly published, non-null values.
SOURCE_RULES = {
    "LEG2002": {
        "decision": "NO_GO",
        "go": set(),
        "reason": "Archive incomplète et contradictoire selon sa propre notice; conservation documentaire uniquement.",
    },
    "LEG2007": {
        "decision": "GO",
        "go": {"party_votes", "contest_seats", "registered_voters", "turnout_rate", "invalid_vote_rate"},
        "reason": "Valeurs publiées exploitables dans le périmètre local historique, sans imputation des cellules vides.",
    },
    "LEG2011": {
        "decision": "GO",
        "go": {"party_votes", "contest_seats", "registered_voters", "turnout_rate", "invalid_vote_rate"},
        "reason": "Valeurs publiées structurellement cohérentes; provenance secondaire à conserver dans chaque fait.",
    },
    "LEG2016": {
        "decision": "GO",
        "go": {"party_votes", "contest_seats", "turnout_rate"},
        "reason": "Votes et mesures publiées utilisables; inscrits et pourcentage de votes nuls absents.",
    },
    "LEG2021": {
        "decision": "GO",
        "go": {"party_votes", "contest_seats", "turnout_rate"},
        "reason": "Votes, sièges et participation publiés utilisables; inscrits absents et champ invalide non publié.",
    },
    "REG2015": {
        "decision": "GO",
        "go": {"party_votes", "contest_seats", "turnout_rate", "valid_votes"},
        "reason": "Votes, sièges, participation et suffrages valides publiés et structurellement cohérents.",
    },
    "REG2021": {
        "decision": "GO",
        "go": {"party_votes", "contest_seats", "turnout_rate"},
        "reason": "Votes, sièges et participation publiés utilisables; inscrits et votes invalides absents.",
    },
}

FIELD_MAP = {
    "party_votes": "colonnes de codes partisans",
    "contest_seats": "nSieges",
    "registered_voters": "nInscrits",
    "turnout_rate": "txParticipation",
    "valid_votes": "nValides",
    "invalid_vote_rate": "pctNuls",
    "representative_profile": "repPctFemmes et répartitions âge/éducation",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_qualification(as_of: str, baseline: str = "v12") -> dict:
    date.fromisoformat(as_of)
    if baseline.lower() != "v12":
        raise ValueError("La baseline doit être v12")
    profile = _load(PROFILE_PATH)
    registry = _load(REGISTRY_PATH)
    profiles = {item["election_id"]: item for item in profile["profiles"]}
    source_ids = {item["source_id"] for item in profile["profiles"]}

    decisions = []
    measure_decisions = []
    for election_id, rule in SOURCE_RULES.items():
        item = profiles[election_id]
        source_id = item["source_id"]
        crosswalks = [entry for entry in registry["crosswalks"] if entry["source_system"] == source_id]
        contests = [entry for entry in registry["contests"] if entry["source_system"] == source_id]
        status_counts = dict(sorted(Counter(entry["review_status"] for entry in crosswalks).items()))
        historical_boundary = any(entry["review_status"] == "boundary_bridge_required" for entry in crosswalks)
        party_review = sum(
            entry["entity_type"] == "party_or_alliance" and entry["review_status"] == "manual_review_required"
            for entry in crosswalks
        )
        restrictions = []
        if historical_boundary:
            restrictions.append("Les faits restent attachés au découpage historique; comparaison avec le découpage actuel interdite sans bridge validé.")
        if party_review:
            restrictions.append(
                f"{party_review} codes partisans restent provisoires; ils sont conservés séparément et ne doivent pas être fusionnés implicitement."
            )
        if item["party_null_cells"]:
            restrictions.append(
                f"{item['party_null_cells']} cellules partisanes vides restent NULL et ne signifient jamais zéro."
            )
        if item["seat_scope_gap"]:
            restrictions.append(
                f"Le total nSieges couvre {item['seat_total_in_file']} sièges publiés, soit {item['seat_scope_gap']} de moins que le total national V12."
            )
        if election_id == "LEG2011":
            restrictions.append("La source n'est pas une publication officielle primaire; sa provenance secondaire doit rester visible.")
        if election_id == "LEG2002":
            restrictions.extend(item["limitations"])

        decisions.append(
            {
                "source_id": source_id,
                "election_id": election_id,
                "decision": rule["decision"],
                "source_rows": item["rows"],
                "contest_count": len(contests),
                "crosswalk_count": len(crosswalks),
                "crosswalk_review_statuses": status_counts,
                "evidence_sha256": item["sha256"],
                "reason": rule["reason"],
                "restrictions": restrictions,
            }
        )
        for measure_id in MEASURE_IDS:
            go = rule["decision"] == "GO" and measure_id in rule["go"]
            reason = _measure_reason(election_id, measure_id, item, go)
            measure_decisions.append(
                {
                    "source_id": source_id,
                    "election_id": election_id,
                    "measure_id": measure_id,
                    "source_field": FIELD_MAP[measure_id],
                    "decision": "GO" if go else "NO_GO",
                    "null_policy": "Conserver NULL; aucune reconstruction et aucune conversion implicite en zéro.",
                    "reason": reason,
                }
            )

    go_scopes = [
        {
            "source_id": decision["source_id"],
            "election_id": decision["election_id"],
            "measures": [
                item["measure_id"]
                for item in measure_decisions
                if item["source_id"] == decision["source_id"] and item["decision"] == "GO"
            ],
        }
        for decision in decisions
        if decision["decision"] == "GO"
    ]
    return {
        "schema_version": 1,
        "phase": "V13_ELECTORAL_QUALIFICATION",
        "baseline_release": "V12",
        "as_of": as_of,
        "scope": "Qualification groupée des sept archives électorales déjà acquises et profilées.",
        "decision_vocabulary": ["GO", "NO_GO"],
        "source_count": len(decisions),
        "counts": {
            "go_sources": sum(item["decision"] == "GO" for item in decisions),
            "no_go_sources": sum(item["decision"] == "NO_GO" for item in decisions),
            "go_measure_scopes": sum(item["decision"] == "GO" for item in measure_decisions),
            "no_go_measure_scopes": sum(item["decision"] == "NO_GO" for item in measure_decisions),
        },
        "evidence": {
            "source_profile": str(PROFILE_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "identity_registry": str(REGISTRY_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "acquisition_source_ids": sorted(source_ids),
        },
        "source_decisions": decisions,
        "measure_decisions": measure_decisions,
        "authorized_for_future_ingestion": go_scopes,
        "ingestion_executed": False,
        "global_restrictions": [
            "LEG2002 reste ARCHIVE_ONLY et ne rejoint pas les faits canoniques.",
            "Les cellules partisanes vides restent inconnues; elles ne valent pas zéro.",
            "Les géographies 2007 et 2011 restent des snapshots historiques sans équivalence territoriale actuelle implicite.",
            "nSieges décrit la capacité publiée du contest, pas une attribution de sièges par parti.",
            "Un taux de participation publié ne permet pas de reconstruire un nombre d'inscrits ou de votants.",
            "Les profils de représentants régionaux 2021 nécessitent un profil dédié avant toute intégration.",
        ],
        "next_step": "Construire V13 uniquement avec les mesures GO, puis tester les cubes au grain contest × parti × élection.",
    }


def _measure_reason(election_id: str, measure_id: str, profile: dict, go: bool) -> str:
    if election_id == "LEG2002":
        return "Source classée ARCHIVE_ONLY; aucune mesure n'est admise dans le canonique."
    if go:
        if measure_id == "party_votes" and profile["party_null_cells"]:
            return "Valeurs non nulles directement publiées; les cellules vides sont exclues de toute agrégation exigeant des zéros explicites."
        if measure_id == "contest_seats" and profile["seat_scope_gap"]:
            return "Capacité des contests renseignés uniquement; le total national complet ne doit pas être déduit de cette source."
        if measure_id == "valid_votes":
            return "nValides est publié et égale exactement la somme des voix partisanes sur toutes les lignes comparées."
        return "Champ directement publié, non vide et structurellement valide dans le profil consolidé."
    missing = set(profile["completely_empty_columns"])
    if measure_id == "registered_voters" and "nInscrits" in missing:
        return "nInscrits est entièrement vide."
    if measure_id == "invalid_vote_rate" and ({"pctNuls", "invalide"} & missing or "invalide" in profile["constant_zero_columns"]):
        return "Champ absent, vide ou zéro technique déclaré non publié par la notice."
    if measure_id == "valid_votes" and profile["valid_vote_reconciliation"] is None:
        return "Aucun champ de suffrages valides directement qualifié dans cette source."
    if measure_id == "representative_profile":
        return "Hors du noyau électoral; un profil de domaine et de précision est encore requis."
    return "Mesure non directement publiée ou sémantique insuffisamment qualifiée."


def validate_qualification(qualification: dict) -> list[str]:
    errors = []
    if qualification.get("schema_version") != 1 or qualification.get("phase") != "V13_ELECTORAL_QUALIFICATION":
        errors.append("métadonnées racine invalides")
    if qualification.get("baseline_release") != "V12" or qualification.get("ingestion_executed") is not False:
        errors.append("baseline ou état d'ingestion invalide")
    sources = qualification.get("source_decisions", [])
    measures = qualification.get("measure_decisions", [])
    if len(sources) != 7 or len({item.get("source_id") for item in sources}) != 7:
        errors.append("sept décisions source uniques sont requises")
    expected_measure_count = 7 * len(MEASURE_IDS)
    measure_keys = [(item.get("source_id"), item.get("measure_id")) for item in measures]
    if len(measures) != expected_measure_count or len(set(measure_keys)) != expected_measure_count:
        errors.append(f"{expected_measure_count} décisions de mesure uniques sont requises")
    allowed = {"GO", "NO_GO"}
    if any(item.get("decision") not in allowed for item in sources + measures):
        errors.append("décision hors vocabulaire")
    source_ids = {item.get("source_id") for item in sources}
    if any(item.get("source_id") not in source_ids for item in measures):
        errors.append("mesure rattachée à une source inconnue")
    counts = qualification.get("counts", {})
    expected_counts = {
        "go_sources": sum(item.get("decision") == "GO" for item in sources),
        "no_go_sources": sum(item.get("decision") == "NO_GO" for item in sources),
        "go_measure_scopes": sum(item.get("decision") == "GO" for item in measures),
        "no_go_measure_scopes": sum(item.get("decision") == "NO_GO" for item in measures),
    }
    if counts != expected_counts or expected_counts != {
        "go_sources": 6,
        "no_go_sources": 1,
        "go_measure_scopes": 23,
        "no_go_measure_scopes": 26,
    }:
        errors.append("compteurs de décision incohérents")
    go_sources = {item["source_id"] for item in sources if item["decision"] == "GO"}
    authorized = qualification.get("authorized_for_future_ingestion", [])
    if {item.get("source_id") for item in authorized} != go_sources:
        errors.append("périmètre d'ingestion future incohérent")
    authorized_measures = {
        (item.get("source_id"), measure_id)
        for item in authorized
        for measure_id in item.get("measures", [])
    }
    expected_authorized_measures = {
        (item.get("source_id"), item.get("measure_id")) for item in measures if item.get("decision") == "GO"
    }
    if authorized_measures != expected_authorized_measures:
        errors.append("liste des mesures autorisées incohérente avec les décisions")
    if any(not item.get("reason") for item in sources + measures):
        errors.append("chaque décision doit être motivée")
    return errors


def render_report(qualification: dict) -> str:
    lines = [
        "V13 — QUALIFICATION GROUPÉE DES ARCHIVES ÉLECTORALES",
        "",
        f"Baseline : {qualification['baseline_release']}",
        f"Date d'observation : {qualification['as_of']}",
        "Ingestion exécutée : NON",
        f"Décisions source : {qualification['counts']['go_sources']} GO / {qualification['counts']['no_go_sources']} NO_GO",
        f"Périmètres de mesure : {qualification['counts']['go_measure_scopes']} GO / {qualification['counts']['no_go_measure_scopes']} NO_GO",
        "",
        "DÉCISIONS PAR SOURCE",
        "",
    ]
    for item in qualification["source_decisions"]:
        lines.append(
            f"- {item['election_id']} ({item['source_id']}) : {item['decision']} — {item['reason']}"
        )
        for restriction in item["restrictions"]:
            lines.append(f"  Limite : {restriction}")
    lines.extend(["", "MESURES AUTORISÉES POUR UNE INGESTION FUTURE", ""])
    for item in qualification["authorized_for_future_ingestion"]:
        lines.append(f"- {item['election_id']} : {', '.join(item['measures'])}")
    lines.extend(["", "RÈGLES NON NÉGOCIABLES", ""])
    lines.extend(f"- {item}" for item in qualification["global_restrictions"])
    lines.extend(["", "PROCHAINE ÉTAPE", "", qualification["next_step"], ""])
    return "\n".join(lines)


def generate(
    as_of: str,
    baseline: str = "v12",
    output: str | Path | None = None,
    report_output: str | Path | None = None,
) -> int:
    qualification = build_qualification(as_of, baseline)
    errors = validate_qualification(qualification)
    if errors:
        print("ELECTORAL_QUALIFICATION_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    output_path = Path(output) if output else DEFAULT_OUTPUT
    report_path = Path(report_output) if report_output else DEFAULT_REPORT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(qualification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(qualification), encoding="utf-8")
    print(
        f"ELECTORAL_QUALIFICATION_OK go_sources={qualification['counts']['go_sources']} "
        f"go_measure_scopes={qualification['counts']['go_measure_scopes']} output={output_path}"
    )
    return 0
