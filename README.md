# Morocco Electoral Data Warehouse

V15 est le socle public reproductible du warehouse électoral marocain. Une seule pipeline canonique produit un paquet autonome en CSV, Parquet et DuckDB; V9 à V14.1 restent des releases historiques immuables et reproductibles séparément.

## Démarrage

Python 3.11 est requis.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install --no-deps --editable .

python -m morocco_elections bootstrap
python -m morocco_elections validate --mode public
python -m morocco_elections analyze reference
```

`bootstrap` valide d’abord tout paquet V15 déjà présent. Sinon, il vérifie la taille et le SHA-256 de l’archive locale ou de l’asset public configuré dans `metadata/v15_publication.json`, extrait dans un staging protégé puis remplace atomiquement l’installation. `--network-only` prouve le parcours externe; une URL miroir du même asset peut être fournie avec `MOROCCO_ELECTIONS_V15_URL`.

## Construire V15

Une seule commande exécute le pipeline V15 :

```powershell
python -m morocco_elections build v15
```

L’entrée publique par défaut est `data/exports/open/v14.1/`; si elle est absente, le pipeline télécharge la distribution officielle V14.1 dont la taille, le SHA-256 et le manifeste sont épinglés. Elle peut être remplacée avec `--seed-dir`, mais le même contrat d’intégrité s’applique. La sortie est `data/exports/open/v15/` et l’archive téléchargeable est créée sous `data/exports/open/releases/`. Le code V15 n’importe aucun générateur V9–V14.1.

Les trois usages sont distingués explicitement :

- utilisation du paquet V15 : autonome, sans Excel ni chemin privé ;
- reconstruction publique : depuis un paquet public V14.1 vérifié ;
- reconstruction historique complète : certaines sources locales non redistribuables restent nécessaires.

## Modèle public

Le parcours initial utilise huit tables CORE :

1. `dim_geo`
2. `dim_party`
3. `dim_election`
4. `dim_electoral_contest`
5. `fact_election_result`
6. `fact_electoral_mobilization`
7. `fact_mandate`
8. `fact_observation`

Toutes les autres tables sont classées `SPECIALIZED`, `BRIDGE`, `METADATA` ou `ANALYTICAL`. Le [contrat V15](metadata/v15_contract.json) versionne les 31 tables, colonnes, types, nullités, rôles, unités, domaines, clés, relations, contraintes et corrections. Le DDL, le manifeste, le dictionnaire et les validateurs en dérivent.

Les cinq analyses de référence utilisent des cubes réellement disponibles : évolution territoriale des partis; fragmentation/HHI/compétitivité; résultats versus contrôle communal; mandats et représentation territoriale; questions parlementaires publiées. Les [requêtes SQL V15](examples/v15_reference_queries.sql) sont également embarquées dans le paquet.

Le paquet expose aussi `coverage_matrix.json` : inscrits publiés par élection, gouvernance communale résolue/non résolue, états de preuve des affiliations, précision des dates partielles et numérateur/dénominateur/statut de chaque analyse. La couverture parlementaire reste `UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR`. Les ambiguïtés d’identité ou de temporalité restent `NULL` ou `UNRESOLVED`; aucun classement de personnes n’est produit.

## Qualité et développement

```powershell
python -m morocco_elections validate --mode public
python -m morocco_elections validate --mode ci
python -m ruff check .
python -m pytest
```

La validation publique contrôle les SHA-256, les empreintes logiques typées et triées des 31 tables dans CSV/Parquet/DuckDB, les en-têtes CSV, schémas et nullabilités Parquet, le schéma DuckDB, les grains, clés étrangères, domaines, intervalles, corrections, couverture et réconciliations des cinq cubes. Les tests de mutation altèrent le vrai DDL et le vrai paquet pour prouver ces rejets.

Principes : les RAW restent immuables et hors Git; une absence n’est jamais imputée à zéro; les découpages et affiliations restent datés; aucune donnée sensible, RAW ou secrète n’est suivie.

## Licences et historique

- code : MIT (`LICENSE`) ;
- documentation : CC BY 4.0 (`LICENSES/DOCUMENTATION.md`) ;
- base composite et données : `LICENSES/DATA.md` et `ATTRIBUTIONS.md`.

Les commandes historiques `build`, `export`, `docs`, `qualify`, `quality`, `identity` et `github` restent disponibles pour reproduire V9–V14.1. Leur mémoire scientifique est conservée sous `docs/` et `metadata/`; elles ne font pas partie du parcours V15.
