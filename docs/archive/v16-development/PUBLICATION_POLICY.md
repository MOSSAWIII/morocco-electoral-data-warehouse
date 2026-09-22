# V16 — gate de publication

Une release est `PUBLICATION_READY` seulement si chaque fichier possède une provenance, une date d’acquisition, un SHA-256, un statut de licence et une classe d’affirmation, si la matrice de couverture se réconcilie, et si tous les gates suivants sont vrais :

1. `EVIDENCE_BUNDLE_VERIFIED`
2. `SEMANTIC_FACTS_VALIDATED`
3. `LEGAL_REGIME_PINNED`
4. `RESULT_STATUS_KNOWN`
5. `AS_OF_DATE_VALID`
6. `OFFICIAL_UNIVERSE_DECLARED`
7. `DENOMINATOR_TYPED`
8. `GRAIN_COMPATIBLE`
9. `BOUNDARY_COMPATIBLE`
10. `PARTY_LINEAGE_REVIEWED`
11. `SOURCE_CONFLICTS_RESOLVED_OR_EXPOSED`
12. `CANDIDACY_AND_SEATS_VALIDATED`
13. `METRIC_RECONCILED`
14. `ANALYTIC_METRICS_ADMISSIBLE`
15. `COVERAGE_DISCLOSED`
16. `UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE`
17. `PRIVACY_REVIEW_PASSED`
18. `CLAIM_CLASS_DECLARED`
19. `REDISTRIBUTION_PERMITTED`
20. `REPRODUCIBLE_FROM_CLEAN_ENVIRONMENT`
21. `V15_IMMUTABILITY_VERIFIED`

L’échec d’un seul gate conserve les données en mode exploratoire avec `NOT_PUBLICATION_READY` et des erreurs explicites. Aucun score composite ne peut masquer un échec. Chaque gate est calculé par une fonction enregistrée à partir d’un `PublicationContext`; son résultat publie `status`, `justification`, `evidence_id` (empreinte SHA-256 des preuves inspectées) et `affected_records`. Les dictionnaires de booléens fournis par l’appelant sont refusés.

`EVIDENCE_BUNDLE_VERIFIED` inventorie récursivement les octets présents sous la racine du paquet. Chaque fichier doit être soit un fichier public déclaré, soit le bundle de preuves, soit le manifeste attesté, soit un rapport de construction propre référencé. Tout fichier supplémentaire, lien symbolique ou chemin sortant de la racine fait échouer le gate. Les sources officielles brutes utilisées comme preuves sont conservées sous une racine de preuves distincte et ne peuvent donc entrer silencieusement dans le paquet public.

`PRIVACY_REVIEW_PASSED` exige exactement une revue traçable et favorable pour chaque fichier public, même lorsqu'il est agrégé. Une valeur déclarative `privacy_review_required = false` ne constitue jamais une exemption. La revue doit être datée au plus tard à la date `as_of_date`; une revue orpheline, future ou dupliquée fait échouer le gate.

`OFFICIAL_UNIVERSE_DECLARED` ne fait pas confiance au seul booléen `is_external`. Chaque univers et chacun de ses identifiants attendus doivent référencer une source du registre officiel dont les octets, la taille et le SHA-256 sont vérifiés localement; l'URL de l'univers doit être identique à l'URL enregistrée. Un total agrégé sans liste d'identifiants reste insuffisant.

Le gate reconstitue aussi l'ensemble attendu directement depuis les octets officiels selon une méthode d'extraction contrôlée et versionnée. `HCP_RGPH2014_COMMUNES` relit tous les codes complets du classeur HCP, y compris les lignes à population masquée; `JSON_UNIVERSES_OBJECT` lit les tableaux d'identifiants nommés par `universe_id`. Un identifiant déclaré absent de la source, un identifiant source omis ou une méthode non reconnue bloque la publication.

`SEMANTIC_FACTS_VALIDATED` exige une base DuckDB située sous la racine du paquet et déclarée parmi les fichiers publics avec son SHA-256 observé. Il relit en lecture seule les trois tables de faits, compare leur multiset complet à `semantic_facts`, puis compare les dimensions `dim_election`, `dim_electoral_contest`, `dim_geo` et toutes les colonnes de `bridge_geo_parent`. Il valide ensuite le graphe parental actif à la date de chaque scrutin. Une omission, une modification ou une ligne ajoutée échoue, même si le bundle de preuves correspond au contexte modifié.

`LEGAL_REGIME_PINNED` compare chaque ligne et tous les champs, obligatoires et facultatifs, des trois tables `dim_legal_regime`, `bridge_election_legal_regime` et `bridge_contest_legal_regime` aux ensembles évalués dans la base DuckDB déclarée. Il lie aussi exhaustivement `fact_geo_population` et `bridge_geo_official_identifier`, puis réextrait leurs lignes depuis les octets HCP épinglés et les géographies de la base publiée. Une formule ou une classification juridique réécrite échoue même avec un bundle cohérent; une falsification coordonnée des populations, de la base et du bundle échoue si le classeur source reste inchangé.

Pour `COMM2015`, les six parents V15 des 41 arrondissements sont des préfectures/provinces, pas des communes. Le fait que `1 497 + 6 = 1 503` égale le total DGCL n'est qu'une coïncidence de nombres; il ne constitue ni un univers officiel d'identifiants de conseils ni une réconciliation du grain communal.

Le registre historique `comm2015_council_candidates.seed.json` reste un artefact candidat. La preuve distincte `comm2015_geo_parents.seed.json` limite sa prétention à la parenté applicable le 4 septembre 2015 : l'annexe du décret 2-15-577 est revue visuellement et croisée avec les 41 codes HCP exacts. Les 41 relations et les six chaînes vers préfecture/province puis région sont matérialisées; les identifiants `COMM2015-CITY:*` restent internes. Cette promotion ne certifie ni limites polygonales, ni univers électoral complet, ni identifiant officiel des six communes-parentes.

`REDISTRIBUTION_PERMITTED` accepte uniquement les fichiers portant `license_status = REDISTRIBUTABLE`. Ce statut doit correspondre à exactement une décision du registre de licence, avec base juridique, URL de preuve, responsable et date antérieure ou égale à `as_of_date`. `METADATA_ONLY` autorise la publication de la notice, jamais l'inclusion des octets sources dans le paquet public.

`BOUNDARY_COMPATIBLE` refuse qu'une simple ligne `SAME_BOUNDARY` et `confidence = 1` prouve l'identité de deux versions distinctes. Chaque version et succession est liée exhaustivement à `dim_geo_version` et `bridge_geo_lineage` du paquet; sa source officielle doit posséder des octets locaux à taille/SHA-256 revérifiés. Chaque version directement comparée doit référencer par `geometry_path` un fichier GeoJSON du paquet, présent dans son inventaire et conforme au SHA-256 déclaré. Le gate inspecte des polygones fermés en coordonnées longitude/latitude sans CRS alternatif et compare les empreintes des géométries réellement lues. Un fichier absent, modifié, mal formé ou différent bloque la comparaison directe, même si le contrôle et le bundle ont été réécrits ensemble. Cela ne prouve pas encore que la géométrie a été reconstruite correctement depuis les coordonnées et segments de la source; les géométries officielles finales, leur dérivation et les dates d'effet restent à acquérir et valider.

`METRIC_RECONCILED` ne valide pas une égalité numérique dépourvue de provenance. Chaque valeur officielle comparée possède un `source_id` obligatoire relié à une entrée du registre dont les octets sont revérifiés; le schéma conserve séparément valeur officielle, valeur recalculée, différence, tolérance et statut.
Le gate compare le multiset complet des rapprochements du contexte à la table `fact_result_reconciliation` du paquet; une omission ou mutation échoue même après régénération du bundle et du manifeste. Chaque concours déclaré doit recevoir exactement un statut pour `turnout_rate`, `ballot_categories_vs_voters`, `party_votes_vs_valid_votes` et `allocated_seats_vs_contest_seats`; l'absence d'un contrôle échoue. Pour `turnout_rate`, le gate relit la mobilisation matérialisée, vérifie que la valeur officielle et sa source concordent avec le fait, puis recalcule exactement `voters / registered_voters`; une modification coordonnée du contexte et du registre échoue. Pour les trois autres contrôles, les valeurs officielles doivent également correspondre à la ligne de mobilisation et à sa source. Le motif contrôlé `not_computable_reason` est recalculé : composants manquants, taxonomie des bulletins non vérifiée, univers de partis ou de sièges non vérifié. Une mutation coordonnée des composants de bulletins ne peut pas conserver un ancien motif. Une métrique sans dérivation prise en charge ne peut pas être `PASS`. Le recalcul de concours exige une concordance exacte avec un ensemble attendu distinct, mais cet ensemble doit encore être extrait d'une source électorale officielle : un tableau fourni par l'appelant ne suffit pas. La dérivation des autres métriques, la taxonomie sourcée des bulletins et l'exécution sur tous les concours finaux restent obligatoires avant publication.
