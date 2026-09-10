from __future__ import annotations

from pathlib import Path

from morocco_elections.config import get_paths
from morocco_elections.legacy.v9 import documentation as base
from morocco_elections.releases.v12 import documentation as v12


def configure_paths(data_dir: str | Path | None = None) -> None:
    paths = get_paths(data_dir)
    base.WORKBOOK = paths.v13_workbook
    base.OUTPUT_DIR = paths.documentation_v13
    base.VERSION = "V13"
    base.AUDIT_SHEET = "WORKBOOK_AUDIT_V13"
    for previous in ("V9", "V10", "V11", "V12"):
        base.STATUS_LEGEND = base.STATUS_LEGEND.replace(previous, "V13")


def _adapt(docs: dict[str, str], model: dict) -> dict[str, str]:
    adapted = v12._adapt(docs, model)
    adapted[base.DOCUMENTS[0]] += """

ÉTAT V13 — CŒUR ÉLECTORAL MULTI-SCRUTINS
OBSERVÉ: 639 courses électorales, 10 883 résultats contest × parti et 639 lignes de
mobilisation provenant de six archives qualifiées. Les législatives 2007, 2011, 2016,
2021 et les régionales 2015, 2021 rejoignent le canonique dans leurs seuls périmètres GO.
ARCHIVE_ONLY: le fichier législatif 2002 reste exclu des faits canoniques.
"""
    adapted[base.DOCUMENTS[2]] += """

CUBES ÉLECTORAUX V13
FACT_ELECTION_RESULT est au grain contest_id × party_id et porte uniquement les voix
non nulles directement publiées. FACT_ELECTORAL_MOBILIZATION est au grain contest_id;
ses mesures peuvent être NULL indépendamment selon la qualification source × mesure.
DIM_ELECTORAL_CONTEST fixe l'élection, le type de liste, le territoire et le découpage.
"""
    adapted[base.DOCUMENTS[3]] += """

DIMENSIONS V13
DIM_ELECTORAL_CONTEST contient 639 contest_id uniques. DIM_GEO reçoit 159 territoires
historiques ou provisoires datés. DIM_PARTY reçoit quatre partis ou alliances historiques
provisoires. Ces ajouts garantissent les clés étrangères sans affirmer d'équivalence moderne.
"""
    adapted[base.DOCUMENTS[4]] += """

DÉCOUPAGES HISTORIQUES V13
Les courses de 2007 et 2011 sont attachées à boundary_version=source_election_<année>.
Leur geo_id historique est analysable dans son propre millésime. Une comparaison avec une
géographie actuelle est interdite tant qu'un bridge surfacique ou institutionnel n'est pas validé.
"""
    adapted[base.DOCUMENTS[5]] += """

CROSSWALKS V13
Le registre versionné relie les codes source aux election_id, party_id et geo_id. Cinq codes
partisans 2007 restent provisoires; ils sont conservés séparément. Aucune fusion de parti ou
de territoire n'est réalisée sur la seule ressemblance d'un libellé.
"""
    adapted[base.DOCUMENTS[6]] += """

TEMPS V13
Chaque contest est valide à la date de son scrutin et conserve son boundary_version.
Les élections intégrées couvrent 2007–2021. La date du scrutin n'autorise pas à transférer
un découpage, un parti ou une valeur de mobilisation vers une autre élection.
"""
    adapted[base.DOCUMENTS[7]] += """

FAITS ÉLECTORAUX V13
OBSERVÉ: votes, capacité en sièges du contest, inscrits, participation, suffrages valides
ou taux de bulletins blancs/nuls uniquement lorsque la qualification vaut GO.
NULL: mesure absente ou non qualifiée; NULL ne signifie jamais zéro.
nSieges est une capacité du contest et non une attribution de sièges à un parti.
"""
    adapted[base.DOCUMENTS[11]] += """

LINEAGE V13
Six XLSX acquis avec SHA-256 → profil consolidé → registre d'identités → qualification
source × mesure → faits canoniques. V12 est reconstruite depuis ses sources avant ajout des
tables V13; le classeur V12 existant n'est ni lu comme bootstrap ni modifié.
"""
    adapted[base.DOCUMENTS[12]] += """

JOINTURES V13
- FACT_ELECTION_RESULT.contest_id → DIM_ELECTORAL_CONTEST.contest_id: N:1, obligatoire.
- FACT_ELECTION_RESULT.party_id → DIM_PARTY.party_id: N:1, obligatoire.
- FACT_ELECTORAL_MOBILIZATION.contest_id → DIM_ELECTORAL_CONTEST.contest_id: 1:1.
- DIM_ELECTORAL_CONTEST.geo_id → DIM_GEO.geo_id: N:1, obligatoire.
- DIM_ELECTORAL_CONTEST.election_id → DIM_ELECTION.election_id: N:1, obligatoire.
Interdit: joindre 2007/2011 à la géographie courante par nom ou agréger NULL comme zéro.
"""
    adapted[base.DOCUMENTS[13]] += """

MÉTRIQUES V13
vote_share = votes / somme(votes non NULL) dans le même contest, uniquement comme couverture
des valeurs observées; elle ne devient une part officielle que si le dénominateur publié se
réconcilie. turnout_rate et invalid_vote_rate sont OBSERVÉS lorsqu'ils sont publiés, non dérivés.
Toute division retourne NULL lorsque son dénominateur est absent ou nul.
"""
    return adapted


def _validate(model: dict, docs: dict[str, str], before_hash: str) -> None:
    errors: list[str] = []
    if len(model["sheets"]) != 71:
        errors.append(f"71 onglets attendus, obtenu {len(model['sheets'])}")
    if set(model["audit"]) != set(model["sheets"]) - {"WORKBOOK_AUDIT_V13"}:
        errors.append("WORKBOOK_AUDIT_V13 n'est pas exhaustif")
    expected = {
        "DIM_ELECTORAL_CONTEST": 639,
        "FACT_ELECTION_RESULT": 10_883,
        "FACT_ELECTORAL_MOBILIZATION": 639,
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
        "10 883 résultats",
        "639 courses électorales",
        "ARCHIVE_ONLY",
        "NULL ne signifie jamais zéro",
        "boundary_version",
    ]:
        if phrase not in corpus:
            errors.append(f"Règle V13 absente: {phrase}")
    for name, content in docs.items():
        for token in ["VERSION", "CLASSEUR SOURCE", "DATE DE GÉNÉRATION", "PÉRIMÈTRE", "RENVOIS"]:
            if token not in content:
                errors.append(f"Métadonnée absente de {name}: {token}")
        if len(content.strip()) < 500:
            errors.append(f"Document trop court: {name}")
    if before_hash != base.sha256(base.WORKBOOK):
        errors.append("Le classeur V13 a changé pendant la documentation")
    if errors:
        raise RuntimeError("ÉCHEC DOCUMENTATION V13\n- " + "\n- ".join(errors))


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
    print(f"DOCUMENTATION_OK version=V13 files=15 output={base.OUTPUT_DIR}")
    print(f"WORKBOOK_SHA256={before}")


if __name__ == "__main__":
    main()
