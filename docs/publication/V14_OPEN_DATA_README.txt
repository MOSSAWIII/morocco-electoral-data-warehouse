MOROCCO ELECTORAL DATA WAREHOUSE — PAQUET OUVERT V14

Généré le : 2026-09-12
SHA-256 du classeur V13 de base : 35f5f12b55a603c05c7230b701d0a629dbd78b697b49da177cdf7a3419770332

PÉRIMÈTRE

V14 conserve les faits ouverts V13 et remplace le sous-ensemble parlementaire 2023–2024
par l'union dédupliquée de ce sous-ensemble et des nouvelles questions écrites ou orales 2017–2024.
La couverture décrit les 59 fichiers uniques disponibles; elle ne prouve pas l'exhaustivité de l'activité parlementaire.

TABLES

- dim_geo: 1825 lignes; clé=geo_id.
- dim_party: 57 lignes; clé=party_id.
- dim_time: 17 lignes; clé=time_id.
- dim_election: 9 lignes; clé=election_id.
- dim_electoral_contest: 3715 lignes; clé=contest_id.
- dim_person_public: 1185 lignes; clé=person_id.
- fact_election_result: 10883 lignes; clé=result_id.
- fact_electoral_mobilization: 639 lignes; clé=contest_id.
- fact_communal_election_result: 22054 lignes; clé=contest_id,party_id.
- fact_commune_election_summary: 3076 lignes; clé=contest_id.
- fact_observation: 3203 lignes; clé=observation_id.
- fact_parliamentary_mandate: 1654 lignes; clé=mandate_id.
- sources: 61 lignes; clé=source_id.
- dim_indicator: 335 lignes; clé=indicator_id.
- data_dictionary: 292 lignes; clé=metric_id.
- dim_parliamentary_period: 30 lignes; clé=period_id.
- dim_institution: 94 lignes; clé=institution_id.
- dim_parliamentary_subject: 58806 lignes; clé=subject_id.
- dim_parliamentary_author: 1622 lignes; clé=author_id.
- dim_parliamentary_group: 19 lignes; clé=group_id.
- dim_parliamentary_source: 59 lignes; clé=source_id.
- fact_parliamentary_question: 65748 lignes; clé=question_id.
- fact_parliamentary_response: 30257 lignes; clé=response_id.
- bridge_question_author: 65748 lignes; clé=question_author_id.
- bridge_question_source: 66974 lignes; clé=question_source_id.
- analytical_parliamentary_trajectory: 3142 lignes; clé=trajectory_id.

DÉMARRAGE RAPIDE

DuckDB: SELECT * FROM fact_parliamentary_question LIMIT 10;
Trois requêtes reproductibles sont fournies dans queries.sql.
Les relations sont déclarées dans manifest.json et tous les fichiers sont couverts par checksums.sha256.
Les licences, attributions et informations de citation sont incluses dans le paquet.

LIMITES

- Une question est identifiée par type × numéro source × date de dépôt.
- 66 974 occurrences source sont conservées pour 65 748 questions dédupliquées.
- Les auteurs sont raccordés uniquement par identité Unicode exacte dans la même législature.
- Un auteur non raccordé garde person_id=NULL; aucun rapprochement flou n'est appliqué.
- Le parti est attribué seulement via un mandat de la même législature pour une identité exacte.
- Les trajectoires sont dérivées uniquement pour les personnes raccordées; leur taux de réponse
  vaut 100 × questions avec date de réponse / questions publiées du groupe.
- Les libellés d'auteur ne sont pas diffusés dans le paquet public.
- Une absence de date de réponse signifie seulement non publiée dans les fichiers disponibles.
- Les textes et objets restent des champs source; aucune taxonomie thématique n'est inventée.
- Le maximum observé est de 2446 questions pour un auteur source;
  cette valeur répartie sur plusieurs fichiers et années est conservée, sans conclure à sa représentativité.
