# Produit analytique autonome

Le produit analytique vit exclusivement sur la branche `Main-Analytics`. Il lit
le warehouse canonique sans l'attacher en écriture et matérialise une base
indépendante :

```powershell
python -m morocco_elections.analytics.cli build --replace
python -m morocco_elections.analytics.cli validate
```

La sortie par défaut est
`data/exports/analytics/morocco_elections_analytics.duckdb`. Elle est ignorée par
Git et entièrement reconstruisible. `analytics_build_metadata` enregistre les
SHA-256 de la base et du manifeste canoniques, le release ID et le mode
`READ_ONLY`.

## Contrat des marts

| Mart | Grain | Clé |
|---|---|---|
| `mart_contest_results` | un résultat de parti/liste, concours et bulletin | `analytical_result_id` |
| `mart_contest_competitiveness` | un concours et bulletin | `contest_id` |
| `mart_party_performance` | un parti, une élection et un bulletin | `party_performance_id` |
| `mart_geography_profile` | un territoire, une élection et un bulletin | `geography_profile_id` |
| `mart_parliamentary_activity` | une personne, parti, législature, période et type de question | `parliamentary_activity_id` |

`analytics_column_catalog` documente l'unité et la signification stable de
chaque colonne. `analytics_join_contracts` déclare les cardinalités autorisées.
Les statuts opérationnels sont `AVAILABLE`, `LIMITED` et `NOT_AVAILABLE` ; tout
statut non disponible porte une raison. La normalisation interne est exposée
comme `SOURCE_DISTRIBUTION_NORMALIZED`. La compatibilité longitudinale reste
`UNKNOWN` tant qu'elle n'est pas démontrée indépendamment.

Les six requêtes de démonstration dans `examples/analytics/` couvrent le profil
d'une élection, le classement territorial d'un parti, les marges de victoire,
la concentration communale, la comparaison séparée des bulletins et l'activité
parlementaire. Chaque sortie conserve sa source, son périmètre ou ses limites.

Une correction factuelle détectée pendant l'analyse ne doit pas modifier le
warehouse depuis cette branche. Elle doit être décrite séparément et proposée
sur `main` avec sa preuve source.
