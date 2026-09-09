# Morocco Electoral Data Warehouse

Warehouse quantitatif consacré aux élections, à la représentation et à la gouvernance territoriale au Maroc. La release analytique actuelle est V11; V9 et V10 restent des baselines immuables.

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

## Organisation

- `src/morocco_elections/` : package, domaines, qualité, stockage, exports et compatibilité V9.
- `data/` : données locales ignorées par Git ; voir son README pour le contrat des zones.
- `docs/v9/ontology/` : les 15 documents UTF-8 de l’ontologie V9.
- `docs/v10/ontology/` : les 15 documents UTF-8 de l’ontologie V10.
- `docs/v11/ontology/` : les 15 documents UTF-8 de l’ontologie V11.
- `docs/research/` : preuves historiques des qualifications et baselines QA ; elles ne constituent pas la roadmap active.
- `docs/architecture/` : règles de dépendance et flux futurs.
- `metadata/` : provenance physique des sources et backlog GitHub.
- `database/` et `infrastructure/postgres/` : contrats d'une option PostgreSQL future.
- `tests/unit/`, `tests/integration/` et `tests/fixtures/synthetic/` : stratégie de test.

V11 contient 67 onglets. Elle préserve intégralement V10 et ajoute à `FACT_OBSERVATION` les 1 538 populations légales 2014 et les 1 538 populations municipales 2024 validées par V10-QA-3. Aucun des 25 couples indicateur-millésime `NO_GO` n’est ingéré.

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
python -m morocco_elections build v9
python -m morocco_elections docs v9
python -m morocco_elections build v10
python -m morocco_elections docs v10
python -m morocco_elections build v11
python -m morocco_elections docs v11
python -m morocco_elections validate --mode full --release v10 --baseline v9
python -m morocco_elections validate --mode full --release v11 --baseline v10
python -m morocco_elections quality baseline --release v10 --as-of 2026-09-08
python -m morocco_elections qualify electoral-denominators --baseline v10 --as-of 2026-09-08
python -m morocco_elections qualify local-presidencies --baseline v10 --as-of 2026-09-08
python -m morocco_elections qualify hcp-indicators --baseline v10 --as-of 2026-09-08
python -m morocco_elections quality baseline --release v11 --as-of 2026-09-08
python -m morocco_elections github publish-backlog
```

Le mode `ci` fonctionne sans données. Le mode `full` vérifie les empreintes, volumes, documents, onglets et différences autorisées de la release demandée sans écrire de fichier.

Les commandes de qualification restent disponibles pour reproduire les décisions historiques. Elles ne doivent être relancées ou étendues qu'en présence d'une nouvelle source ou preuve crédible. Une qualification `NO_GO` ne déclenche ni release ni export.

## Cap actuel

La roadmap active est volontairement limitée :

1. produire des analyses de référence à partir de V11 ;
2. qualifier une nouvelle source seulement après avoir confirmé son accessibilité, sa provenance et son potentiel — les questions parlementaires sont le prochain candidat ;
3. préparer PostgreSQL seulement lorsqu'un besoin d'interrogation, de collaboration ou de performance le justifie.

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
