# Revues externes de publication

Le build ne crée aucune décision de licence, de confidentialité ou de classe
d'affirmation. Une personne indépendante examine le contenu candidat, puis
inscrit sa décision dans `metadata/warehouse/publication_reviews.json`. Tant que
ces décisions manquent ou ne correspondent pas exactement au contenu inspecté,
les gates de publication restent en échec.

## Contenu à examiner

Construire d'abord un paquet candidat, puis lire `package-manifest.json`. Pour
chaque fichier, la revue référence `review_sha256`, et non nécessairement le
SHA-256 physique `sha256` :

- `review_scope = ENTIRE_FILE` signifie que les deux empreintes sont identiques;
- pour le DuckDB, le scope logique exclut seulement les trois tables de preuve
  auto-référentielles `publication_file`, `publication_review` et
  `publication_gate_result`;
- pour `table-catalog.json`, le même scope exclut seulement les entrées de ces
  trois tables. Les schémas, lignes et vues substantiels restent couverts.

Le validateur recalcule chaque `review_sha256`. Une valeur choisie arbitrairement,
une modification du contenu substantiel ou une revue liée à une ancienne
empreinte échoue donc fermement. Cette séparation permet en revanche au build de
matérialiser la décision externe dans DuckDB sans invalider la décision par son
propre ajout.

## Champs requis

Chaque tableau du registre contient exactement une décision par fichier candidat
et par type de revue. Les trois types partagent :

- `relative_path` et `file_sha256`, ce dernier égal au `review_sha256` manifesté;
- `reviewed_by`, auteur humain ou organisme responsable;
- `reviewed_at`, date ISO de la décision (elle peut être postérieure à la date
  d'observation des données `as_of_date`);
- `evidence_id`, référence stable du dossier ou procès-verbal examiné.

La revue de licence ajoute `decision = REDISTRIBUTABLE`, `legal_basis`,
`evidence_url` et `proof_sha256`. La revue de confidentialité ajoute
`decision = PASS` et `review_method`. La revue de classe d'affirmation ajoute
`claim_class`, `review_method`, `uncertainty_applicable` et, lorsque cette
dernière valeur est vraie, `uncertainty_disclosure`.

Le contributeur ne doit ni copier automatiquement les déclarations du manifeste
dans ce registre, ni se désigner comme revue indépendante du contenu qu'il vient
de produire. Après réception des décisions, reconstruire le paquet et exécuter :

```bash
morocco-elections validate
morocco-elections audit --summary --require-ready
```

Une reconstruction qui change un contenu examiné ignore la décision devenue
obsolète et maintient les gates fermés.
