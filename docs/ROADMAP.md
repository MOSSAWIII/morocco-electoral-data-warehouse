# Roadmap — Open Moroccan Electoral Data Warehouse

## Cap

Le projet construit un socle ouvert, profond et cohérent pour relier territoires, élections, partis, personnes, mandats, gouvernance, activité parlementaire et contexte socio-économique. Il n'existe qu'un produit logique : les formats Excel, CSV, Parquet, DuckDB ou SQL sont des accès différents aux mêmes faits canoniques.

La release publique courante est V14.1. Le classeur V13 reste son socle Excel immuable et V14 reste son premier paquet parlementaire immuable. La suite suit ce flux :

```text
SOURCES → RAW IMMUTABLES → PROFILAGE → IDENTITÉS/CROSSWALKS
        → FAITS CANONIQUES → CUBES → EXPORTS/ANALYSES
```

État courant : le cœur électoral V13 est publié, V14 ajoute l'activité parlementaire longitudinale et V14.1 en corrige la validité analytique sans nouvelle source. La prochaine vague porte d'abord sur les identités, affiliations et couches analytiques parlementaires démontrables, puis sur le territoire HCP.

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

Le catalogue [`metadata/acquisition_catalog.json`](../metadata/acquisition_catalog.json) pilote quatre états factuels :

- `TO_ACQUIRE` : source ou famille crédible encore absente des RAW ;
- `ACQUIRED` : octets conservés et inventoriés, sans ingestion canonique ;
- `INTEGRATED` : périmètre qualifié chargé dans la release canonique indiquée ;
- `WATCHLIST` : chantier gelé jusqu'à une preuve nouvelle.

Au 12 septembre 2026, le catalogue compte 4 familles `TO_ACQUIRE`, 10 sources `ACQUIRED`, 14 sources `INTEGRATED` dans V13–V14 et 4 chantiers en `WATCHLIST`. Les 73 ressources physiques acquises sont toutes classées.

Les domaines de collecte sont : élections, Parlement, gouvernance, partis, HCP, finances locales, géographie et contexte. Une acquisition n'autorise jamais automatiquement l'ingestion canonique. Elle produit un fichier RAW immuable et un profil local ignorés par Git.

Sortie attendue : un patrimoine de sources classées, une carte de couverture et une liste courte de candidats réellement intégrables. Aucune release n'est créée.

## Phase 2 — Profilage transversal

Pour chaque fichier collecté, relever au minimum : format, taille, empreinte, feuilles ou tables, colonnes et volumes. Les qualifications ultérieures ajoutent grain, années, clés candidates, valeurs manquantes, doublons, domaines, données personnelles et compatibilité avec V13.

Chaque source est alors classée :

- `CANONICAL_CANDIDATE`
- `REFERENCE`
- `CONTEXTUAL`
- `PILOT`
- `BLOCKED`
- `ARCHIVE_ONLY`

Une source ne devient candidate canonique que si producteur, grain, période, clés, réutilisation et limites sont compris.

Le premier classement des 73 ressources acquises donne 69 `CANONICAL_CANDIDATE`, 3 `REFERENCE` et 1 `ARCHIVE_ONLY`; aucune ne reste `NOT_EVALUATED`. Cette classe est un tri de travail, jamais une autorisation d'ingestion. La liste courte est volontairement limitée :

1. la base communale HCP CEE 2023–2024 ;
2. la base HCP des douars et ménages 2024 ;
3. les bases HCP logement urbain, migration interne et transport domicile-travail, une à la fois.

Les questions écrites et orales sont intégrées dans V14. Les engagements ministériels restent acquis mais hors de la liste courte.

## Phase 3 — Ontologie V1

L'ontologie commune reste petite : territoire, élection, parti/alliance, personne, institution, mandat, fonction, conseil, activité parlementaire, indicateur, programme/budget, événement et source/preuve.

Les relations temporelles portent `valid_from`, `valid_to`, `observation_date`, `publication_date` et `retrieved_at` selon leur nature. Cela s'applique notamment aux découpages, affiliations, mandats, fonctions, présidences et compositions institutionnelles.

L'ontologie V1.1 est matérialisée par V13 pour le cœur électoral, étendue dans V14 pour le Parlement et clarifiée dans V14.1 pour distinguer auteur source, personne, couverture et exposition.

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
- Excel : export local d'inspection et d'usage courant, distinct du paquet Git léger.
- DuckDB : interrogation locale de tous les fichiers.
- PostgreSQL : service ultérieur si un besoin réel apparaît.

Ces formats ne créent ni modèles ni règles métier concurrents.

## Phase 10 — PostgreSQL conditionnel

La migration commence seulement si collaboration simultanée, API, mises à jour fréquentes, volumes, transactions ou contrôle d'accès la justifient. Le schéma SQL sera dérivé du canonique et Excel restera un export; PostgreSQL ne deviendra pas une deuxième source de vérité.

## Releases indicatives

- **V13 — Cœur électoral étendu** : réalisée; élections, mobilisation, découpages historiques et diffusion multi-format.
- **V14 — Parlement longitudinal** : questions écrites et orales, dates de réponse publiées et trajectoires consolidées.
- **V14.1 — Validité analytique** : sémantique corrigée, couverture `UNKNOWN`, temps explicite, auteurs source séparés des personnes, exposition et zéros issus des mandats.
- **V15 — Territoire enrichi** : HCP, établissements économiques, douars, habitat et mobilités selon les grains publiés.
- **V16 — Complétude électorale ciblée** : dénominateurs, candidatures, sièges, élections partielles et archives exploitables.

Ces noms ne sont pas des engagements rigides. Des domaines peuvent être regroupés lorsqu'un lot cohérent débloque une capacité analytique; une simple collecte ne déclenche jamais une version.

## Prochain enchaînement

1. Publier et éprouver V14.1 depuis un environnement vierge.
2. Améliorer les raccordements d'identité uniquement avec des preuves déterministes.
3. Historiser affiliations et groupes lorsque leurs intervalles sont documentés.
4. Ajouter les couches dérivées de sujets, institutions et géographies avec méthode et confiance.
5. Relier les engagements ministériels déjà acquis, puis reprendre HCP source par source.
6. Ne réactiver les sources de gouvernance bloquées qu'avec une preuve nouvelle.
7. Déclencher PostgreSQL seulement lorsqu'un besoin opérationnel mesurable apparaît.

Le projet est réussi lorsqu'une personne extérieure peut relier les données par des identifiants stables, retrouver la source de chaque valeur importante, comprendre les lacunes et exécuter des analyses sans connaître l'histoire interne du dépôt.
