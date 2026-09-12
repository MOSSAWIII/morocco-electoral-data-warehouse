# Morocco Electoral Data Warehouse

Warehouse électoral marocain ouvert, traçable et directement exploitable. **V14.1 est la release publique courante.** Elle corrige la validité analytique de la série parlementaire V14 sans ajouter ni modifier de donnée source; les releases antérieures restent un historique reproductible.

V14.1 relie un modèle canonique de territoires, élections, partis, personnes, mandats, gouvernance locale, activité parlementaire et observations socio-économiques. Elle conserve le cœur multi-scrutins V13 et expose 65 748 questions écrites ou orales publiées entre 2017 et 2024, dont 30 257 possèdent une date de réponse publiée. Ces nombres décrivent le corpus disponible, pas l'activité exhaustive du Parlement ni un taux réel de réponse gouvernementale.

## Utilisation courante

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install --no-deps --editable .

python -m morocco_elections build v13
python -m morocco_elections export v14.1
python -m morocco_elections analyze v13
python -m morocco_elections validate --mode ci
python -m morocco_elections validate --mode full --release v14.1 --baseline v14
```

Les cinq familles de commandes actives sont `build`, `export`, `analyze`, `validate` et `sources`. Leur aide est disponible avec `python -m morocco_elections <commande> --help`.

- `build v13` reconstruit le dernier classeur Excel, utilisé comme socle stable de l'export ouvert.
- `export v14.1` produit le modèle courant non nominatif en CSV, Parquet et DuckDB sous `data/exports/open/v14.1/`.
- `analyze v13` exécute les analyses de référence sans écrire dans le warehouse.
- `validate --mode ci` contrôle rapidement le dépôt et les contrats actifs sans données locales.
- `validate --mode full` vérifie aussi les fichiers locaux, leurs empreintes, les volumes, les relations et la comparaison V13/V12.
- `sources` catalogue, acquiert et profile les sources sans autoriser automatiquement leur ingestion.

La racine des données est `<repo>/data` par défaut. L’argument `--data-dir` est prioritaire sur la variable `ELECTIONS_DATA_DIR`.

## Point d’entrée documentaire

Commencer par [le README du paquet V14.1](docs/publication/V14_1_OPEN_DATA_README.txt), puis consulter [l’ontologie du socle V13](docs/v13/ontology/00_INDEX_ET_MODE_EMPLOI.txt). Le contrat machine-readable commun se trouve dans [`metadata/ontology_v1.json`](metadata/ontology_v1.json).

Trois requêtes DuckDB parlementaires reproductibles sont fournies dans [`examples/v14_1_reference_queries.sql`](examples/v14_1_reference_queries.sql). Les notes de validité sont dans [`docs/publication/V14_1_RELEASE_NOTES.md`](docs/publication/V14_1_RELEASE_NOTES.md).

## Licences

- code : MIT, voir [`LICENSE`](LICENSE) ;
- documentation originale : CC BY 4.0, voir [`LICENSES/DOCUMENTATION.md`](LICENSES/DOCUMENTATION.md) ;
- base composite et données : politique ODbL/source par source, voir [`LICENSES/DATA.md`](LICENSES/DATA.md) et [`ATTRIBUTIONS.md`](ATTRIBUTIONS.md).

La licence du projet ne remplace pas celle des producteurs. Toute réutilisation doit conserver les identifiants de source et leurs attributions.

Principes non négociables :

- les RAW sont immuables et restent hors de Git ;
- une absence reste `NULL`, jamais un zéro reconstruit ;
- les identifiants source sont conservés avec leur correspondance canonique ;
- les découpages historiques restent datés ;
- `OBSERVÉ`, `DÉRIVÉ`, `STRUCTURE VIDE`, `PILOTE` et `BLOQUÉ` ne sont jamais confondus ;
- les formats Excel, CSV, Parquet et DuckDB exposent un seul modèle logique.

## État du projet

### Roadmap active

1. Éprouver V14.1 et améliorer les identités parlementaires uniquement avec des preuves déterministes.
2. Historiser ensuite les affiliations et groupes lorsqu'une source datée permet les dénominateurs de groupe.
3. Construire les couches dérivées thèmes, institutions et géographies, séparées des textes source.
4. Intégrer les engagements ministériels acquis, puis reprendre une seule vague HCP à la fois.

La roadmap détaillée est dans [`docs/ROADMAP.md`](docs/ROADMAP.md).

### Watchlist bloquée

Ces sujets ne consomment plus de développement sans preuve nouvelle : inscrits communaux 2015–2021, 135 présidences non résolues, conseils communaux 2015, SMIIG et les 25 couples HCP restés `NO_GO`.

### Historique terminé

V9 à V13, leurs documents, leurs rapports de release et les décisions de qualification restent immuables. Les anciennes commandes `docs`, `qualify`, `quality`, `identity` et `github` sont conservées pour les reproduire, mais ne font pas partie du parcours courant. Leur index se trouve dans [`docs/research/README.md`](docs/research/README.md).

Les wrappers historiques V9 restent disponibles :

```powershell
python build_v9.py
python generate_v9_documentation.py
```

## Organisation

- `src/morocco_elections/` : construction du socle V13, exports V14/V14.1, analyses, sources et compatibilité historique ;
- `data/` : RAW et exports locaux ignorés par Git ;
- `docs/publication/` : documentation des paquets publics courants ;
- `docs/v13/ontology/` : ontologie détaillée du socle Excel canonique ;
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
