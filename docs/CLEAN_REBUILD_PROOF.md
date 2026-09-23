# Preuve de reconstruction propre

La reconstruction de référence consignée ici, dont la base Git est la révision
`9005a45b142f4f3ceaccdd379c266f7ef215eefc`, a été exécutée le 23 septembre
2026 vers deux répertoires de sortie absents et distincts. Elle constitue une
preuve historique précise, pas l'identifiant mouvant de l'état de travail
courant. Les deux exécutions ont utilisé les mêmes sources locales adressées par
SHA-256. Chaque objet, y compris le seed historique extrait, a été accepté
seulement après vérification de sa taille et de son empreinte déclarées.

## Protocole

Chaque construction a exécuté séparément :

```powershell
python -m morocco_elections build --output '<sortie-vide>'
python -m morocco_elections validate --package '<sortie>'
python -m morocco_elections audit --package '<sortie>' --summary
```

Chaque construction a réutilisé, après vérification cryptographique, 41 objets acquis distincts du registre ; les 45 entrées restantes sont explicitement documentaires ou internes et ne déclarent aucun contenu acquis. Chaque paquet contient 45 tables, 10 vues analytiques et 8 fichiers. Les validations retournent `integrity_status = PASS` et `publication_status = NOT_PUBLICATION_READY`, sans fichier non géré, entrée manquante, divergence de taille ou divergence de SHA-256 interne. Les 86 identifiants du registre canonique sont matérialisés une fois chacun, toutes les colonnes de provenance `source_id` les référencent, et aucun identifiant actif ne conserve un label de version intermédiaire. Deux univers et 1 550 membres sont matérialisés : l'univers territorial COMM2015 et l'allocation nationale officielle des 395 sièges LEG2021 entre 12 partis.

## Résultat comparatif

Les sorties déterministes suivantes sont strictement identiques entre les deux constructions :

| Fichier | SHA-256 |
|---|---|
| `table-catalog.json` | `d85bd151a65f8d13c242d55d0e5f17f4426512fec2ed6e38d8202d0ad21349a3` |
| `data-contract.json` | `c86ef1b388aa5930b5a41e4b292b1aaeeefead548342b7a28745d52bdcf334c5` |
| `geo-parent-report.json` | `f2644edc4ea7f0ad7698f504a693ce976fdcc4f0733f9717e25f36d1a6de43a5` |
| `reconciliation-report.json` | `d99bd17d742a01755efce2266bbb57ea421dfc30f09ffba184ba1e0fe6c5a378` |
| `result-history-report.json` | `8f60ba62406037c0c49f5bac7571689d1b5bdf9e92ee1818c0d34d9f4f4f02b1` |

Le catalogue prouve l'égalité du schéma ordonné, du nombre de lignes et de l'empreinte logique des 45 tables. Pour les 10 vues, il épingle aussi la définition SQL normalisée, son SHA-256 et les dépendances déclarées.

Le résumé d'audit sépare désormais les 0 relations parentales non résolues des 177 identités communales encore sans correspondance institutionnelle exacte. Il publie également les contrôles calculables et non calculables par élection, ainsi que les 7 élections qui n'ont pas encore d'univers officiel de résultats matérialisé.

Les fichiers physiques DuckDB ne sont pas comparés octet pour octet : leur organisation interne peut différer pour un contenu logique identique. Les manifestes et index qui scellent ces octets physiques diffèrent donc entre les exécutions et restent valides pour leur propre paquet. La reproductibilité exigée porte sur les 55 objets logiques, le contrat et les rapports déterministes.

Le manifeste distingue désormais l'empreinte physique `sha256` de l'empreinte
stable `review_sha256`. Deux constructions indépendantes doivent produire les
mêmes `review_sha256`, `review_byte_size` et `review_scope` pour chaque fichier;
la CI compare explicitement ce vecteur. Les revues externes restent ainsi liées
au même contenu substantiel même lorsque la disposition physique de DuckDB
diffère.

La CI applique ce protocole depuis un checkout propre, compare les sorties ci-dessus et refuse toute dérive suivie ou non suivie.

La même suite, le même lint et les mêmes dépendances ont aussi été exécutés avec succès sous CPython 3.11 et CPython 3.12.11. La matrice CI couvre donc 3.11 et 3.12, conformément à la plage `>=3.11,<3.13` déclarée par le paquet.
