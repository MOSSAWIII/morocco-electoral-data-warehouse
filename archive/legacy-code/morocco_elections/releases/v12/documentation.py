from __future__ import annotations

from pathlib import Path

from morocco_elections.config import get_paths
from morocco_elections.legacy.v9 import documentation as base
from morocco_elections.releases.v11 import documentation as v11


def configure_paths(data_dir: str | Path | None = None) -> None:
    paths = get_paths(data_dir)
    base.WORKBOOK = paths.v12_workbook
    base.OUTPUT_DIR = paths.documentation_v12
    base.VERSION = "V12"
    base.AUDIT_SHEET = "WORKBOOK_AUDIT_V12"
    base.STATUS_LEGEND = base.STATUS_LEGEND.replace("V9", "V12").replace("V10", "V12").replace("V11", "V12")


def _adapt(docs: dict[str, str], model: dict) -> dict[str, str]:
    # V11's adapter reapplies the V10 delta before adding its own.
    adapted = v11._adapt(docs, model)
    adapted[base.DOCUMENTS[0]] += """

ÉTAT V12 — ACTIVITÉ PARLEMENTAIRE
OBSERVÉ: 5 589 questions parlementaires écrites issues de quatre ressources officielles
du cycle 2023–2024. 5 453 lignes sont raccordées exactement à une identité V11;
136 restent non raccordées et aucune correspondance floue n'est appliquée.
PÉRIMÈTRE PARTIEL: les questions orales et les autres périodes ne sont pas incluses.
"""
    adapted[base.DOCUMENTS[2]] += """

FAIT PARLEMENTAIRE V12
Table: PARLIAMENTARY_QUESTIONS.
Grain: source_id × source_question_number, matérialisé par question_id.
Dimensions autorisées: person_id et party_id seulement lorsqu'un raccord exact existe,
date de dépôt, période source et ministère destinataire. Le nombre de questions est additif
sur des ensembles de question_id disjoints; il ne prouve ni présence ni assiduité.
"""
    adapted[base.DOCUMENTS[8]] += """

ACTIVITÉ PARLEMENTAIRE V12
OBSERVÉ: nom public du député, groupe, ministère, sujet, texte, date de dépôt et valeur
de réponse tels que publiés. DÉRIVÉ: response_status dépend seulement de la présence
d'une date de réponse. person_id est NULL pour 136 lignes sans égalité Unicode exacte.
Jointure autorisée: PARLIAMENTARY_QUESTIONS.person_id → DIM_PERSON.person_id.
Jointure interdite: nom seul, rapprochement flou ou transfert de parti hors période.
"""
    adapted[base.DOCUMENTS[11]] += """

LINEAGE V12
Quatre XLSX officiels data.gov.ma → contrôle de schéma et de grain → raccord Unicode exact
aux mandats 2021–2026 → PARLIAMENTARY_QUESTIONS → export Excel. Les RAW restent hors Git.
La release est reconstruite depuis V8 + RAW + décisions versionnées, sans lire V9, V10 ou V11.
"""
    adapted[base.DOCUMENTS[12]] += """

RÈGLES DE JOINTURE PARLEMENTAIRE V12
- question_id est unique et obligatoire.
- person_id est optionnel et référence DIM_PERSON lorsqu'il est présent.
- party_id est hérité du mandat 2021–2026 uniquement pour les identités raccordées.
- source_id référence SOURCES; source_question_number n'est unique qu'à l'intérieur de source_id.
- les 136 lignes non raccordées restent analysables par question mais pas par trajectoire individuelle.
"""
    adapted[base.DOCUMENTS[13]] += """

MÉTRIQUES PARLEMENTAIRES V12
question_count = COUNT(DISTINCT question_id) dans un périmètre source déclaré.
answered_question_count = COUNT(DISTINCT question_id) où response_date n'est pas NULL.
response_rate = 100 × answered_question_count / question_count; NULL si question_count=0.
Ces métriques sont DÉRIVÉES et ne deviennent jamais des indicateurs officiels.
"""
    return adapted


def _validate(model: dict, docs: dict[str, str], before_hash: str) -> None:
    errors: list[str] = []
    if len(model["sheets"]) != 68:
        errors.append(f"68 onglets attendus, obtenu {len(model['sheets'])}")
    if set(model["audit"]) != set(model["sheets"]) - {"WORKBOOK_AUDIT_V12"}:
        errors.append("WORKBOOK_AUDIT_V12 n'est pas exhaustif")
    expected = {
        "PARLIAMENTARY_QUESTIONS": 5_589,
        "FACT_OBSERVATION": 3_203,
        "LOCAL_MANDATES": 32_513,
        "PARLIAMENTARY_MANDATES": 1_654,
        "COMMUNE_ELECTION_PANEL": 3_076,
        "ELECTORAL_TRANSITIONS_2015_2021": 14_555,
        "ANALYTICAL_PANEL": 22_054,
        "DIM_PERSON": 33_697,
    }
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
    for phrase in [
        "5 589 questions parlementaires écrites",
        "5 453 lignes",
        "136 restent non raccordées",
        "PÉRIMÈTRE PARTIEL",
        "COUNT(DISTINCT question_id)",
    ]:
        if phrase not in corpus:
            errors.append(f"Règle V12 absente: {phrase}")
    for name, content in docs.items():
        for token in ["VERSION", "CLASSEUR SOURCE", "DATE DE GÉNÉRATION", "PÉRIMÈTRE", "RENVOIS"]:
            if token not in content:
                errors.append(f"Métadonnée absente de {name}: {token}")
        if len(content.strip()) < 500:
            errors.append(f"Document trop court: {name}")
    if before_hash != base.sha256(base.WORKBOOK):
        errors.append("Le classeur V12 a changé pendant la documentation")
    if errors:
        raise RuntimeError("ÉCHEC DOCUMENTATION V12\n- " + "\n- ".join(errors))


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
    print(f"DOCUMENTATION_OK version=V12 files=15 output={base.OUTPUT_DIR}")
    print(f"WORKBOOK_SHA256={before}")


if __name__ == "__main__":
    main()
