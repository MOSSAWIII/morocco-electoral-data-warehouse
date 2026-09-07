from __future__ import annotations

from pathlib import Path

from morocco_elections.config import get_paths
from morocco_elections.legacy.v9 import documentation as base


IDENTITY_OLD = """- BLOQUÉ: l'identité locale V10 n'est pas commune + personne en pratique. Les
  32 513 mandats portent seulement 1 538 person_id, soit un identifiant par commune.
- L'identité parlementaire"""
IDENTITY_NEW = """- DÉRIVÉ: V10 porte 32 512 person_id locaux déterministes pour 32 513 observations.
- La portée reste source + commune + circonscription + parti + nom Unicode normalisé;
  aucune égalité de nom ne prouve une identité inter-circonscription.
- Les 44 groupes nom-commune ambigus sont conservés dans IDENTITY_AUDIT_V10.
- L'identité parlementaire"""


def configure_paths(data_dir: str | Path | None = None) -> None:
    paths = get_paths(data_dir)
    base.WORKBOOK = paths.v10_workbook
    base.OUTPUT_DIR = paths.documentation_v10
    base.VERSION = "V10"
    base.AUDIT_SHEET = "WORKBOOK_AUDIT_V10"
    base.STATUS_LEGEND = base.STATUS_LEGEND.replace("V9", "V10")


def _adapt(docs: dict[str, str], model: dict) -> dict[str, str]:
    adapted = {name: content.replace("V9", "V10").replace("64 onglets", "67 onglets") for name, content in docs.items()}
    for name, content in adapted.items():
        content = content.replace(IDENTITY_OLD, IDENTITY_NEW)
        content = content.replace("cinq unités\nuniques encore signalées pour revue explicite", "cinq unités\nuniques validées manuellement par code officiel et parent administratif")
        content = content.replace("UNITÉS À REVOIR\n", "UNITÉS VALIDÉES\nVoir MANUAL_RESOLUTIONS_V10: cinq décisions géographiques, dix lignes élection-spécifiques, confiance 1.0.\n")
        content = content.replace("- BLOQUÉ: le person_id local V10 est un proxy communal, pas une identité d'élu;\n  les analyses individuelles doivent utiliser les lignes RAW en attendant sa correction.", "- DÉRIVÉ: le person_id local V10 est Unicode, déterministe et de portée prudente;\n  toute analyse doit respecter source+commune+circonscription+parti.")
        content = content.replace("- Personne : person_id, stable pour les députés TAFRA; BLOQUÉ au niveau local car\n  la clé V10 actuelle se réduit à un proxy communal.", "- Personne : person_id, stable pour les députés TAFRA et déterministe au niveau local;\n  sa portée locale prudente interdit les rapprochements sans preuve externe.")
        content = content.replace("Les effectifs d'élus peuvent être additionnés par parti puis commune, sous réserve\ndes deux écarts de siège documentés en QA.", "Les effectifs observés sont additionnables par parti. Deux vacances documentées\nexpliquent l'écart brut de deux sièges; le total réconcilié est exact.")
        content = content.replace("BLOQUÉ: deux communes ont 15 lignes d'élus pour 16 sièges attendus", "OBSERVÉ: deux communes ont 15 élus pour 16 sièges légaux; une vacance documentée réconcilie chacune")
        content = content.replace("person_id local a la forme TAFRA_LOCAL_2021_<idCommune>_<hash>.", "person_id local a la forme PERS_LOCAL_V10_<sha256-128>.")
        content = content.replace("LOCAL_MANDATES: local_mandate_id uniquement. person_id local V10 n'est pas une clé\nd'individu et ne doit pas servir de clé analytique.", "LOCAL_MANDATES: local_mandate_id identifie l'observation; person_id identifie une\npersonne prudente dans sa portée documentée, jamais au-delà sans preuve.")
        content = content.replace("- person_id de LOCAL_MANDATES utilisé comme identité d'élu;", "- person_id local utilisé au-delà de sa portée source+commune+circonscription+parti;")
        content = content.replace("ALERTE IDENTITÉ: BLOQUÉ — 32 513 lignes mais 1 538 person_id, un par commune; utiliser local_mandate_id pour l'unicité de ligne.", "IDENTITÉ DÉRIVÉE: 32 513 observations, 32 512 person_id prudents; utiliser local_mandate_id pour l'unicité de ligne.")
        content = content.replace("ALERTE IDENTITÉ: les 1 538 entrées TAFRA_LOCAL_2021_* sont des proxies communaux, pas des élus distincts.", "IDENTITÉ DÉRIVÉE: 32 512 entrées PERS_LOCAL_V10_*; portée conservatrice documentée.")
        content = content.replace("1 538 proxies locaux communaux. Les proxies locaux ne sont pas des personnes uniques.", "32 512 identités locales prudentes. Elles ne constituent pas une identité nationale.")
        marker = "\nRENVOIS"
        addendum = "\nRÈGLES V10\n- Les valeurs RAW restent OBSERVÉES et inchangées.\n- Les noms normalisés, person_id, parts et réconciliations sont DÉRIVÉS.\n- Les cinq crosswalks et deux vacances portent une décision et une preuve dans MANUAL_RESOLUTIONS_V10.\n"
        if addendum not in content and marker in content:
            pass
        adapted[name] = content

    # Replace the detailed identity section, whose V9 prose is intentionally explicit.
    identity = adapted[base.DOCUMENTS[8]]
    start = identity.index("DIM_PERSON\n")
    end = identity.index("\nPARLIAMENTARY_MANDATES\n")
    identity_section = f"""DIM_PERSON
OBSERVÉ/DÉRIVÉ: {model['sheets']['DIM_PERSON']['rows']} lignes, dont 1 185 identités parlementaires
et 32 512 identités locales prudentes.

LOCAL_MANDATES
OBSERVÉ: 32 513 observations d'élus locaux; local_mandate_id reste la clé de ligne.
DÉRIVÉ: person_name_normalized et person_name_match_key sont calculés sans écraser
person_name_ar. person_id est le SHA-256 tronqué de la portée source + commune +
circonscription + parti + nom Unicode normalisé.
OBSERVÉ: une identité Bni Makada est liée à deux observations RAW conservées.
DÉRIVÉ: 44 groupes nom-commune ambigus sont audités sans fusion spéculative.
INTERDIT: utiliser le nom seul ou étendre person_id hors de sa portée documentée.
"""
    adapted[base.DOCUMENTS[8]] = identity[:start] + identity_section + identity[end:]

    adapted[base.DOCUMENTS[0]] += "\nÉTAT V10\nLes cinq variantes géographiques et les deux écarts de sièges sont résolus avec preuve. Restent BLOQUÉS: nInscrits, sièges 2015, 135 présidences et historique partisan parlementaire complet.\n"
    adapted[base.DOCUMENTS[5]] += "\nDÉCISIONS V10\nCinq unités géographiques, dix lignes élection-spécifiques: validated_manual, confidence_score=1.0. Les graphies historiques restent des alias.\n"
    adapted[base.DOCUMENTS[9]] += "\nRÉCONCILIATION V10\nidCommune 770: 15 élus + 1 vacance documentée = 16 sièges légaux.\nidCommune 817: 15 élus + 1 vacance documentée = 16 sièges légaux.\nDifférence observée: -2. Différence réconciliée: 0. Aucun élu n'est imputé.\n"
    adapted[base.DOCUMENTS[12]] += "\nCARDINALITÉS V10\nIDENTITY_AUDIT_V10: audit_id unique; 44 groupes.\nMANUAL_RESOLUTIONS_V10: resolution_id unique; 7 décisions.\nCOUNCIL_SEAT_STATUS_V10: source_idcommune unique; 1 538 communes.\n"
    adapted[base.DOCUMENTS[13]] += "\nMÉTRIQUE: party_seat_share_legal\nFORMULE: 100 × party_seats / legal_seat_count\nDÉNOMINATEUR/PÉRIMÈTRE: sièges légaux publiés de la commune\nRÈGLE NULL: NULL si legal_seat_count est NULL ou 0\nSTATUT: DÉRIVÉ\n"
    adapted[base.DOCUMENTS[14]] = adapted[base.DOCUMENTS[14]].replace("Inventaire exhaustif des 64", "Inventaire exhaustif des 67")
    return adapted


def _validate(model: dict, docs: dict[str, str], before_hash: str) -> None:
    errors = []
    if len(model["sheets"]) != 67:
        errors.append(f"67 onglets attendus, obtenu {len(model['sheets'])}")
    if set(model["audit"]) != set(model["sheets"]) - {"WORKBOOK_AUDIT_V10"}:
        errors.append("WORKBOOK_AUDIT_V10 n'est pas exhaustif")
    expected = {"LOCAL_MANDATES": 32513, "PARLIAMENTARY_MANDATES": 1654, "COMMUNE_ELECTION_PANEL": 3076, "ELECTORAL_TRANSITIONS_2015_2021": 14555, "ANALYTICAL_PANEL": 22054, "DIM_PERSON": 33697, "IDENTITY_AUDIT_V10": 44, "MANUAL_RESOLUTIONS_V10": 7, "COUNCIL_SEAT_STATUS_V10": 1538}
    for sheet, rows in expected.items():
        if model["sheets"][sheet]["rows"] != rows:
            errors.append(f"{sheet}: {model['sheets'][sheet]['rows']} au lieu de {rows}")
    catalog = docs[base.DOCUMENTS[14]]
    for sheet, data in model["sheets"].items():
        if f"ONGLET: {sheet}" not in catalog:
            errors.append(f"Onglet absent du catalogue: {sheet}")
        for column in data["headers"]:
            if sheet not in {"README", "RAW_HCP_RGPH2024_FULL"} and str(column) not in catalog:
                errors.append(f"Colonne absente du catalogue: {sheet}.{column}")
    corpus = "\n".join(docs.values())
    for phrase in ["32 512", "44 groupes", "idCommune 770", "idCommune 817", "135 présidences", "sièges 2015", "nInscrits", "Différence réconciliée: 0"]:
        if phrase not in corpus:
            errors.append(f"Règle V10 absente: {phrase}")
    for name, content in docs.items():
        for token in ["VERSION", "CLASSEUR SOURCE", "DATE DE GÉNÉRATION", "PÉRIMÈTRE", "RENVOIS"]:
            if token not in content:
                errors.append(f"Métadonnée absente de {name}: {token}")
        if len(content.strip()) < 500:
            errors.append(f"Document trop court: {name}")
    if before_hash != base.sha256(base.WORKBOOK):
        errors.append("Le classeur V10 a changé pendant la documentation")
    if errors:
        raise RuntimeError("ÉCHEC DOCUMENTATION V10\n- " + "\n- ".join(errors))


def main(data_dir: str | Path | None = None) -> None:
    configure_paths(data_dir)
    if not base.WORKBOOK.exists():
        raise FileNotFoundError(base.WORKBOOK)
    before = base.sha256(base.WORKBOOK)
    model = base.load_model()
    docs, _ = base.build_docs(model)
    docs = _adapt(docs, model)
    _validate(model, docs, before)
    base.write_documents(docs)
    print(f"DOCUMENTATION_OK version=V10 files=15 output={base.OUTPUT_DIR}")
    print(f"WORKBOOK_SHA256={before}")


if __name__ == "__main__":
    main()
