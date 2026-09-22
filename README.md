# Morocco Electoral Data Warehouse

Un warehouse électoral marocain reproductible, publié comme un DuckDB accompagné d'un manifeste cryptographique compact. Le projet possède un modèle, une pipeline, une CLI et un validateur canoniques. Les anciennes publications restent des snapshots immuables de provenance; elles ne sont plus des applications à choisir ou maintenir.

## Contenu

Le DuckDB couvre les élections et scrutins publiés, la mobilisation, les résultats généraux et communaux, les territoires, les partis, les personnes et mandats publics, l'activité parlementaire, les indicateurs et les preuves de publication. La décision détaillée par domaine — grain, période, source, couverture, limite, licence et statut — est dans [docs/PRODUCT_SCOPE.md](docs/PRODUCT_SCOPE.md).

Repères du snapshot de développement actuel : 9 élections, 3 715 scrutins, 10 883 résultats électoraux, 22 054 résultats communaux, 1 825 territoires, 1 654 mandats, 65 748 questions parlementaires et 30 257 réponses. Ces nombres décrivent le périmètre publié, pas nécessairement l'univers officiel complet.

## Installer

Python 3.11 est requis.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps --editable .
```

Les données RAW et les sorties sont hors Git. Le build réutilise les octets locaux vérifiés ou télécharge uniquement les sources déjà déclarées, avec taille et SHA-256 épinglés. Une divergence interrompt la construction.

Un cache de contenu facultatif peut être indiqué par `MOROCCO_ELECTIONS_SOURCE_CACHE`. Chaque fichier du cache porte comme nom son SHA-256; il n'est utilisé qu'après validation de sa taille et de son empreinte. Ce cache accélère les reconstructions et rend les serveurs officiels intermittents non bloquants sans assouplir l'intégrité.

## Construire, valider et publier

```powershell
morocco-elections build
morocco-elections validate
morocco-elections audit --summary
morocco-elections package
morocco-elections status
```

`build` produit par défaut `data/exports/open/warehouse/`, dont `morocco_elections.duckdb`, `package-manifest.json`, `table-catalog.json` et `evidence-bundle.json`. Le bundle est un index de preuve : il contient chemins, tailles, SHA-256, empreintes logiques de tables, références de sources et revues synthétiques, jamais une seconde copie des faits.

Les cinq commandes acceptent `--help`. Les destinations de build et d'archive sont configurables; aucun chemin utilisateur absolu n'est codé dans le produit.

## Interroger DuckDB

```powershell
python -c "import duckdb; c=duckdb.connect('data/exports/open/warehouse/morocco_elections.duckdb', read_only=True); print(c.sql('SELECT election_id, count(*) AS contests FROM dim_electoral_contest GROUP BY election_id ORDER BY election_id'))"
```

La table `sources` décrit la provenance. `coverage_universe`, `coverage_universe_member` et `release_coverage_matrix` distinguent couverture observée et complétude officielle. `fact_result_reconciliation` conserve les contrôles calculables et les raisons structurées de non-calculabilité.

## Limites connues

- aucun statut final de résultat n'est inféré sans historique officiel structuré;
- les candidatures, allocations de sièges, lignées partisanes et certaines géographies historiques restent bloquées faute de sources suffisamment reliées;
- la couverture des questions parlementaires est inconnue sans dénominateur officiel;
- les RAW dont la licence de redistribution n'est pas établie sont vérifiés localement mais exclus du paquet;
- une absence reste `NULL`, manquante ou non calculable; elle n'est jamais transformée en zéro.

Les priorités factuelles sont dans [docs/ROADMAP.md](docs/ROADMAP.md). La politique des contrôles est dans [docs/GATE_POLICY.md](docs/GATE_POLICY.md).

## Sources, licences et archives

Le registre canonique est `metadata/warehouse/official_source_registry.json`. Il fixe autorité, URL, date d'acquisition, taille, SHA-256, statut de vérification, licence et décision de redistribution. Le code est sous MIT; la documentation sous CC BY 4.0; les droits des données restent source par source selon [LICENSES/DATA.md](LICENSES/DATA.md) et [ATTRIBUTIONS.md](ATTRIBUTIONS.md).

Les documents des développements antérieurs sont sous `docs/archive/`. Le manifeste `metadata/warehouse/v15_immutable_checksums.json` protège le snapshot historique utilisé comme seed. Ces archives servent à la provenance et à la non-régression, pas au parcours normal.

## Développer

```powershell
python -m compileall -q src
ruff check .
pytest
```

La CI unique reproduit le paquet depuis un checkout propre, valide les checksums et empreintes, exécute les mutations critiques et refuse toute dérive de fichiers générés ou non suivis.
