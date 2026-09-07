# Architecture du projet V10–V13

## Flux autorisé

`RAW → STAGING → PROCESSED → POSTGRESQL → EXPORTS`

RAW est immuable. STAGING décode et normalise sans décision analytique. PROCESSED applique les identités, crosswalks et règles métier. PostgreSQL deviendra la source canonique en V13. Les classeurs Excel sont des exports reproductibles.

Une couche peut dépendre uniquement des couches situées à sa gauche. Un export ne peut jamais alimenter RAW, STAGING ou la couche canonique.

## Domaines

- `identity` : clés de personnes, normalisation Unicode, collisions et décisions de désambiguïsation.
- `geography` : DIM_GEO, découpages temporels, crosswalks et preuves de revue manuelle.
- `elections` : électorat, offre, mobilisation, résultats, sièges et transitions.
- `governance` : conseils, présidences, exécutifs communaux et SMIIG.
- `socioeconomics` : population et indicateurs HCP avec validité temporelle.
- `parliament` : mandats, questions et trajectoires d’activité.

## Dépendances techniques

- `domains` ne dépend pas d’Excel, de PostgreSQL ou d’un chemin local.
- `storage` adapte les fichiers et, ultérieurement, PostgreSQL aux contrats des domaines.
- `quality` contrôle schémas, volumes, clés, provenance et non-altération.
- `exports` lit la couche canonique et produit des artefacts ; il ne contient aucune règle métier primaire.
- `legacy/v9` conserve la reproductibilité du classeur V9 jusqu’à son remplacement contrôlé.

## Configuration

Les arguments CLI ont priorité sur `ELECTIONS_DATA_DIR`, qui a priorité sur `<repo>/data`. Aucun chemin absolu ni secret n’est versionné.

