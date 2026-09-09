# Architecture du projet

## Flux autorisé

`RAW → STAGING → TABLES CANONIQUES VERSIONNÉES → EXPORTS`

RAW est immuable. STAGING décode et normalise sans décision analytique. La couche canonique applique les identités, crosswalks et règles métier. Les classeurs Excel sont actuellement les exports analytiques reproductibles.

PostgreSQL est un adaptateur de stockage possible, pas une condition de vérité des données. Sa mise en œuvre commencera lorsqu'un besoin d'interrogation, de collaboration ou de performance sera documenté. Elle ne changera ni les grains ni les règles métier canoniques.

Une couche peut dépendre uniquement des couches situées à sa gauche. Un export ne peut jamais alimenter RAW, STAGING ou la couche canonique.

## Construction courante

V11 est reconstruite à partir des RAW disponibles, des décisions versionnées et de V8 comme bootstrap historique. Aucun classeur V9, V10 ou V11 n'est une entrée de construction. La reconstruction intermédiaire de V10 est temporaire, vérifiée par son SHA-256 historique puis supprimée.

V8 ne sera retirée qu'après récupération ou qualification séparée des sources physiques des tables qu'elle porte encore. Elle ne doit pas être remplacée par une extraction canonique non sourcée qui déplacerait simplement la dépendance.

## Domaines

- `identity` : clés de personnes, normalisation Unicode, collisions et décisions de désambiguïsation.
- `geography` : DIM_GEO, découpages temporels, crosswalks et preuves de revue manuelle.
- `elections` : électorat, offre, mobilisation, résultats, sièges et transitions.
- `governance` : conseils, présidences, exécutifs communaux et SMIIG.
- `socioeconomics` : population et indicateurs HCP avec validité temporelle.
- `parliament` : mandats, questions et trajectoires d’activité.

## Dépendances techniques

- `domains` ne dépend pas d’Excel, de PostgreSQL ou d’un chemin local.
- `storage` adapte les fichiers et, si le besoin est confirmé, PostgreSQL aux contrats des domaines.
- `quality` contrôle schémas, volumes, clés, provenance et non-altération.
- `exports` lit la couche canonique et produit des artefacts ; il ne contient aucune règle métier primaire.
- `legacy/v9` conserve la reproductibilité du classeur V9 jusqu’à son remplacement contrôlé.

## Règles de proportionnalité

- Une release est créée uniquement lorsque les données canoniques ou leur schéma changent.
- Une recherche conclue `NO_GO` reste une preuve historique et ne crée pas de release.
- Un qualificateur complet n'est développé qu'après identification d'une source candidate crédible.
- Un chantier bloqué n'est rouvert qu'avec une preuve nouvelle.
- Une abstraction partagée doit répondre à au moins deux usages réels.
- La QA protège les données ; elle ne remplace ni le produit analytique ni la roadmap.

## Configuration

Les arguments CLI ont priorité sur `ELECTIONS_DATA_DIR`, qui a priorité sur `<repo>/data`. Aucun chemin absolu ni secret n’est versionné.
