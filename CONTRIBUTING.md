# Contribution

## Flux Git

La protection serveur de `main` n'est pas disponible pour ce dépôt privé avec le plan GitHub actuel. La règle suivante est donc procédurale et obligatoire : aucun commit ni push direct sur `main`.

1. Partir de `main` à jour et vérifier son alignement avec `origin/main`.
2. Créer une branche `chore/<sujet>`, `research/<sujet>`, `feat/<sujet>` ou `fix/<sujet>`.
3. Limiter chaque pull request à un changement cohérent.
4. Exécuter `python -m ruff check .`, `python -m pytest` et `python -m morocco_elections validate --mode ci`.
5. Exécuter aussi `python -m morocco_elections validate --mode full --release v13 --baseline v12` pour toute modification touchant le modèle, les sources, les volumes ou la documentation courante.
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
- `v10.0.0` : identités locales, crosswalks et intégrité des sièges.
- `v11.0.0` : ingestion minimale des deux indicateurs HCP validés.
- `v12.0.0` : questions parlementaires écrites qualifiées.
- `v13.0.0` : cœur électoral multi-scrutins et identités historiques.
- V13 est la seule release opérationnelle; V9 à V12 restent reproductibles et immuables.
- PostgreSQL reste différé jusqu'à la démonstration d'un besoin concret.

## Proportionnalité

- Ne pas créer de release pour une qualification ou un résultat `NO_GO`.
- Ne pas développer de qualificateur complet sans source candidate crédible.
- Ne pas rouvrir un chantier bloqué sans preuve nouvelle.
- Préférer une règle locale claire à une abstraction sans usages répétés.
- Limiter une pull request à une amélioration directement reliée au produit final.
