# Morocco Electoral Data Warehouse

Warehouse quantitatif consacré aux élections, à la représentation et à la gouvernance territoriale au Maroc. La release analytique actuelle est V10; V9 reste une baseline immuable.

## Principes

- Les RAW sont immuables et restent hors de Git.
- Le flux autorisé est `RAW → STAGING → PROCESSED → POSTGRESQL → EXPORTS`.
- PostgreSQL deviendra la couche canonique ; Excel restera un produit d’export.
- Toute donnée est qualifiée : `OBSERVÉ`, `DÉRIVÉ`, `STRUCTURE VIDE`, `PILOTE` ou `BLOQUÉ`.
- Une valeur absente n’est jamais reconstruite sans source et une métrique dérivée n’est jamais présentée comme officielle.

## Organisation

- `src/morocco_elections/` : package, domaines, qualité, stockage, exports et compatibilité V9.
- `data/` : données locales ignorées par Git ; voir son README pour le contrat des zones.
- `docs/v9/ontology/` : les 15 documents UTF-8 de l’ontologie V9.
- `docs/v10/ontology/` : les 15 documents UTF-8 de l’ontologie V10.
- `docs/architecture/` : règles de dépendance et flux futurs.
- `metadata/` : provenance physique des sources et backlog GitHub.
- `database/` et `infrastructure/postgres/` : contrats réservés à V13.
- `tests/unit/`, `tests/integration/` et `tests/fixtures/synthetic/` : stratégie de test.

V10 contient 67 onglets. Elle conserve 32 513 mandats locaux et produit 32 512 identités locales Unicode prudentes, avec 44 groupes ambigus audités. Les cinq variantes géographiques sont validées et les deux écarts de sièges sont expliqués comme vacances datées, sans imputation d’élu.

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
python -m morocco_elections validate --mode full --release v10 --baseline v9
python -m morocco_elections github publish-backlog
```

Le mode `ci` fonctionne sans données. Le mode `full` vérifie les empreintes, volumes, documents, 67 onglets V10 et différences autorisées par rapport à V9 sans écrire de fichier.

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

La branche `main` reçoit les changements par pull request après réussite de la CI. Utiliser `feat/...` ou `fix/...` pour les fonctions métier et `chore/...` pour l’infrastructure.

Le backlog hors ligne définit sept chantiers et quatre jalons dans `metadata/github_backlog.json`. Sa publication restera différée jusqu’à la création d’un dépôt GitHub distant.
