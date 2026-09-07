## Objet

Décrire le changement et le grain de données concerné.

## Issue et type de branche

- Issue liée :
- [ ] La branche utilise `chore/`, `research/`, `feat/` ou `fix/`.
- [ ] Aucun commit ni push direct n'a été effectué sur `main`.

## Provenance et qualité

- [ ] Aucun RAW, classeur, export, secret ou fichier binaire n'est ajouté.
- [ ] Les nouvelles sources ou versions sont inscrites dans le manifeste.
- [ ] Les RAW existants restent inchangés.
- [ ] Les statuts `OBSERVÉ`, `DÉRIVÉ`, `STRUCTURE VIDE`, `PILOTE` et `BLOQUÉ` sont respectés.
- [ ] Les clés, cardinalités, règles de nullité et limitations sont documentées.

## Validation

- [ ] `python tools/validate_project.py --mode ci`
- [ ] `pytest`
- [ ] `python tools/validate_project.py --mode full` si le modèle, les données ou la documentation changent.
- [ ] La CI distante est réussie avant fusion par squash.
