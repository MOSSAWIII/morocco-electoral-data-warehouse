# Contribution

## Flux Git

La protection serveur de `main` n'est pas disponible pour ce dépôt privé avec le plan GitHub actuel. La règle suivante est donc procédurale et obligatoire : aucun commit ni push direct sur `main`.

1. Partir de `main` à jour et vérifier son alignement avec `origin/main`.
2. Créer une branche `chore/<sujet>`, `research/<sujet>`, `feat/<sujet>` ou `fix/<sujet>`.
3. Limiter chaque pull request à un changement cohérent.
4. Exécuter `python -m morocco_elections validate --mode ci` et les tests.
5. Exécuter aussi `--mode full` pour toute modification touchant le modèle, les sources, les volumes ou la documentation V9.
6. Pousser uniquement la branche de travail et ouvrir une pull request vers `main`.
7. Fusionner par squash uniquement après réussite de la CI et revue de la provenance, puis supprimer la branche distante.

Même le propriétaire du dépôt suit ce flux. Une urgence ne justifie pas de contourner la CI; elle utilise une PR `fix/...` minimale.

## Données et traçabilité

- Ne jamais committer de RAW, classeur Excel, Parquet, archive, Shapefile, export de base ou secret.
- Ne jamais modifier un RAW. Une correction se fait dans une couche normalisée et conserve la valeur source.
- Toute nouvelle source doit être inscrite dans `metadata/source_manifest.json` avec URL, producteur, licence, version, grain, dimensions, chemin relatif et SHA-256.
- Toute transformation doit avoir une clé, un grain, une règle de nullité et un statut qualité explicites.
- Toute résolution manuelle doit conserver la décision, la preuve, l'auteur et la date.

## Versions

- `v9.0.0` : baseline GitHub du warehouse V9.
- `V10` : identités locales et intégrité.
- `V11` : pouvoir local, SMIIG, résultats 2015 et indicateurs HCP.
- `V12` : questions et trajectoires parlementaires.
- `V13` : PostgreSQL canonique et Excel comme export.
