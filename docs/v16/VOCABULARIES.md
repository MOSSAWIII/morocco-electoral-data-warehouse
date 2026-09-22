# V16 — vocabulaires contrôlés (version 1.0.0)

Le registre exécutable canonique est `morocco_elections.v16.contracts.VOCABULARIES`. Toute valeur absente est invalide; ajouter un code exige une modification versionnée du registre et des tests.

## Statuts de qualité et de faits

| Vocabulaire | Code | Signification |
|---|---|---|
| `quality_status` | `VERIFIED` | Source et valeur vérifiées. |
| | `QUALIFIED` | Utilisable avec limites divulguées. |
| | `UNRESOLVED` | Non résolu. |
| | `REJECTED` | Rejeté par validation. |
| `fact_status` | `OBSERVED` | Fait directement observé. |
| | `OFFICIAL` | Fait publié par l’autorité compétente. |
| | `RECOMPUTED` | Valeur dérivée déterministement. |
| | `INFERRED` | Inférence, jamais présentée comme fait observé. |
| | `FORECAST` | Prévision, jamais présentée comme fait observé. |
| `validation_status` | `PASS` | Écart dans la tolérance. |
| | `FAIL` | Écart hors tolérance. |
| | `NOT_COMPUTABLE` | Entrées absentes ou incompatibles. |

## Scrutins et résultats

| Vocabulaire | Codes |
|---|---|
| `list_type` | `LOCAL`, `REGIONAL`, `NATIONAL`, `INDIVIDUAL` |
| `result_type` | `VOTES`, `SEATS`, `MOBILIZATION`, `ALLOCATION` |
| `result_status` | `PROVISIONAL`, `FINAL`, `RECTIFIED`, `ANNULLED` |
| `legal_decision_type` | `RECTIFICATION`, `ANNULMENT`, `PARTIAL_ELECTION`, `CONFIRMATION` |

## Couverture

| Vocabulaire | Code | Signification |
|---|---|---|
| `verification_status` | `VERIFIED` | Dénominateur vérifié contre la source. |
| | `PENDING` | Vérification en attente. |
| | `REJECTED` | Dénominateur rejeté. |
| `coverage_dimension` | `ACQUIRED` | Couverture des sources acquises. |
| | `OFFICIAL` | Couverture de l’univers officiel. |
| | `TERRITORIAL` | Couverture territoriale. |
| | `TEMPORAL` | Couverture temporelle. |
| | `DOCUMENTARY` | Couverture documentaire. |
| | `FIELD` | Couverture par champ. |
| `coverage_status` | `COMPLETE` | Numérateur égal au dénominateur officiel vérifié. |
| | `PARTIAL` | Univers officiel partiellement couvert. |
| | `EMPTY` | Univers officiel vérifié sans observation acquise. |
| | `UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR` | Aucun dénominateur officiel fiable. |
| `universe_type` | `OFFICIAL_CONTESTS`, `OFFICIAL_TERRITORIES`, `OFFICIAL_RECORDS`, `OFFICIAL_DOCUMENTS`, `OFFICIAL_FIELDS`, `OFFICIAL_PERIODS` | Nature du dénominateur officiel externe. |

## Historiques et rapprochements

| Vocabulaire | Codes |
|---|---|
| `party_lineage_type` | `MERGER`, `SPLIT`, `RENAME`, `COALITION`, `SUCCESSION` |
| `geo_lineage_type` | `SAME_BOUNDARY`, `SPLIT`, `MERGER`, `REDISTRICTED`, `PARENT_CHANGE` |
| `matching_method` | `OFFICIAL_IDENTIFIER`, `DOCUMENTED_CROSSWALK`, `HUMAN_REVIEW`, `NAME_ONLY` |

`NAME_ONLY` est conservé comme code de rejet/audit mais interdit par validation pour identifier une personne.

## Science et publication

| Vocabulaire | Codes |
|---|---|
| `metric_status` | `COMPUTED`, `NOT_COMPUTED` |
| `publication_status` | `PUBLICATION_READY`, `NOT_PUBLICATION_READY` |
| `claim_class` | `OBSERVED_FACT`, `DERIVED_DESCRIPTIVE`, `ASSOCIATION`, `PREDICTION`, `CAUSAL` |
| `license_status` | `REDISTRIBUTABLE`, `METADATA_ONLY`, `FORBIDDEN`, `UNKNOWN` |

Un fichier public ne peut avoir une licence `FORBIDDEN` ou `UNKNOWN`. Une ligne `INFERRED` ou `FORECAST` ne peut avoir la classe `OBSERVED_FACT`.
