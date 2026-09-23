## Objet

Décrire le changement et le grain de données concerné.

## Issue et type de branche

- Issue liée :
- [ ] La branche utilise `chore/`, `research/`, `feat/` ou `fix/`.
- [ ] Aucun commit ni push direct n'a été effectué sur `main`.

## Provenance et qualité

- [ ] Aucun RAW, classeur, export, secret ou fichier binaire n'est ajouté.
- [ ] Les nouvelles sources sont inscrites dans le registre canonique.
- [ ] Les RAW existants restent inchangés.
- [ ] Les clés, cardinalités, règles de nullité et limitations sont documentées.

## Validation

- [ ] `python -m ruff check .`
- [ ] `python -m pytest`
- [ ] `python -m morocco_elections build --output <sortie>`
- [ ] `python -m morocco_elections validate --package <sortie>`
- [ ] `python -m morocco_elections audit --package <sortie> --summary`
- [ ] La CI distante est réussie avant fusion par squash.
