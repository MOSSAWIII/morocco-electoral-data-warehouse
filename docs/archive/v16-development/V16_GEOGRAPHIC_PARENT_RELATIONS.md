# Relations parentales géographiques V16

V16 conserve V15 byte pour byte et matérialise les corrections dans `bridge_geo_parent`. Le diagnostic ciblé comptait 3 293 faits législatifs rattachés à 135 couples élection-territoire de type `province_prefecture_snapshot` dont le parent régional historique n'était pas représenté dans `dim_geo`. La validation exhaustive a aussi révélé 504 faits sur 16 couples élection-district préfectoral : leur chaîne V15 aboutissait à une région actuelle plutôt qu'à la version régionale historique du concours.

Le build matérialise 204 relations datées du seul jour de scrutin : 151 relations historiques vers la région déclarée par les concours sources, 41 relations arrondissement → commune-parente, 6 relations commune-parente → préfecture/province et 6 relations préfecture/province → région. Les 41 codes d'arrondissement sont les codes HCP exacts; les six identifiants `COMM2015-CITY:*` sont internes à V16 et ne sont pas présentés comme des identifiants officiels. Le BO 6381 établit le groupement nominal; il ne fournit pas de polygones.

Résultat matérialisé : 3 797 violations `REGIONAL_PARENT_MISMATCH` avant superposition, 3 797 corrigées, 0 restante, 0 référence orpheline et 0 relation ambiguë. Le sous-ensemble demandé de 3 293 écarts est conservé dans `requested_snapshot_mismatches`.

Le gate `SEMANTIC_FACTS_VALIDATED` relit `bridge_geo_parent` dans le DuckDB déclaré, compare toutes ses colonnes au contexte évalué, valide dates, doublons et références, puis parcourt le graphe actif pour chaque fait. Les tests négatifs couvrent suppression, doublon, parent muté, rattachement direct erroné à une préfecture, date incompatible, code officiel inventé et empreinte source modifiée.

Les quatre lignes BO 6374 sans équivalent Tafra au grain communal — Tanger, Fès, Rabat et Salé — portent désormais leur `v16_communal_parent_id` vérifié. Elles restent `UNMATCHED` uniquement parce que Tafra expose des résultats d'arrondissements sans ligne équivalente de conseil de ville; ce blocage précis est enregistré dans `remaining_blocker`.

Artefacts :

- `data/exports/open/v16-development/morocco_elections_v16.duckdb`
- `data/exports/open/v16-development/v16_geo_parent_report.json`
- `data/exports/open/v16-development/bo6374_tafra_2015_reconciliation.json`
