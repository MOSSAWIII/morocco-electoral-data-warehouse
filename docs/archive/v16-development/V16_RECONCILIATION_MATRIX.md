# Matrice exhaustive des rapprochements V16

La table `fact_result_reconciliation` est générée depuis le DuckDB V16 et les empreintes du manifeste des sources. Elle couvre les 3 715 concours réellement présents dans `dim_electoral_contest`. Quatre contrôles sont applicables à chaque concours : participation, comptabilité des bulletins, voix partisanes contre suffrages valides et sièges attribués contre sièges à pourvoir. Le produit attendu et matérialisé est donc de 14 860 lignes, avec exactement une ligne par `(contest_id, metric)`.

Le diagnostic courant produit 14 860 `NOT_COMPUTABLE`, aucun `PASS` artificiel et aucun `FAIL` masqué. Cette distribution est imposée par les faits : sur 639 lignes de mobilisation, 187 ont des inscrits, 82 des suffrages valides, 547 un nombre de sièges et 639 un taux publié, mais aucune n'a de votants, de bulletins invalides ou de bulletins blancs. Les 3 076 synthèses communales conservent également leur taux publié, soit un agrégat inspectable pour chacun des 3 715 concours, mais aucun taux ne peut être recalculé sans nombre de votants. Aucun univers externe vérifié de partis/listes ou d'attributions de sièges n'est disponible. Les cellules absentes restent `NULL`; `missing_components` énumère les composants manquants.

Les contrôles détail–agrégat sont explicitement non applicables en l'absence de totaux agrégés indépendants. Les rangs, gagnants, marges, HHI et ENP sont conditionnels et explicitement non applicables tant qu'un univers externe complet de partis/listes n'est pas vérifié. Ils ne produisent donc aucune ligne, conformément à l'invariant « zéro statut pour un contrôle non applicable ».

Les sources Tafra sont qualifiées comme copies secondaires attribuées à elections.ma. Le classeur communal 2015 comporte 1 538 lignes de concours. Le fichier des élus comporte 31 482 personnes et 1 538 communes distinctes, mais ne constitue pas un univers officiel exhaustif des candidatures; il ne débloque aucun total partisan.

Chaque rapprochement conserve l'identifiant du concours et du contrôle, les valeurs observée et recalculée, l'écart, la tolérance, le statut, le motif structuré, la source, la preuve, la méthode et les composants manquants. Le gate `METRIC_RECONCILED` relit la table DuckDB, la compare au contexte, puis régénère toute la matrice depuis les faits et les octets épinglés. Une modification coordonnée de la table et du contexte échoue donc également.

Artefacts :

- `data/exports/open/v16-development/morocco_elections_v16.duckdb`
- `data/exports/open/v16-development/v16_reconciliation_report.json`
