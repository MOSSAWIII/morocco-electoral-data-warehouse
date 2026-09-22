# Preuve de reconstruction propre

La révision `e9259d59aab18ed90aa5307e6bc58053ef7465e4` a été reconstruite le 22 septembre 2026 depuis deux clones Git propres, distincts et sans fichier généré préalable. Les deux exécutions ont utilisé le même cache externe adressé par SHA-256. Ce cache ne constitue pas une sortie réutilisée : chaque objet est accepté seulement après vérification de sa taille et de son empreinte déclarées.

## Protocole

Chaque clone a exécuté séparément :

```powershell
$env:MOROCCO_ELECTIONS_SOURCE_CACHE = '<cache-externe>'
python -m morocco_elections build --output '<sortie-vide>'
python -m morocco_elections validate --package '<sortie>'
python -m morocco_elections audit --package '<sortie>' --summary
```

Les deux clones étaient propres avant et après la construction. Chacun a acquis 40 des 42 entrées déclarées; les deux autres sont explicitement `metadata_only`. Chaque paquet contient 45 tables et 9 fichiers. Les deux validations retournent `PASS`, sans fichier non géré, entrée manquante, divergence de taille ou divergence de SHA-256 interne au paquet.

## Résultat comparatif

Le fichier `table-catalog.json` est strictement identique dans les deux sorties : SHA-256 `3a3510e4fe973ce301b38750de7291ecb5b0c83bf7025d73d10be7822f389e0e`. Il prouve l'égalité, pour les 45 tables, du schéma ordonné, du nombre de lignes et de l'empreinte logique. Les cinq autres sorties déterministes comparées sont également identiques :

| Fichier | SHA-256 |
|---|---|
| `data-contract.json` | `e86e3037db7ee5e989a606758d96fec4b749753175747f41080da83b764b3e74` |
| `geo-parent-report.json` | `f2644edc4ea7f0ad7698f504a693ce976fdcc4f0733f9717e25f36d1a6de43a5` |
| `reconciliation-report.json` | `f7a10f11f946a68a7f9b01c2030cdb874d4f82cf8291c9feeebde5d5f678437e` |
| `result-history-report.json` | `14fb6181dde543333dc51261708c6f19ed027e09ac03887a33d2be63b8cdc5bb` |
| `v15-immutable-checksums.json` | `f5558c09cdb4257b62e760563c0ac57d1d670f74ade798bd0a6f1ad14b17fec9` |

Les fichiers physiques DuckDB ne sont pas comparés octet pour octet. DuckDB peut produire des organisations physiques et tailles différentes pour un même contenu logique. Par conséquent, les manifestes et index de preuve qui scellent ces octets physiques diffèrent aussi entre les exécutions. Chacun reste valide pour son propre paquet. La reproductibilité exigée porte sur le contenu matérialisé : les 45 empreintes logiques, les nombres de lignes, les schémas, le contrat et les rapports sont identiques.

La CI applique désormais le même contrôle en construisant deux paquets, en validant les deux et en comparant octet pour octet le catalogue logique et les sorties déterministes.
