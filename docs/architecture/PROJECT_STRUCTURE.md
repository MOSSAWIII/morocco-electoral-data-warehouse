# Architecture du projet

## Flux unique

```text
RAW → STAGING → TABLES CANONIQUES VERSIONNÉES → EXPORTS ET ANALYSES
```

Une couche dépend uniquement des couches situées à sa gauche. Les RAW sont immuables; un export ne peut jamais réalimenter la construction canonique.

## Release opérationnelle

V13 est reconstruite à partir des sources physiques, des décisions versionnées et de V8 comme bootstrap des tables historiques qui ne disposent pas encore de sources séparées. Les modules V9 à V12 restent dans `legacy/` et `releases/` parce que V13 les réexécute en mémoire et vérifie leurs empreintes; leurs anciens classeurs ne deviennent pas des entrées canoniques.

Le paquet V13 est exposé par Excel pour l'inspection locale et par CSV, Parquet et DuckDB pour la diffusion. Ces formats portent les mêmes tables et règles.

## Responsabilités

- `domains/elections` : faits électoraux multi-scrutins et identifiants de courses.
- `domains/identity` : normalisation Unicode, identifiants et registre de correspondance.
- `domains/geography` et `domains/governance` : décisions manuelles versionnées nécessaires à V10–V13.
- `releases` et `legacy` : reconstruction déterministe de l'historique jusqu'à V13.
- `sources` : catalogue, acquisition immuable et profilage.
- `exports` : formats d'accès sans règle métier concurrente.
- `analysis` : analyses de référence en lecture seule.
- `quality` : invariants, empreintes, relations et limites scientifiques.
- `research` : qualificateurs historiques conservés pour reproduire les décisions.

Les espaces PostgreSQL vides ont été retirés. Ils seront créés seulement si un besoin opérationnel mesurable apparaît.

## Configuration

Les arguments CLI ont priorité sur `ELECTIONS_DATA_DIR`, qui a priorité sur `<repo>/data`. Aucun chemin absolu ni secret n'est versionné.

Une release correspond à un changement du canonique ou de son schéma. Une collecte, un `NO_GO` ou une nouvelle idée d'architecture ne crée pas de release.
