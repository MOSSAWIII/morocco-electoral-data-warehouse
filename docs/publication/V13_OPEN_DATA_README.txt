MOROCCO ELECTORAL DATA WAREHOUSE — PAQUET OUVERT V13

Release source : V13
Généré le : 2026-09-11
SHA-256 du classeur source : 35f5f12b55a603c05c7230b701d0a629dbd78b697b49da177cdf7a3419770332

CONTENU

Le paquet expose un seul modèle canonique sous trois accès: CSV, Parquet et DuckDB.
Les fichiers ne sont pas trois produits différents; ils contiennent les mêmes tables et règles.

- dim_geo: 1825 lignes; clé=geo_id; source Excel=DIM_GEO.
- dim_party: 57 lignes; clé=party_id; source Excel=DIM_PARTY.
- dim_election: 9 lignes; clé=election_id; source Excel=DIM_ELECTION.
- dim_electoral_contest: 639 lignes; clé=contest_id; source Excel=DIM_ELECTORAL_CONTEST.
- fact_election_result: 10883 lignes; clé=result_id; source Excel=FACT_ELECTION_RESULT.
- fact_electoral_mobilization: 639 lignes; clé=contest_id; source Excel=FACT_ELECTORAL_MOBILIZATION.
- sources: 61 lignes; clé=source_id; source Excel=SOURCES.
- data_dictionary: 292 lignes; clé=metric_id; source Excel=DATA_DICTIONARY.

DÉMARRAGE RAPIDE

DuckDB: SELECT * FROM fact_election_result LIMIT 10;
Jointure: fact_election_result.contest_id = dim_electoral_contest.contest_id.
Les checksums sont dans checksums.sha256; le schéma et les volumes sont dans manifest.json.

LIMITES ESSENTIELLES

- LEG2002 n'est pas intégré.
- Une cellule absente reste NULL et ne signifie jamais zéro.
- Les géographies 2007/2011 restent liées à leur découpage historique.
- Les agrégats doivent rester séparés par élection et type de liste.
- Les conditions de réutilisation sont conservées source par source dans la table sources.
- Ce paquet ne contient ni RAW, ni noms de personnes, ni questions parlementaires nominatives.
- Le fichier DuckDB porte un hash logique stable; son checksum binaire local figure dans checksums.sha256.
