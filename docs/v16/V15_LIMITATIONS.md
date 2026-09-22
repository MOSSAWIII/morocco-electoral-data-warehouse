# V15.0.0 — immuabilité et limites connues

V15.0.0 est une release publiée et immuable. Ses fichiers suivis sont épinglés par SHA-256 dans `metadata/v16/v15_immutable_checksums.json`. Toute correction doit être publiée sous une nouvelle version documentée; il est interdit de remplacer silencieusement un artefact V15 ou de réutiliser le numéro `15.0.0`.

Limites connues à ne pas corriger rétroactivement dans V15 :

- la couverture mesure principalement le corpus acquis et ne représente pas toujours un univers électoral officiel externe;
- certaines périodes parlementaires n’ont pas de dénominateur officiel et portent donc un statut d’inconnu;
- les versions provisoires, définitives, rectifiées et annulées des résultats ne sont pas toutes historisées séparément;
- les régimes juridiques, candidatures, règles d’attribution et décisions contentieuses ne sont pas entièrement structurés;
- les lignées historiques des partis et des géographies ne suffisent pas à toutes les comparaisons longitudinales;
- certains agrégats analytiques requièrent des pondérations et préconditions scientifiques plus explicites;
- la présence d’une donnée dans V15 ne prouve ni une exhaustivité nationale ni son applicabilité à une autre date.
- les 82 concours où une somme chargée de voix peut être comparée à un total de suffrages valides ne disposent pas pour autant d'un univers officiel des partis attendus; cette comparaison est exploratoire, pas une réconciliation PASS. Le rapprochement V16 les classe `NOT_COMPUTABLE` jusqu'à preuve de l'exhaustivité du détail.

V16 traite ces limites de façon additive. Ce document constitue une divulgation, pas une modification des données V15.
