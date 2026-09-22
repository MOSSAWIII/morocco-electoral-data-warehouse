# V16 — rapprochement BO 6374, Tafra et élus communaux 2015

## Statut

Ce rapprochement porte uniquement sur les 713 lignes candidates déjà transcrites des pages imprimées 6105 à 6118 du BO 6374. Il ne transforme ni ces transcriptions, ni Tafra, en univers juridique officiel.

Résultat reproductible actuel :

- 709 identités Tafra rapprochées, dont 603 par nom arabe exact et 106 par variante unique dans la même province ou préfecture ;
- 701 écarts `Tafra = BO + 4` expliqués par les quatre sièges additionnels féminins institués pour 2015 par l'article 128 bis de la loi organique 59-11, ajouté par la loi organique 34-15 ;
- 1 ligne où les trois effectifs sont égaux (`MATCH`) ;
- 7 conflits d'effectifs conservés comme `AMBIGUOUS` ;
- 4 conseils de grandes villes conservés comme `UNMATCHED`, car le BO décrit le conseil communal tandis que Tafra décrit les arrondissements.

Les sept conflits visibles sont :

| Province/préfecture | Commune Tafra | BO | `nSieges` Tafra | Élus observés | Écart |
|---|---:|---:|---:|---:|---:|
| Nador | Bni Sidel Louta | 11 | 14 | 14 | +3 |
| Driouch | Azlaf | 11 | 14 | 14 | +3 |
| Taounate | Bni Snous | 13 | 16 | 16 | +3 |
| Taounate | Ouartzagh | 15 | 17 | 17 | +2 |
| Khémisset | Oulmes | 23 | 25 | 25 | +2 |
| Azilal | Ait Oumdis | 23 | 26 | 26 | +3 |
| Azilal | Ait Tamlil | 23 | 26 | 26 | +3 |

Les quatre divergences de grain sont Tanger, Fès, Rabat et Salé. Aucune n'est forcée vers un arrondissement particulier.

## Méthode et preuves

Le classeur HCP RGPH 2014 sert de pont bilingue : ses 1 538 codes, noms arabes et noms latins rejoignent exactement les 1 538 lignes Tafra par province/préfecture et commune normalisées. Dans chaque province, les lignes BO sont ensuite affectées une seule fois : égalité arabe d'abord, puis variante de nom unique avec seuil et marge explicites. L'identifiant Tafra relie directement le classeur de résultats au classeur des élus ; les 31 482 élus observés reproduisent `nSieges` pour les 1 538 identifiants.

Chaque source est contrôlée par taille et SHA-256. L'artefact conserve les identifiants de source et le validateur le recalcule intégralement ; toute mutation d'identifiant Tafra, d'effectif ou de source provoque un échec.

Construction et validation :

```powershell
python tools/reconcile_v16_bo6374_tafra.py
python tools/validate_v16.py
```

Artefacts générés :

- `data/exports/open/v16-development/bo6374_tafra_2015_reconciliation.json`
- `data/exports/open/v16-development/bo6374_tafra_2015_reconciliation_report.json`

La distribution complète des écarts par type de commune et province/préfecture se trouve dans le rapport JSON. Les sept conflits et quatre divergences de grain restent des anomalies ciblées ; aucune lecture des pages 6119 à 6136 n'est requise pour ce périmètre.
