# Guide analytique

Le produit est un unique fichier DuckDB. Les 45 tables matérialisées restent la
source de vérité; dix vues `analytics_*` forment une couche de lecture sans
copier les faits. Le fichier `table-catalog.json` décrit, pour chaque table, son
rôle, son grain, sa clé logique, ses clés de relation autorisées, son usage et
ses limites. Il catalogue séparément les vues.

## Construire et ouvrir

```powershell
morocco-elections build
morocco-elections validate
morocco-elections audit --summary
morocco-elections package
morocco-elections status
```

```python
import duckdb

db = duckdb.connect(
    "data/exports/open/warehouse/morocco_elections.duckdb",
    read_only=True,
)
print(db.sql("FROM analytics_elections ORDER BY election_date"))
```

La reconstruction utilise uniquement les sources déclarées et épinglées. Les
commandes refusent une divergence de taille ou de SHA-256. `validate` contrôle
le paquet, `audit` explique les limites, et `package` valide puis archive le
paquet canonique existant sans le reconstruire.

## Vues de consommation

| Vue | Grain | Usage |
|---|---|---|
| `analytics_elections` | une élection | scrutins disponibles et provenance |
| `analytics_contests` | un concours et son régime applicable | concours, territoire, type de liste et droit applicable |
| `analytics_party_results` | un résultat de parti/liste dans un concours | résultats territoriaux ou par parti; couverture non présumée |
| `analytics_seats` | un résultat de parti/liste | sièges lorsqu'ils existent; disponibilité explicite |
| `analytics_mobilization` | un concours | inscrits, votants, bulletins et participation recalculable |
| `analytics_geographies` | une géographie interne | hiérarchie, population et statut de liaison HCP |
| `analytics_quality_controls` | un contrôle et une métrique par concours | `PASS`, `FAIL` et `NOT_COMPUTABLE` |
| `analytics_coverage` | un périmètre de couverture par publication | numérateur, dénominateur et statut de couverture |
| `analytics_provenance` | une source | autorité, URL, période, licence et statut |
| `analytics_national_summary` | une élection observée | agrégats descriptifs nationaux avec limite explicite |

Les requêtes prêtes à exécuter sont dans
[`examples/analytical_queries.sql`](../examples/analytical_queries.sql). Elles
couvrent les quinze usages minimaux du catalogue, notamment les données
manquantes, les 177 identifiants communaux non reliés à l'univers HCP et les
14 860 contrôles actuellement non calculables.

## Matrice des questions

| Question analytique | Vue et grain | Préconditions testées | Statut actuel | Limite |
|---|---|---|---|---|
| Q01 — Quelles élections sont présentes ? | `analytics_elections`, une élection | clé `election_id` unique | Disponible | inventaire observé |
| Q02 — Quels concours composent une élection ? | `analytics_contests`, un concours | clé `contest_id` unique | Disponible | 354 régimes non résolus |
| Q03 — Quels résultats sont observés dans un territoire ? | `analytics_party_results`, un résultat de liste par concours | aucune pour lecture descriptive | Disponible | exhaustivité inconnue |
| Q04 — Quels résultats sont observés pour un parti ? | `analytics_party_results`, un résultat de liste par concours | aucune pour lecture descriptive | Disponible | comparabilité historique non établie |
| Q05 — Quels sièges sont disponibles ? | `analytics_seats`, un résultat de liste par concours | `availability_status = 'AVAILABLE'` | Partiel | les absences restent `NULL` |
| Q06 — La participation peut-elle être recalculée ? | `analytics_mobilization`, un concours | inscrits non nuls et votants présents | Non calculable | votants absents |
| Q07 — Quelle hiérarchie territoriale est vérifiée ? | `analytics_geographies`, une géographie | relation parent prouvée | Partiel | relations historiques incomplètes |
| Q08 — Quelle population officielle est raccordée ? | `analytics_geographies`, une géographie | `hcp_link_status = 'VERIFIED'` | Partiel | 177 identités non reliées |
| Q09 — Quelle couverture est démontrée ? | `analytics_coverage`, un scope de publication | univers officiel explicite | Partiel | allocation nationale de sièges 2021 disponible; sept scrutins sans univers de résultats |
| Q10 — Quelles entrées de mobilisation manquent ? | `analytics_mobilization`, un concours | aucune | Disponible | absence non assimilée à zéro |
| Q11 — Quels contrôles sont calculables ? | `analytics_quality_controls`, une métrique par concours | composants admissibles présents | Partiel | 14 860 `NOT_COMPUTABLE` |
| Q12 — Quelle est la provenance d'un résultat ? | résultats + `analytics_provenance`, un résultat | `source_id` déclaré | Disponible | droits source par source |
| Q13 — Quelles licences sont déclarées ? | `analytics_provenance`, une source | décision de source présente | Partiel | autorisation de release séparée |
| Q14 — Quelles identités territoriales restent ouvertes ? | `analytics_geographies`, une géographie | statut de crosswalk calculé | Disponible | 177 `UNRESOLVED` |
| Q15 — Quelle allocation nationale officielle peut être publiée ? | `coverage_universe_member`, un parti ayant obtenu des sièges en 2021 | page officielle de la Chambre épinglée et 12 membres ré-extraits | Disponible pour `LEG2021` | 395 sièges; ne prouve ni l'univers des votes ni les allocations locales détaillées |

## Règles d'analyse

Une somme de résultats observés n'est pas un total officiel tant qu'un univers
externe vérifié ne démontre pas l'exhaustivité. Une part ou un taux n'est
calculable que si son dénominateur est présent et admissible. La vue de
mobilisation applique cette règle et renvoie `NULL` avec
`denominator_status = 'NOT_COMPUTABLE'` sinon.

Les valeurs `NULL` restent absentes : ne pas les convertir en zéro. Conserver
dans toute restitution les colonnes de source, qualité, couverture, validation
et limites. Les statuts `PARTIAL`, `UNRESOLVED`, `NOT_COMPUTABLE` et
`UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR` sont des résultats utiles, pas des
erreurs à masquer.

Les comparaisons territoriales exigeant un identifiant HCP officiel doivent
filtrer `analytics_geographies.hcp_link_status = 'VERIFIED'`. Les lignes
`UNRESOLVED` restent consultables par `geo_id` pour les analyses qui n'exigent
pas cette équivalence. Aucune correspondance par nom n'est officielle.

`audit --summary` publie le nombre de contrôles calculables par élection. Dans
l'état courant, aucun des contrôles n'est calculable faute de composants
officiels suffisants : COMM2015 et COMM2021 en comptent chacun 6 152,
LEG2007 380, LEG2011 368, LEG2016 736, LEG2021 416, REG2015 328 et REG2021
328. Le rapport complet `reconciliation-report.json` ventile aussi ces nombres
par métrique.

## Limites actuelles

- La complétude nationale des résultats n'a pas de dénominateur officiel
  vérifié; `analytics_national_summary` reste donc descriptif et porte
  `UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR`.
- Les 177 identifiants communaux hérités non reliés à l'univers HCP restent
  `UNRESOLVED`.
- Les 14 860 rapprochements sans entrées admissibles restent
  `NOT_COMPUTABLE`; ils ne bloquent pas les descriptions compatibles.
- Les sièges sont absents de plusieurs séries et restent `NULL` avec
  `NOT_AVAILABLE`.
- Aucun statut final, taux, total, rattachement territorial ou historique de
  parti n'est inféré sans preuve institutionnelle.

Ces limites sont aussi exposées par `audit --summary`, les vues analytiques et
les tables de preuve. Il n'est pas nécessaire de consulter les archives pour
utiliser le produit courant.
