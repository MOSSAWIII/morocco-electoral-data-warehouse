# Morocco Electoral Data Warehouse

Warehouse électoral marocain ouvert, traçable et directement exploitable. **V13 est la seule release opérationnelle.** Les releases V9 à V12 sont conservées comme historique reproductible et ne constituent plus le parcours normal.

V13 relie un modèle canonique de territoires, élections, partis, personnes, mandats, gouvernance locale, activité parlementaire et observations socio-économiques. Son nouveau cœur multi-scrutins contient 639 courses électorales, 10 883 résultats `course × parti` et 639 observations de mobilisation pour les législatives 2007–2021 et les régionales 2015–2021.

## Utilisation courante

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install --no-deps --editable .

python -m morocco_elections build v13
python -m morocco_elections export v13
python -m morocco_elections analyze v13
python -m morocco_elections validate --mode ci
python -m morocco_elections validate --mode full --release v13 --baseline v12
```

Les cinq familles de commandes actives sont `build`, `export`, `analyze`, `validate` et `sources`. Leur aide est disponible avec `python -m morocco_elections <commande> --help`.

- `build v13` reconstruit le classeur canonique depuis les RAW, les décisions versionnées et le bootstrap historique nécessaire.
- `export v13` produit le même noyau non nominatif en CSV, Parquet et DuckDB sous `data/exports/open/v13/`.
- `analyze v13` exécute les analyses de référence sans écrire dans le warehouse.
- `validate --mode ci` contrôle rapidement le dépôt et les contrats actifs sans données locales.
- `validate --mode full` vérifie aussi les fichiers locaux, leurs empreintes, les volumes, les relations et la comparaison V13/V12.
- `sources` catalogue, acquiert et profile les sources sans autoriser automatiquement leur ingestion.

La racine des données est `<repo>/data` par défaut. L’argument `--data-dir` est prioritaire sur la variable `ELECTIONS_DATA_DIR`.

## Point d’entrée documentaire

Commencer par [le mode d’emploi V13](docs/v13/ontology/00_INDEX_ET_MODE_EMPLOI.txt). Le [README du paquet ouvert](docs/publication/V13_OPEN_DATA_README.txt) explique l’accès CSV, Parquet et DuckDB. Le contrat machine-readable se trouve dans [`metadata/ontology_v1.json`](metadata/ontology_v1.json).

Principes non négociables :

- les RAW sont immuables et restent hors de Git ;
- une absence reste `NULL`, jamais un zéro reconstruit ;
- les identifiants source sont conservés avec leur correspondance canonique ;
- les découpages historiques restent datés ;
- `OBSERVÉ`, `DÉRIVÉ`, `STRUCTURE VIDE`, `PILOTE` et `BLOQUÉ` ne sont jamais confondus ;
- les formats Excel, CSV, Parquet et DuckDB exposent un seul modèle logique.

## État du projet

### Roadmap active

1. Publier le paquet V13 après décision explicite sur les licences et la visibilité du dépôt.
2. Ajouter une seule vague de données à la fois lorsqu’une source crédible, accessible et raccordable est identifiée.
3. Étendre ensuite le canonique selon la valeur analytique démontrée : gouvernance, territoire/HCP, puis Parlement.
4. Préparer PostgreSQL uniquement si collaboration, performance, API ou mises à jour fréquentes le justifient.

La roadmap détaillée est dans [`docs/ROADMAP.md`](docs/ROADMAP.md).

### Watchlist bloquée

Ces sujets ne consomment plus de développement sans preuve nouvelle : inscrits communaux 2015–2021, 135 présidences non résolues, conseils communaux 2015, SMIIG et les 25 couples HCP restés `NO_GO`.

### Historique terminé

V9, V10, V11 et V12, leurs 15 documents respectifs, leurs rapports de release et les décisions de qualification restent immuables. Les anciennes commandes `docs`, `qualify`, `quality`, `identity` et `github` sont conservées pour les reproduire, mais ne font pas partie du parcours courant. Leur index se trouve dans [`docs/research/README.md`](docs/research/README.md).

Les wrappers historiques V9 restent disponibles :

```powershell
python build_v9.py
python generate_v9_documentation.py
```

## Organisation

- `src/morocco_elections/` : construction V13, export, analyses, sources et compatibilité historique ;
- `data/` : RAW et exports locaux ignorés par Git ;
- `docs/v13/ontology/` : documentation opérationnelle courante ;
- `docs/v9/` à `docs/v12/` et `docs/research/` : mémoire scientifique reproductible ;
- `metadata/` : contrats actifs, provenance et décisions historiques ;
- `tests/` : invariants métier, contrats et intégration CLI.

## Développement

Les changements passent par une branche et une pull request. Installer les outils de développement avec :

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps --editable .
python -m ruff check .
python -m pytest
```

Utiliser `research/...`, `feat/...`, `fix/...` ou `chore/...`. Aucun RAW, classeur, export, secret ou nom de personne ne doit être ajouté à Git.
