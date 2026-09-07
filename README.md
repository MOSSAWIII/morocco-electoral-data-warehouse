# Morocco Electoral Data Warehouse

Warehouse quantitatif consacré aux élections, à la représentation et à la gouvernance territoriale au Maroc. La baseline documentaire et analytique actuelle est la V9.

## Principes

- Les fichiers RAW sont immuables et restent hors de Git.
- PostgreSQL deviendra la couche canonique ; Excel restera un produit d'export.
- Toute donnée est qualifiée par un statut explicite :
  - `OBSERVÉ` : valeur présente dans une source identifiée ;
  - `DÉRIVÉ` : valeur calculée, avec formule et dénominateur documentés ;
  - `STRUCTURE VIDE` : schéma prévu sans donnée disponible ;
  - `PILOTE` : ancien échantillon conservé à titre exploratoire ;
  - `BLOQUÉ` : limite ouverte et enregistrée en QA.
- Une valeur absente n'est jamais reconstruite sans source, et une métrique dérivée n'est jamais présentée comme officielle.

## Baseline V9

La V9 contient 64 onglets et organise notamment deux cubes centraux :

- `COMMUNE × PARTI × ÉLECTION` ;
- `COMMUNE × ÉLECTION`.

Elle comprend aussi les couches mandats, pouvoir local, socio-économie, provenance, contrôles qualité et panels analytiques. Le corpus de référence se trouve dans `documentation_v9/` et contient exactement 15 documents texte UTF-8.

Les principaux volumes contrôlés sont : 32 513 mandats locaux, 1 654 mandats parlementaires, 3 076 observations commune-élection, 14 555 transitions et 22 054 observations du panel analytique commune-parti-élection.

## Données locales

Les sources doivent être placées sous `raw_sources/` selon les chemins définis dans `metadata/source_manifest.json`. Les classeurs `Morocco_Electoral_Data_Warehouse_V8.xlsx` et `Morocco_Electoral_Data_Warehouse_V9.xlsx` restent également locaux. Tous ces fichiers sont ignorés par Git ; leurs empreintes SHA-256 et leurs dimensions attendues sont versionnées.

Il ne faut jamais forcer l'ajout d'un fichier ignoré avec `git add -f`.

## Installation et validation

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python tools/validate_project.py --mode ci
python tools/validate_project.py --mode full
```

Le mode `ci` fonctionne dans un clone sans données. Le mode `full` exige les sources, V8 et V9, mais ne les modifie pas. La documentation peut être régénérée localement avec :

```powershell
python generate_v9_documentation.py
```

La construction actuelle de V9 reste disponible avec `python build_v9.py`. Cette commande écrit V9 ; elle n'est donc pas exécutée par la validation.

## Développement

La branche `main` reçoit les changements par pull request après réussite de la CI. Utiliser des branches `feat/...` ou `fix/...`. Les conventions et contrôles sont détaillés dans `CONTRIBUTING.md`.

## Feuille de route

Les travaux sont organisés en quatre jalons GitHub : V10 identités et intégrité, V11 pouvoir local et socio-économie, V12 activité parlementaire, puis V13 canonique PostgreSQL. Les sept chantiers sont suivis dans les issues du dépôt.

Tant que le dépôt reste uniquement local, le backlog complet est conservé dans `metadata/github_backlog.json`. Après création et authentification du dépôt distant, sa publication idempotente se fait avec :

```powershell
python tools/publish_github_backlog.py
```
