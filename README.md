# Morocco Electoral Data Warehouse

Warehouse quantitatif consacré aux élections, à la représentation et à la gouvernance territoriale au Maroc. La release analytique actuelle est V13; V9 à V12 restent des baselines immuables.

## Principes

- Les RAW sont immuables et restent hors de Git.
- Le flux actuel est `RAW → STAGING → TABLES CANONIQUES VERSIONNÉES → EXPORTS`.
- PostgreSQL reste une option d'exploitation future, à déclencher sur un besoin concret ; Excel est l'export analytique actuel.
- Toute donnée est qualifiée : `OBSERVÉ`, `DÉRIVÉ`, `STRUCTURE VIDE`, `PILOTE` ou `BLOQUÉ`.
- Une valeur absente n’est jamais reconstruite sans source et une métrique dérivée n’est jamais présentée comme officielle.

## Produit final

Le projet vise quatre produits complémentaires, dans cet ordre :

1. des données électorales canoniques et versionnées ;
2. une provenance et des limites scientifiques explicites ;
3. un accès simple pour les analystes ;
4. des analyses de référence démontrant ce que les données permettent réellement de conclure.

La qualité protège ces produits, mais n'est pas un produit autonome. Le succès se mesure aux questions analytiques correctement traitées, pas au nombre de tables, documents ou contrôles.

Le cap d'expansion, de normalisation et de publication est défini dans le [roadmap du warehouse](docs/ROADMAP.md). Il applique une règle simple : collecter largement dans les RAW, puis intégrer strictement dans un modèle canonique unique.

## Organisation

- `src/morocco_elections/` : package, domaines, qualité, stockage, exports et compatibilité V9.
- `data/` : données locales ignorées par Git ; voir son README pour le contrat des zones.
- `docs/v9/ontology/` : les 15 documents UTF-8 de l’ontologie V9.
- `docs/v10/ontology/` : les 15 documents UTF-8 de l’ontologie V10.
- `docs/v11/ontology/` : les 15 documents UTF-8 de l’ontologie V11.
- `docs/v12/ontology/` : la documentation historique immuable de V12 (15 documents UTF-8).
- `docs/v13/ontology/` : la documentation de la release courante V13 (15 documents UTF-8).
- `docs/research/` : preuves historiques des qualifications et baselines QA ; elles ne constituent pas la roadmap active.
- `docs/architecture/` : règles de dépendance, flux et synthèse lisible de l'ontologie V1.
- `metadata/` : provenance physique, backlog GitHub et contrat machine-readable `ontology_v1.json`.
- `database/` et `infrastructure/postgres/` : contrats d'une option PostgreSQL future.
- `tests/unit/`, `tests/integration/` et `tests/fixtures/synthetic/` : stratégie de test.

V13 contient 71 onglets. Elle préserve V12 et ajoute 639 courses électorales, 10 883 résultats `contest × parti` et 639 observations de mobilisation pour les législatives 2007–2021 et les régionales 2015–2021. Le fichier 2002 reste `ARCHIVE_ONLY`; les cellules absentes restent `NULL` et les découpages 2007/2011 demeurent historiques.

La commande `build v12` reconstruit le classeur depuis les RAW, les décisions versionnées et le bootstrap historique V8. Elle ne lit aucun classeur V9, V10 ou V11 comme entrée. V8 reste temporairement nécessaire pour les tables héritées dont les sources physiques ne sont pas encore disponibles séparément ; cette dépendance est explicite et n'entraîne plus une chaîne de releases.

## Point d’entrée de la release courante

Commencer par [`docs/v13/ontology/00_INDEX_ET_MODE_EMPLOI.txt`](docs/v13/ontology/00_INDEX_ET_MODE_EMPLOI.txt). Les tables centrales sont volontairement peu nombreuses :

- `DIM_GEO`, `DIM_TIME`, `DIM_PARTY`, `DIM_PERSON` et `DIM_ELECTION` portent les clés partagées ;
- `RESULTS` est au grain `commune × parti × élection` ;
- `COMMUNE_ELECTION_PANEL` est au grain `commune × élection` ;
- `LOCAL_MANDATES` et `PARLIAMENTARY_MANDATES` portent les mandats observés ;
- `LOCAL_COUNCIL_CONTROL` sépare résultat électoral et contrôle communal ;
- `FACT_OBSERVATION` porte les observations socio-économiques longues avec leur millésime réel ;
- `PARLIAMENTARY_QUESTIONS` est au grain `source × question écrite`.
- `DIM_ELECTORAL_CONTEST` décrit chaque course datée et son découpage ; `FACT_ELECTION_RESULT` et `FACT_ELECTORAL_MOBILIZATION` portent le nouveau cœur multi-scrutins.

Avant tout calcul de taux, vérifier dans le dictionnaire que le dénominateur est réellement publié. Une clé nullable, notamment `PARLIAMENTARY_QUESTIONS.person_id`, ne doit jamais être remplacée par un rapprochement implicite.

Le contrat logique destiné aux prochaines intégrations se trouve dans
[`metadata/ontology_v1.json`](metadata/ontology_v1.json), avec une synthèse dans
[`docs/architecture/ONTOLOGY_V1.txt`](docs/architecture/ONTOLOGY_V1.txt). Il
introduit notamment `contest_id` pour distinguer une course électorale datée
d'une simple entité administrative. Son existence ne signifie pas que toutes
les structures cibles sont déjà alimentées : leur maturité est déclarée
`CURRENT`, `PARTIAL` ou `PLANNED`.

## Installation

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install --no-deps --editable .
```

La racine des données est `<repo>/data` par défaut. Elle peut être déplacée sans changer le code :

```powershell
$env:ELECTIONS_DATA_DIR = "D:\warehouse-electoral-data"
```

Un argument `--data-dir` a priorité sur cette variable.

## Commandes structurées

```powershell
python -m morocco_elections validate --mode ci
python -m morocco_elections validate --mode full
python -m morocco_elections sources catalog
python -m morocco_elections sources acquire --source-id <ID_CATALOGUE> --input <fichier> --as-of AAAA-MM-JJ
python -m morocco_elections sources inventory --as-of AAAA-MM-JJ
python -m morocco_elections sources profile-electoral-archives --baseline v12 --as-of AAAA-MM-JJ
python -m morocco_elections identity build-registry --baseline v12 --as-of AAAA-MM-JJ
python -m morocco_elections qualify electoral-archives --baseline v12 --as-of AAAA-MM-JJ
python -m morocco_elections build v9
python -m morocco_elections docs v9
python -m morocco_elections build v10
python -m morocco_elections docs v10
python -m morocco_elections build v11
python -m morocco_elections docs v11
python -m morocco_elections qualify parliament --baseline v11 --as-of 2026-09-09
python -m morocco_elections build v12
python -m morocco_elections docs v12
python -m morocco_elections build v13
python -m morocco_elections docs v13
python -m morocco_elections analyze v12
python -m morocco_elections analyze v13
python -m morocco_elections validate --mode full --release v10 --baseline v9
python -m morocco_elections validate --mode full --release v11 --baseline v10
python -m morocco_elections validate --mode full --release v12 --baseline v11
python -m morocco_elections validate --mode full --release v13 --baseline v12
python -m morocco_elections analyze v11
python -m morocco_elections quality baseline --release v10 --as-of 2026-09-08
python -m morocco_elections qualify electoral-denominators --baseline v10 --as-of 2026-09-08
python -m morocco_elections qualify local-presidencies --baseline v10 --as-of 2026-09-08
python -m morocco_elections qualify hcp-indicators --baseline v10 --as-of 2026-09-08
python -m morocco_elections quality baseline --release v11 --as-of 2026-09-08
python -m morocco_elections github publish-backlog
```

Le mode `ci` fonctionne sans données. Le mode `full` vérifie les empreintes, volumes, documents, onglets et différences autorisées de la release demandée sans écrire de fichier.

`sources acquire` accepte un fichier local avec `--input` ou une URL HTTP(S) avec `--url`. La commande conserve les octets sous `data/raw/<domaine>/acquisitions/`, calcule leur empreinte, inventorie leur structure et écrit un enregistrement local. Ce dépôt RAW ne constitue jamais une autorisation d'ingestion canonique.

Les commandes de qualification restent disponibles pour reproduire les décisions historiques. Elles ne doivent être relancées ou étendues qu'en présence d'une nouvelle source ou preuve crédible. Une qualification `NO_GO` ne déclenche ni release ni export.

`analyze v11` lit le classeur validé sans rien écrire et exécute cinq analyses de référence. Chaque résultat affiche son périmètre et sa limitation scientifique ; `--format json` fournit la même sortie sous forme structurée.

## Cap actuel

La roadmap active est volontairement limitée :

1. acquérir et profiler par lots les sources électorales, parlementaires et territoriales prometteuses ;
2. ajuster l'ontologie et les registres d'identités sur les structures réellement observées ;
3. intégrer seulement les sources traçables, réutilisables et raccordables qui apportent une capacité analytique ;
4. préparer PostgreSQL seulement lorsqu'un besoin d'interrogation, de collaboration ou de performance le justifie.

Watchlist passive, sans développement en l'absence de preuve nouvelle : inscrits communaux 2015–2021, 135 présidences non résolues, conseils communaux 2015 et SMIIG. Les 25 couples HCP restés `NO_GO` ne sont pas chargés.

Règles de proportionnalité : une release correspond à un changement des données canoniques ou de leur schéma ; un qualificateur complet suppose une source candidate crédible ; une abstraction partagée suppose au moins deux usages réels ; un seul chantier principal de données est conduit à la fois.

## Compatibilité V9

Les anciens points d’entrée restent disponibles :

```powershell
python build_v9.py
python generate_v9_documentation.py
```

Le constructeur écrit dans `data/exports/excel/v9/`. Le générateur documentaire écrit dans `docs/v9/ontology/`.

## Données et sécurité

Les chemins attendus sont définis dans `metadata/source_manifest.json`. RAW, V8, V9, Parquet, Shapefiles, archives, exports PostgreSQL et secrets sont ignorés par Git. Ne jamais contourner cette règle avec `git add -f`.

## Développement

La branche `main` reçoit les changements par pull request après réussite de la CI. Utiliser `research/...` pour les qualifications, `feat/...` ou `fix/...` pour les fonctions métier et `chore/...` pour l’infrastructure.

Le backlog versionné définit huit issues et quatre jalons dans `metadata/github_backlog.json`. Le dépôt distant est privé ; le backlog sert de registre de pilotage et se publie avec `python -m morocco_elections github publish-backlog`.
