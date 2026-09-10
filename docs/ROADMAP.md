# Roadmap — Open Moroccan Electoral Data Warehouse

## Cap

Le projet construit un socle ouvert, profond et cohérent pour relier territoires, élections, partis, personnes, mandats, gouvernance, activité parlementaire et contexte socio-économique. Il n'existe qu'un produit logique : les formats Excel, CSV, Parquet, DuckDB ou SQL sont des accès différents aux mêmes faits canoniques.

La release courante est V13. V9 à V12 restent immuables. La suite suit ce flux :

```text
SOURCES → RAW IMMUTABLES → PROFILAGE → IDENTITÉS/CROSSWALKS
        → FAITS CANONIQUES → CUBES → EXPORTS/ANALYSES
```

## Règles de conduite

- Acquérir largement, intégrer strictement.
- Conserver chaque octet RAW avec URL, producteur, dates, licence, taille et SHA-256.
- Ne jamais corriger un RAW : les corrections vivent dans les crosswalks et tables normalisées.
- Conserver les identifiants source et leur correspondance vers les identifiants canoniques.
- Ne jamais confondre présence, couverture, exactitude externe et utilité analytique.
- Conserver les valeurs absentes à `NULL`; ne jamais reconstruire silencieusement une donnée.
- Ne produire une release que lorsqu'une capacité analytique ou le schéma canonique change.
- Ne développer un qualificateur spécialisé qu'après identification d'une source crédible.

## Phase 1 — Acquisition organisée

Le catalogue [`metadata/acquisition_catalog.json`](../metadata/acquisition_catalog.json) pilote trois états seulement :

- `ACTIVE` : source précise et prête à être acquise ;
- `COLLECTING` : portail ou famille connu, inventaire encore en cours ;
- `WATCHLIST` : chantier gelé jusqu'à une preuve nouvelle.

Les domaines de collecte sont : élections, Parlement, gouvernance, partis, HCP, finances locales, géographie et contexte. Une acquisition n'autorise jamais automatiquement l'ingestion canonique. Elle produit un fichier RAW immuable et un profil local ignorés par Git.

Sortie attendue : un patrimoine de sources classées, une carte de couverture et une liste courte de candidats réellement intégrables. Aucune release n'est créée.

## Phase 2 — Profilage transversal

Pour chaque fichier collecté, relever au minimum : format, taille, empreinte, feuilles ou tables, colonnes et volumes. Les qualifications ultérieures ajoutent grain, années, clés candidates, valeurs manquantes, doublons, domaines, données personnelles et compatibilité avec V12.

Chaque source est alors classée :

- `CANONICAL_CANDIDATE`
- `REFERENCE`
- `CONTEXTUAL`
- `PILOT`
- `BLOCKED`
- `ARCHIVE_ONLY`

Une source ne devient candidate canonique que si producteur, grain, période, clés, réutilisation et limites sont compris.

## Phase 3 — Ontologie V1

L'ontologie commune reste petite : territoire, élection, parti/alliance, personne, institution, mandat, fonction, conseil, activité parlementaire, indicateur, programme/budget, événement et source/preuve.

Les relations temporelles portent `valid_from`, `valid_to`, `observation_date`, `publication_date` et `retrieved_at` selon leur nature. Cela s'applique notamment aux découpages, affiliations, mandats, fonctions, présidences et compositions institutionnelles.

L'ontologie V1.1 est matérialisée par V13 pour le cœur électoral; elle sera étendue sans casser les identifiants existants.

## Phase 4 — Registre d'identités

Le registre commun relie chaque identifiant source à une entité canonique :

```text
entity_type, source_system, source_record_id, canonical_id,
source_label, normalized_label, valid_from, valid_to,
match_method, confidence, evidence_id, review_status
```

Identifiants centraux : `geo_id`, `person_id`, `party_id`, `election_id`, `institution_id`, `mandate_id`, `topic_id`, `indicator_id` et `source_id`.

- Géographie : priorité aux codes, parents administratifs et dates; jamais au seul nom.
- Personnes : Unicode arabe/français, identifiants déterministes, aucune fusion sur le seul nom.
- Partis : distinguer organisation, code source, symbole, alliance, fusion, scission et affiliation datée.

Une clé inconnue reste explicitement inconnue; elle n'est pas remplacée par un rapprochement implicite.

## Phase 5 — Faits canoniques

Le canonique converge vers peu de tables longues :

| Fait | Grain cible |
|---|---|
| `FACT_ELECTION_RESULT` | territoire × élection × parti × circonscription |
| `FACT_ELECTORAL_MOBILIZATION` | territoire × élection |
| `FACT_CANDIDACY` | personne × élection × circonscription × candidature |
| `FACT_MANDATE` | personne × institution × mandat × début de validité |
| `FACT_LOCAL_GOVERNANCE` | territoire × période de gouvernance × parti × rôle |
| `FACT_PARLIAMENTARY_ACTIVITY` | activité publiée |
| `FACT_OBSERVATION` | territoire × millésime × indicateur |
| `FACT_POLITICAL_EVENT` | événement daté |

Les champs observés, normalisés et dérivés restent distinguables et remontent à leur source.

## Phase 6 — Vagues d'intégration

L'ordre est piloté par les sources réellement disponibles, selon :

```text
valeur analytique × couverture × fiabilité ÷ coût d'intégration
```

1. **Cœur électoral** : historique, candidatures, mobilisation, sièges, élections partielles, découpages.
2. **Pouvoir et gouvernance** : présidences, exécutifs, conseils, changements, budgets et programmes.
3. **Territoire et socio-économie** : recensements, finances, équipements, accessibilité et millésimes réels.
4. **Activité parlementaire** : périodes supplémentaires, questions orales, propositions, commissions et votes publiés.
5. **Contexte** : événements, programmes, médias, opinion et chocs, sans les confondre avec les faits centraux.

## Phase 7 — Cubes analytiques

Les cubes sont toujours dérivés des faits canoniques :

1. `GEO × PARTY × ELECTION` — voix, parts, sièges, rang, marge, HHI, ENP, swing.
2. `GEO × ELECTION` — inscrits, votants, participation, abstention, invalides.
3. `PERSON × PARTY × MANDATE × TIME` — candidatures, mandats, fonctions et changements.
4. `PERSON × PERIOD × ACTIVITY_TYPE × TOPIC` — activité parlementaire et réponses publiées.
5. `GEO × PARTY × GOVERNANCE_PERIOD` — sièges, présidence, exécutif et contrôle.
6. `GEO × INDICATOR × OBSERVATION_YEAR` — démographie, emploi, éducation, habitat et services.
7. `GEO × INSTITUTION × PROGRAM × YEAR` — budgets, dépenses, investissements et projets.

## Phase 8 — Analyses de référence

Les analyses sont les tests fonctionnels du warehouse : progression des partis, mobilisation, fragmentation, contrôle des conseils, trajectoires d'élus, activité parlementaire, différences territoriales et effets de découpage. Une nouvelle table doit répondre à une question utile ou apporter une dimension nécessaire à une telle réponse.

## Phase 9 — Publication ouverte

Une release publique contient le canonique, le dictionnaire, l'ontologie, la provenance, les checksums, la couverture, le changelog et quelques requêtes reproductibles.

- Parquet : diffusion canonique compacte.
- CSV : compatibilité universelle.
- Excel : inspection et usage courant.
- DuckDB : interrogation locale de tous les fichiers.
- PostgreSQL : service ultérieur si un besoin réel apparaît.

Ces formats ne créent ni modèles ni règles métier concurrents.

## Phase 10 — PostgreSQL conditionnel

La migration commence seulement si collaboration simultanée, API, mises à jour fréquentes, volumes, transactions ou contrôle d'accès la justifient. Le schéma SQL sera dérivé du canonique et Excel restera un export; PostgreSQL ne deviendra pas une deuxième source de vérité.

## Releases indicatives

- **V13 — Cœur électoral étendu** : nouvelles élections, candidatures, mobilisation ou découpages.
- **V14 — Gouvernance territoriale** : présidences, conseils, fonctions, budgets ou programmes suffisamment prouvés.
- **V15 — Territoire enrichi** : HCP, finances et équipements comparables dans le temps.
- **V16 — Parlement étendu** : périodes et formes d'activité supplémentaires, trajectoires consolidées.

Ces noms ne sont pas des engagements rigides. Des domaines peuvent être regroupés lorsqu'un lot cohérent débloque une capacité analytique; une simple collecte ne déclenche jamais une version.

## Prochain enchaînement

Le premier cycle est désormais réalisé : catalogue, acquisition des sept archives électorales,
profil consolidé, ontologie V1, registre des identités et qualification groupée. Cette qualification
autorise six sources dans des périmètres de mesure fermés; 2002 reste `ARCHIVE_ONLY`.

1. Construire les faits électoraux V13 uniquement à partir des 23 périmètres `GO`.
2. Vérifier les deux cubes centraux `contest × parti × élection` et `contest × élection` par des analyses de référence.
3. Publier V13 dans un modèle canonique unique, puis en dériver Parquet, CSV, DuckDB et Excel.
4. Ajouter ensuite une seule vague de données à la fois, choisie selon sa valeur analytique et sa preuve disponible.
5. Aborder la gouvernance, le territoire/HCP et le Parlement étendu sans faire dépendre un domaine des blocages d'un autre.
6. Déclencher PostgreSQL seulement lorsqu'un besoin opérationnel mesurable apparaît.

Le projet est réussi lorsqu'une personne extérieure peut relier les données par des identifiants stables, retrouver la source de chaque valeur importante, comprendre les lacunes et exécuter des analyses sans connaître l'histoire interne du dépôt.
