MOROCCO ELECTORAL DATA WAREHOUSE — PAQUET OUVERT V13

Release source : V13
Généré le : 2026-09-11
SHA-256 du classeur source : 35f5f12b55a603c05c7230b701d0a629dbd78b697b49da177cdf7a3419770332

CONTENU

Le paquet expose un seul modèle canonique sous trois accès: CSV, Parquet et DuckDB.
Les fichiers ne sont pas trois produits différents; ils contiennent les mêmes tables et règles.

- dim_geo: 1825 lignes; clé=geo_id; source Excel=DIM_GEO.
- dim_party: 57 lignes; clé=party_id; source Excel=DIM_PARTY.
- dim_time: 17 lignes; clé=time_id; source Excel=DIM_TIME.
- dim_election: 9 lignes; clé=election_id; source Excel=DIM_ELECTION.
- dim_electoral_contest: 3715 lignes; clé=contest_id; source Excel=DIM_ELECTORAL_CONTEST.
- dim_person_public: 1185 lignes; clé=person_id; source Excel=DIM_PERSON.
- fact_election_result: 10883 lignes; clé=result_id; source Excel=FACT_ELECTION_RESULT.
- fact_electoral_mobilization: 639 lignes; clé=contest_id; source Excel=FACT_ELECTORAL_MOBILIZATION.
- fact_communal_election_result: 22054 lignes; clé=contest_id,party_id; source Excel=ANALYTICAL_PANEL.
- fact_commune_election_summary: 3076 lignes; clé=contest_id; source Excel=COMMUNE_ELECTION_PANEL.
- fact_observation: 3203 lignes; clé=observation_id; source Excel=FACT_OBSERVATION.
- fact_parliamentary_mandate: 1654 lignes; clé=mandate_id; source Excel=PARLIAMENTARY_MANDATES.
- fact_parliamentary_activity: 5589 lignes; clé=question_id; source Excel=PARLIAMENTARY_QUESTIONS.
- sources: 61 lignes; clé=source_id; source Excel=SOURCES.
- dim_indicator: 335 lignes; clé=indicator_id; source Excel=DATA_DICTIONARY.
- data_dictionary: 292 lignes; clé=metric_id; source Excel=DATA_DICTIONARY.

DÉMARRAGE RAPIDE

DuckDB: SELECT * FROM fact_election_result LIMIT 10;
Jointure: fact_election_result.contest_id = dim_electoral_contest.contest_id.
Trois exemples reproductibles sont fournis dans queries.sql.
Les checksums sont dans checksums.sha256; le schéma et les volumes sont dans manifest.json.
La politique de licence du paquet composite est dans LICENSE_DATA.md.

LIMITES ESSENTIELLES

- LEG2002 n'est pas intégré.
- Une cellule absente reste NULL et ne signifie jamais zéro.
- Les géographies 2007/2011 restent liées à leur découpage historique.
- Les agrégats doivent rester séparés par élection et type de liste.
- Les conditions de réutilisation sont conservées source par source dans la table sources.
- dim_indicator ajoute 43 entrées de conformance OBSERVED_UNDOCUMENTED; leur définition reste obligatoire avant interprétation.
- Ce paquet ne contient ni RAW, ni noms de personnes, ni questions parlementaires nominatives.
- Le fichier DuckDB porte un hash logique stable; son checksum binaire local figure dans checksums.sha256.
