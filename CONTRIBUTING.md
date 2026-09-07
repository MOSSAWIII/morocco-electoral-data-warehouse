# Contribution

## Flux Git

1. Partir de `main` à jour.
2. Créer une branche `feat/<sujet>` ou `fix/<sujet>`.
3. Limiter chaque pull request à un changement cohérent.
4. Exécuter `python tools/validate_project.py --mode ci` et les tests.
5. Exécuter aussi `--mode full` pour toute modification touchant le modèle, les sources, les volumes ou la documentation V9.
6. Fusionner uniquement après réussite de la CI et revue de la provenance.

## Données et traçabilité

- Ne jamais committer de RAW, classeur Excel, Parquet, archive, Shapefile, export de base ou secret.
- Ne jamais modifier un RAW. Une correction se fait dans une couche normalisée et conserve la valeur source.
- Toute nouvelle source doit être inscrite dans `metadata/source_manifest.json` avec URL, producteur, licence, version, grain, dimensions et SHA-256.
- Toute transformation doit avoir une clé, un grain, une règle de nullité et un statut qualité explicites.
- Toute résolution manuelle doit conserver la décision, la preuve, l'auteur et la date.

## Versions

- `v9.0.0` : baseline GitHub du warehouse V9.
- `V10` : identités locales et intégrité.
- `V11` : pouvoir local, SMIIG, résultats 2015 et indicateurs HCP.
- `V12` : questions et trajectoires parlementaires.
- `V13` : PostgreSQL canonique et Excel comme export.

