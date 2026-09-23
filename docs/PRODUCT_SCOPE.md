# Périmètre du produit public

Ce document est la décision canonique de publication du **Morocco Electoral Data Warehouse**. Il décrit le contenu actuellement matérialisé, indépendamment du numéro des anciens paquets. Un `snapshot_id` identifie une publication immuable mais ne change ni le modèle, ni la pipeline.

Principes : une absence n'est jamais interprétée comme zéro; une couverture n'est dite complète que contre un univers externe vérifié; DuckDB est la seule représentation matérialisée; les fichiers JSON de publication ne sont que des index cryptographiques dérivés.

La consommation directe passe par dix vues `analytics_*` dans ce même DuckDB.
Elles ne recopient aucune table et ne constituent pas une seconde source de
vérité. Leur grain, leur clé et leur finalité sont catalogués séparément des 45
tables dans `table-catalog.json`; voir [ANALYTICAL_GUIDE.md](ANALYTICAL_GUIDE.md).

## Matrice des domaines

| Domaine | Tables et grain | Période | Sources principales | Couverture et limites | Licence | Décision |
|---|---|---|---|---|---|---|
| Élections | `dim_election` (une élection), `dim_electoral_contest` (un scrutin territorial), `dim_legal_regime` et bridges (un régime applicable) | élections publiées jusqu'en 2021 | paquet public antérieur vérifié; textes officiels enregistrés et épinglés | 9 élections et 3 715 scrutins; le régime est structuré pour les scrutins couverts | selon `sources`; redistribution contrôlée fichier par fichier | **Publié** |
| Mobilisation | `fact_electoral_mobilization` (un scrutin) | 2007–2021 selon disponibilité | résultats électoraux publiés | 639 lignes; inscrits complets dans le périmètre publié pour 2007 et 2011, indisponibles pour plusieurs élections ultérieures | composite, voir `LICENSES/DATA.md` | **Publié partiellement** |
| Résultats | `fact_election_result`, `fact_communal_election_result`, `fact_commune_election_summary` (résultat au grain déclaré), `fact_result_reconciliation` (un contrôle par scrutin et métrique) | élections publiées jusqu'en 2021 | paquet public vérifié; TAFRA et sources officielles enregistrées | 10 883 résultats généraux, 22 054 résultats communaux, 3 076 synthèses; statut final officiel non inféré; réconciliations non calculables conservées comme telles | composite, avec provenance par source | **Publié partiellement** |
| Territoires | `dim_geo` (une entité), `fact_geo_population` (population officielle), `bridge_geo_official_identifier` (un identifiant officiel), `bridge_geo_parent` (une relation datée) | référentiels utiles aux élections publiées; population RGPH 2014 | HCP et paquet vérifié | 1 825 géographies; 1 538 populations et identifiants; 204 relations parentes vérifiées; aucune équivalence de frontière n'est supposée | métadonnées et faits redistribuables selon le registre | **Publié partiellement** |
| Partis | `dim_party` (un parti) | élections publiées | paquet public vérifié | 57 partis; aucune lignée historique n'est publiée sans source dédiée | composite | **Publié** au niveau d'identité seulement |
| Personnes et mandats | `dim_person_public` (une personne publique), `fact_mandate` (un mandat), `bridge_person_parliamentary_affiliation` (une affiliation parlementaire datée) | législatures 2007–2026 | données parlementaires et TAFRA enregistrées | 1 185 personnes et 1 654 mandats/affiliations; groupes parlementaires historiques non résolus pour les quatre législatures | composite; données publiques uniquement | **Publié partiellement** |
| Parlement | dimensions parlementaires, `fact_parliamentary_question`, `fact_parliamentary_response`, bridges question-source/auteur, trois tables analytiques et `parliamentary_outlier_audit` | questions 2017–2024; mandats 2007–2026 | Parlement et corpus publiés enregistrés | 65 748 questions et 30 257 réponses; couverture totale inconnue faute de dénominateur officiel; analyses descriptives, non causales | composite | **Publié partiellement** |
| Indicateurs | `dim_indicator`, `dim_time`, `fact_observation`, `data_dictionary` (une définition ou observation) | selon indicateur | sources enregistrées dans `sources` | 335 indicateurs et 3 203 observations; précision temporelle explicite; aucune valeur prévue ou inférée publiée comme observation | par source | **Publié partiellement** |
| Preuves | `sources` (une source), `warehouse_metadata` (un snapshot), plus les tables de publication à matérialiser ci-dessous | date du snapshot | registre de sources, fichiers épinglés, build | toute preuve doit être traçable à des octets ou à une source déclarée | statut explicite par fichier/source | **Publié** |

## Tables de preuve matérialisées

Ces tables appartiennent au produit public et sont remplies dans chaque reconstruction :

- `coverage_universe` et `coverage_universe_member` : univers externes et identifiants attendus;
- `publication_file` : index des fichiers, tailles, SHA-256, licence et classe d'affirmation;
- `publication_review` : décisions de licence, confidentialité et classe d'affirmation liées à l'empreinte du contenu inspecté;
- `release_coverage_matrix` : couverture synthétique par périmètre;
- `publication_gate_result` : résultat synthétique de chaque contrôle.

Leur grain est celui déclaré dans le contrat actuel. Le manifeste compact ne contient que leurs empreintes logiques et les références nécessaires à la vérification. Les trois tables de preuve auto-référentielles utilisent une empreinte logique du contenu substantiel du DuckDB qui exclut ces tables de preuve.

## Schémas proposés, exclus du contrat actif

Les tables suivantes sont actuellement vides et ne publient aucun fait. Elles sont des propositions de schéma, pas des tables du produit actif :

- candidatures et sièges : `dim_contest_type`, `dim_seat_category`, `fact_candidacy_list`, `fact_candidate`, `fact_seat_allocation`;
- histoire des partis : `dim_party_version`, `bridge_party_lineage`, `bridge_person_party_affiliation`;
- histoire géographique : `dim_geo_version`, `bridge_geo_lineage`;
- décisions et révisions officielles : `fact_legal_decision`, `fact_result_revision`;
- validation scientifique future : `fact_metric_validation`.

Elles seront déplacées hors du contrat actif. Une table ne pourra y revenir qu'avec une source comprise, un grain défini, une licence décidée, des lignes matérialisées et un usage public ou un gate identifié.

## Critère de maintien d'une table

Une table active doit répondre à une question publique concrète, contenir des faits ou métadonnées nécessaires au snapshot, avoir une provenance et une décision de licence, et être contrôlée par une contrainte, un test ou un gate utile. Les tables analytiques restent publiées uniquement lorsqu'elles sont déterministes et dérivables du DuckDB canonique.
