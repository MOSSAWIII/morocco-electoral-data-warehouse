# Historique des résultats V16

Date d'arrêt du paquet : `2026-09-21`.

Le diagnostic est généré automatiquement dans `v16-result-history-report.json`. Il inventorie 9 élections, 3 715 concours et 32 937 lignes de résultats. Les sources acquises prouvent les valeurs reproduites dans V16, mais aucune ne fournit actuellement un historique officiel structuré associant explicitement statut, prise d'effet et publication aux lignes concernées. En conséquence, `fact_result_revision` reste vide : aucun statut n'est déduit de l'ancienneté d'une élection.

| election_id | scrutin | résultats présents | sources de valeurs | statut déclaré par la source | dates disponibles | historique/rectification | statut prouvable | source officielle encore nécessaire |
|---|---|---|---|---|---|---|---|---|
| LEG2002 | 2002-09-27 | aucun concours publié | aucune | aucun | métadonnées d'élection seulement | non | hors périmètre factuel | publication officielle détaillée si réintégration |
| LEG2007 | 2007-09-07 | partis, mobilisation | `TAFRA_LEGISLATIVE_RESULTS_2007` | aucun | acquisition 2026-09-09 | non | non | proclamation ou publication de l'autorité compétente |
| LEG2011 | 2011-11-25 | partis, mobilisation | `TAFRA_LEGISLATIVE_RESULTS_2011` | aucun | acquisition 2026-09-09 | non | non | proclamation ou publication de l'autorité compétente |
| COMM2015 | 2015-09-04 | partis communaux | `SRC_TAFRA_COMM2015_RAW_V9` | aucun | aucune date de publication prouvée | non | non | résultats communaux officiels datés avec statut |
| REG2015 | 2015-09-04 | partis, mobilisation | `TAFRA_REGIONAL_RESULTS_2015` | aucun | acquisition 2026-09-09 | non | non | proclamation ou publication de l'autorité compétente |
| LEG2016 | 2016-10-07 | partis, mobilisation | `TAFRA_LEGISLATIVE_RESULTS_2016` | aucun | acquisition 2026-09-09 | correction de la source Tafra, pas rectification officielle du résultat | non | proclamation et éventuelles décisions de rectification |
| LEG2021 | 2021-09-08 | partis, mobilisation | `TAFRA_LEGISLATIVE_RESULTS_2021` | aucun | acquisition 2026-09-09; métadonnée parlementaire 2021-09-17 non liée ligne par ligne | non | non | publication officielle détaillée reliant statut et résultats |
| COMM2021 | 2021-09-08 | partis communaux | `SRC_TAFRA_COMM2021_RAW_V9` | aucun | aucune date de publication prouvée | non | non | résultats communaux officiels datés avec statut |
| REG2021 | 2021-09-08 | partis, mobilisation | `TAFRA_REGIONAL_RESULTS_2021` | aucun | acquisition 2026-09-09 | non | non | proclamation ou publication de l'autorité compétente |

Les dates de création ou modification internes aux classeurs XLSX ne sont pas des dates de publication officielles. La date du scrutin n'est jamais substituée à `published_at`. Une date d'acquisition établit seulement le moment à partir duquel le projet peut avoir connu les octets acquis.

## Conditions de matérialisation

Une ligne de `fact_result_revision` n'est admissible que si ses octets sources épinglés contiennent un claim structuré reproduisant `revision_id`, `result_id`, `contest_id`, `result_status`, `valid_from` et `published_at` lorsqu'il est connu. La ligne conserve aussi `known_at`, `verification_method = STRUCTURED_SOURCE_CLAIM` et `verification_status = VERIFIED`. Toute rectification ou annulation doit conserver sa chaîne antérieure et, le cas échéant, sa décision juridique.

Le gate `RESULT_STATUS_KNOWN` relit la table DuckDB et les octets de preuve. En l'absence actuelle de claims officiels, il échoue avec huit lacunes `OFFICIAL_RESULT_STATUS_NOT_PROVEN`, une par élection chargée. Le gate `AS_OF_DATE_VALID` vérifie séparément la date d'arrêt matérialisée, les dates des éventuelles révisions et l'absence de données connues ou applicables dans le futur; il peut donc passer honnêtement avec zéro révision.
