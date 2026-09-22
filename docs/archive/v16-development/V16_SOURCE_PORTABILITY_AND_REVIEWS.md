# Portabilité des preuves et revues V16

Le paquet physique contient neuf fichiers : sept payloads inventoriés, `package-manifest.json` et `evidence-bundle.json`. Les deux derniers sont des contrôles d'intégrité : le bundle épingle le manifeste et son empreinte est publiée hors paquet. Les gates de revue portent donc sur les sept payloads sans créer de référence cryptographique circulaire.

## Matrice compacte des fichiers

| Fichier | Source | Licence | Confidentialité | `claim_class` | Preuve | Gates consommateurs | Portabilité |
|---|---|---|---|---|---|---|---|
| `morocco_elections_v16.duckdb` | `V16_BUILD_PIPELINE` | ODbL 1.0, droits tiers conservés | PASS, revue schéma/contenu | `DERIVED_DESCRIPTIVE` | SHA du fichier + politique `LICENSES/DATA.md` | quatre gates de revue, faits, métriques | payload relatif |
| `data-contract.json` | `V16_BUILD_PIPELINE` | ODbL 1.0 | PASS | `DERIVED_DESCRIPTIVE` | idem | quatre gates de revue | payload relatif |
| `v15-immutable-checksums.json` | `V16_BUILD_PIPELINE` | ODbL 1.0 | PASS | `DERIVED_DESCRIPTIVE` | idem | revues, immutabilité V15 | payload relatif |
| `v16-geo-parent-report.json` | `V16_BUILD_PIPELINE` | ODbL 1.0 | PASS | `DERIVED_DESCRIPTIVE` | idem | revues, relations géographiques | payload relatif |
| `v16-reconciliation-report.json` | `V16_BUILD_PIPELINE` | ODbL 1.0 | PASS | `DERIVED_DESCRIPTIVE` | idem | revues, rapprochements | payload relatif |
| `v16-result-history-report.json` | `V16_BUILD_PIPELINE` | ODbL 1.0 | PASS | `DERIVED_DESCRIPTIVE` | idem | revues, historique des résultats | payload relatif |
| `table-catalog.json` | `V16_BUILD_PIPELINE` | ODbL 1.0 | PASS | `DERIVED_DESCRIPTIVE` | idem | revues, intégrité exhaustive | payload relatif |
| `package-manifest.json` | contrôle de build | contrôle hors registre payload | aucune donnée additionnelle | contrôle, aucune affirmation métier | épinglé par le bundle | intégrité du paquet | relatif au paquet |
| `evidence-bundle.json` | contexte des gates | contrôle hors registre payload | contient les décisions, pas les RAW | contrôle, aucune affirmation métier | SHA externe du build | `EVIDENCE_BUNDLE_VERIFIED` | relatif au paquet |

Chaque payload possède exactement une `license_review`, une `privacy_review` et une `claim_review`. Chaque revue contient le chemin relatif et le SHA-256 du fichier inspecté. Le manifeste refuse les statuts de licence `UNKNOWN` et `FORBIDDEN` pour un payload public.

## Sources nécessaires aux deux gates portables

| Source | Licence observée | Preuve/gate | Catégorie | Octets inclus |
|---|---|---|---|---|
| HCP RGPH 2014, population légale des communes | `UNKNOWN`; aucune autorisation de redistribution déduite | univers territorial / `OFFICIAL_UNIVERSE_DECLARED` | `REPRODUCIBLY_ACQUIRABLE` | non |
| TAFRA résultats communaux 2015 et 2021 | CC BY 4.0 déclarée par la fiche source | rapprochements / `METRIC_RECONCILED` | `REPRODUCIBLY_ACQUIRABLE` | non |
| TAFRA législatives 2007, 2011, 2016 et 2021 | attribution Creative Commons annoncée par openAFRICA | rapprochements / `METRIC_RECONCILED` | `REPRODUCIBLY_ACQUIRABLE` | non |
| TAFRA régionales 2015 et 2021 | attribution Creative Commons annoncée par openAFRICA | rapprochements / `METRIC_RECONCILED` | `REPRODUCIBLY_ACQUIRABLE` | non |
| TAFRA élus communaux 2015 | CC BY 4.0 dans la qualification V11-A | contrôle transitive du rapprochement / `METRIC_RECONCILED` | `REPRODUCIBLY_ACQUIRABLE` | non |

Chaque acquisition enregistre une URL HTTP(S), un chemin relatif logique, une taille, un SHA-256 et une empreinte du descripteur. Une URL, une empreinte ou des octets distants modifiés provoquent un échec explicite. Aucun chemin absolu de dépôt n'est sérialisé.

Le rapport machine détaillé est `data/exports/open/v16-development-portability-report.json`. Il compare les statuts des gates dans le dépôt et depuis le paquet autonome, et liste la matrice complète fichier → revue ainsi que les dix descripteurs de source.
