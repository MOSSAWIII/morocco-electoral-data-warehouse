# Contribution

## Flux Git

La protection serveur de `main` n'est pas disponible pour ce dépôt privé avec le plan GitHub actuel. La règle suivante est donc procédurale et obligatoire : aucun commit ni push direct sur `main`.

1. Partir de `main` à jour et vérifier son alignement avec `origin/main`.
2. Créer une branche `chore/<sujet>`, `research/<sujet>`, `feat/<sujet>` ou `fix/<sujet>`.
3. Limiter chaque pull request à un changement cohérent.
4. Exécuter `python -m ruff check .` et `python -m pytest`.
5. Construire puis contrôler le produit avec `python -m morocco_elections build --output <sortie>`, `python -m morocco_elections validate --package <sortie>` et `python -m morocco_elections audit --package <sortie> --summary`.
6. Pousser uniquement la branche de travail et ouvrir une pull request vers `main`.
7. Fusionner par squash uniquement après réussite de la CI et revue de la provenance, puis supprimer la branche distante.

Même le propriétaire du dépôt suit ce flux. Une urgence ne justifie pas de contourner la CI ; elle utilise une PR `fix/...` minimale.

## Données et traçabilité

- Ne jamais committer de RAW, classeur Excel, Parquet, archive, Shapefile, export de base ou secret.
- Ne jamais modifier un RAW. Une correction se fait dans une couche normalisée et conserve la valeur source.
- Toute nouvelle source doit être inscrite dans le registre canonique avec URL, producteur, licence, grain, chemin relatif et SHA-256.
- Toute transformation doit avoir une clé, un grain, une règle de nullité et un statut qualité explicites.
- Toute résolution manuelle doit conserver la décision, la preuve, l'auteur et la date.

## Publication

Le dépôt construit un produit unique. Son identité de développement est `0.0.0.dev0`. La première publication sera `v1.0.0`, uniquement lorsque `audit --require-ready` confirme les douze gates bloquants; l'archive est ensuite créée avec `morocco-elections package --require-ready --output morocco-electoral-data-warehouse-v1.0.0.zip`. Le snapshot utilisé comme seed est un artefact historique de provenance, pas une version active du produit. PostgreSQL reste différé jusqu'à la démonstration d'un besoin concret.

## Proportionnalité

- Ne pas créer de release pour une qualification ou un résultat `NO_GO`.
- Ne pas développer de qualificateur complet sans source candidate crédible.
- Ne pas rouvrir un chantier bloqué sans preuve nouvelle.
- Préférer une règle locale claire à une abstraction sans usages répétés.
- Limiter une pull request à une amélioration directement reliée au produit final.
