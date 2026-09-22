# V16 — contrat des indicateurs scientifiques

Tous les indicateurs échouent de manière fermée : une précondition manquante produit `NOT_COMPUTED`, une valeur nulle et la liste exacte des préconditions échouées.

| Indicateur | Formule | Dénominateur/périmètre | Préconditions bloquantes |
|---|---|---|---|
| Part régionale pondérée | `SUM(party_votes) / SUM(valid_votes)` | Suffrages valides des communes observées de la région | Grains compatibles; voix valides positives. |
| Moyenne communale non pondérée | `MEAN(party_votes / valid_votes)` | Communes observées, chacune de poids égal | Nom explicite; ne jamais la présenter comme résultat régional. |
| HHI | `SUM(vote_share_i²)` | Distribution complète des voix du périmètre | Parts dans `[0,1]`, somme égale à 1 dans la tolérance, couverture complète. |
| ENEP | `1 / HHI_votes` | Distribution complète des voix | Préconditions HHI; identités partisanes comparables. |
| ENPP | `1 / SUM(seat_share_i²)` | Distribution complète des sièges | Parts de sièges complètes, somme égale à 1, couverture complète. |
| Gallagher | `SQRT(0.5 × SUM((seat_share_i - vote_share_i)²))` | Vecteurs voix/sièges alignés sur le même périmètre | Partis alignés, parts complètes, géographie et scrutin comparables. |
| Volatilité de Pedersen | `0.5 × SUM(ABS(p_i,t - p_i,t-1))` | Deux élections alignées | Frontières identiques/crosswalkées, lignées partisanes revues, couverture complète. |
| Fragmentation | HHI et nombre effectif approprié | Distribution complète pertinente | Même garde-fou que HHI/ENEP/ENPP. |

Chaque sortie contient formule, dénominateur, périmètre, couverture et limites. Ces indicateurs sont descriptifs : aucun n’est un score de fraude et aucun ne justifie seul une conclusion causale.

Le taux parlementaire V16 est le `observed_published_question_rate`: questions trouvées dans le corpus public acquis pour 100 jours de mandat observés. Il ne mesure ni toute l’activité parlementaire ni un univers officiel absent.
