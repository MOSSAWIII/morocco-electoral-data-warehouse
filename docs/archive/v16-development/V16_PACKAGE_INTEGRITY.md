# Intégrité du paquet V16

Le paquet canonique de développement est `data/exports/open/v16-development/`. Il est toujours construit dans un répertoire de staging neuf, validé sur place, puis déplacé vers cette destination. L'option `--replace` remplace l'ancien paquet seulement après la réussite de la validation; un échec laisse la destination existante intacte.

Les preuves sources portables et les revues fichier par fichier sont décrites dans [`V16_SOURCE_PORTABILITY_AND_REVIEWS.md`](V16_SOURCE_PORTABILITY_AND_REVIEWS.md). Les sources RAW nécessaires aux univers et aux rapprochements ne sont pas copiées : elles sont récupérées par URL épinglée puis refusées si leur taille ou leur SHA-256 diffère.

## Inventaire fermé

Le paquet contient exactement neuf fichiers :

- `morocco_elections_v16.duckdb`
- `data-contract.json`
- `v15-immutable-checksums.json`
- `v16-geo-parent-report.json`
- `v16-reconciliation-report.json`
- `v16-result-history-report.json`
- `table-catalog.json`
- `package-manifest.json`
- `evidence-bundle.json`

Les sept premiers sont les charges utiles déclarées dans `package-manifest.json`. Le manifeste enregistre pour chacune le chemin relatif, la taille, le SHA-256, le type d'artefact, la provenance, la date d'acquisition, le statut de licence, la classe d'affirmation, le statut de redistribution et l'identifiant de preuve. Le bundle épingle ensuite le SHA-256 du manifeste. Le rapport de build externe épingle enfin les SHA-256 du manifeste et du bundle, ce qui évite toute dépendance circulaire entre fichiers attestés.

`table-catalog.json` inventorie exhaustivement les 57 tables DuckDB. Pour chaque table, il publie le schéma ordonné, le nombre de lignes et une empreinte logique déterministe. Le validateur recalcule ces trois éléments depuis la base.

Les artefacts de travail `bo6374_tafra_2015_reconciliation.json` et `bo6374_tafra_2015_reconciliation_report.json` ne font pas partie du paquet public. Les rapports `v16-development-build-report.json` et `v16-development-gate-report.json` sont également externes au paquet et les quatre exclusions sont déclarées explicitement dans le rapport de gates.

## Validation autonome

La commande suivante valide un paquet à son emplacement courant ou après copie vers un autre répertoire :

```shell
python tools/validate_v16_package.py data/exports/open/v16-development
```

La validation refuse notamment : fichier non inventorié, fichier inventorié absent, chemin absolu ou traversant, doublon, divergence de taille ou de SHA-256, table omise ou supplémentaire, divergence de schéma ou de lignes, fichier brut, et redistribution affirmative lorsque la licence est inconnue ou interdite. Elle reconstruit son contexte depuis le paquet lui-même; aucun fichier local obligatoire extérieur au paquet n'est requis pour ce contrôle d'intégrité. Elle recalcule également les 21 gates et publie leurs résultats sous `publication_evaluation`. L'option `--require-ready` retourne un code d'échec tant qu'un seul gate est bloqué.

L'audit métier complet reste distinct : il peut relire les preuves officielles conservées dans le dépôt, sans les copier dans le paquet public. Le paquet de développement ne prétend pas que ces revues sont terminées. Les sept charges utiles portent donc des statuts `UNKNOWN`, `PENDING_HUMAN_REVIEW` et `privacy_review_required = true` lorsque les décisions humaines manquent.

## État des gates

`EVIDENCE_BUNDLE_VERIFIED` passe lorsque l'inventaire physique, le manifeste, le catalogue de tables et le bundle concordent. Cela ne transforme pas la release en publication finale. Le rapport courant conserve `NOT_PUBLICATION_READY` : sept gates passent et quatorze restent bloqués avec leurs motifs et nombres d'enregistrements affectés, notamment les revues de licence, confidentialité, affirmation, frontières, lignées et reproductibilité par deux builds propres.

Les tests de mutation couvrent les suppressions, ajouts, altérations d'octets, tailles et SHA-256 falsifiés, chemins dangereux, tables omises, nombres de lignes modifiés, mutations coordonnées sans preuve du bundle, fichiers bruts et déclarations de redistribution incompatibles.
