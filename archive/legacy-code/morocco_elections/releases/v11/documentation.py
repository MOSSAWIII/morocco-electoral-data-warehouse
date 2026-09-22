from __future__ import annotations

from pathlib import Path

from morocco_elections.config import get_paths
from morocco_elections.legacy.v9 import documentation as base
from morocco_elections.releases.v10 import documentation as v10


def configure_paths(data_dir: str | Path | None = None) -> None:
    paths = get_paths(data_dir)
    base.WORKBOOK = paths.v11_workbook
    base.OUTPUT_DIR = paths.documentation_v11
    base.VERSION = "V11"
    base.AUDIT_SHEET = "WORKBOOK_AUDIT_V11"
    base.STATUS_LEGEND = base.STATUS_LEGEND.replace("V9", "V11").replace("V10", "V11")


def _adapt(docs: dict[str, str], model: dict) -> dict[str, str]:
    adapted = v10._adapt(docs, model)
    adapted[base.DOCUMENTS[0]] += """

ÉTAT V11-HCP
OBSERVÉ: 1 538 populations légales 2014 et 1 538 populations municipales 2024
sont ajoutées à FACT_OBSERVATION. Les 25 autres décisions V10-QA-3 restent NO_GO.
La population légale 2024 de POPULATION concorde cellule par cellule avec la nouvelle
publication officielle et n'est pas dupliquée dans FACT_OBSERVATION.
"""
    adapted[base.DOCUMENTS[2]] += """

CUBE HCP V11
Grain: geo_id × time_id × metric_id dans FACT_OBSERVATION.
Mesures OBSERVÉES: population_legal en 2014 et population_municipal en 2024.
La mesure est additive géographiquement uniquement dans le périmètre des 1 538 unités
analytiques; elle n'est jamais additive entre millésimes.
"""
    adapted[base.DOCUMENTS[10]] += """

APPORT V11-HCP
- OBSERVÉ: population_legal 2014, 1 538/1 538 unités, total 33 848 242.
- OBSERVÉ: population_municipal 2024, 1 538/1 538 unités, total 36 490 591.
- CONTRÔLE: population_legal 2024, 1 538 valeurs identiques à POPULATION, total 36 828 330.
- BLOQUÉ: les 25 autres couples indicateur-millésime qualifiés NO_GO ne sont pas ingérés.
"""
    adapted[base.DOCUMENTS[11]] += """

LINEAGE V11-HCP
RAW HCP officiels locaux → raccordement exact V10 → gate V10-QA-3 → FACT_OBSERVATION.
Les classeurs RAW restent hors Git. Aucun RAW n'est embarqué dans une nouvelle feuille.
"""
    adapted[base.DOCUMENTS[12]] += """

JOINTURE HCP V11
Clé autorisée: FACT_OBSERVATION.geo_id → DIM_GEO.geo_id et time_id → DIM_TIME.time_id.
Cardinalité attendue: 1 538 lignes par metric_id × time_id.
Interdit: jointure sur le nom, remplacement silencieux de l'année d'observation ou
propagation automatique dans les panels électoraux.
"""
    adapted[base.DOCUMENTS[13]] += """

RÈGLES TEMPORELLES V11-HCP
- 2014 vers élection 2015: CONDITIONNELLE, référence antérieure d'un an.
- 2024 vers élection 2015: INTERDITE.
- 2014 ou 2024 vers élection 2021: CONDITIONNELLE avec année et distance explicites.
- Aucune interpolation et aucune valeur artificiellement qualifiée de « 2021 ».
"""
    return adapted


def _validate(model: dict, docs: dict[str, str], before_hash: str) -> None:
    errors: list[str] = []
    if len(model["sheets"]) != 67:
        errors.append(f"67 onglets attendus, obtenu {len(model['sheets'])}")
    if set(model["audit"]) != set(model["sheets"]) - {"WORKBOOK_AUDIT_V11"}:
        errors.append("WORKBOOK_AUDIT_V11 n'est pas exhaustif")
    expected = {
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
        "population_legal 2014",
        "population_municipal 2024",
        "33 848 242",
        "36 490 591",
        "25 autres",
        "2024 vers élection 2015: INTERDITE",
    ]:
        if phrase not in corpus:
            errors.append(f"Règle V11 absente: {phrase}")
    for name, content in docs.items():
        for token in ["VERSION", "CLASSEUR SOURCE", "DATE DE GÉNÉRATION", "PÉRIMÈTRE", "RENVOIS"]:
            if token not in content:
                errors.append(f"Métadonnée absente de {name}: {token}")
        if len(content.strip()) < 500:
            errors.append(f"Document trop court: {name}")
    if before_hash != base.sha256(base.WORKBOOK):
        errors.append("Le classeur V11 a changé pendant la documentation")
    if errors:
        raise RuntimeError("ÉCHEC DOCUMENTATION V11\n- " + "\n- ".join(errors))


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
    print(f"DOCUMENTATION_OK version=V11 files=15 output={base.OUTPUT_DIR}")
    print(f"WORKBOOK_SHA256={before}")


if __name__ == "__main__":
    main()
