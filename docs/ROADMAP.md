# Roadmap du warehouse électoral

Cette roadmap décrit des capacités et des blocages, pas des versions de produit.

## Capacités présentes

- une pipeline canonique produit un DuckDB, un catalogue de tables, un manifeste et un index cryptographique compact;
- la CLI unique construit, valide, audite, archive et résume le produit;
- les univers territoriaux, leurs membres, la matrice de couverture, les fichiers substantiels, les revues et les résultats des gates sont matérialisés dans DuckDB;
- les résultats, mobilisations, régimes juridiques couverts, populations et relations territoriales sont réconciliés lorsque les entrées le permettent;
- les fichiers, sources, licences, classes d'affirmation et contrôles de confidentialité sont vérifiés;
- une CI unique reconstruit et soumet le paquet aux mutations critiques.

## Blocages factuels

- régimes juridiques incomplets pour 354 scrutins ou types de listes;
- grains et dénominateurs officiels absents pour plusieurs couvertures;

Les historiques de révision, géométries datées, lignées partisanes, candidatures, allocations de sièges et validations scientifiques restent des propositions hors du contrat public. Leur absence ne bloque pas la publication du périmètre actuel.

## Acquisitions utiles après consolidation

Une source n'entre dans la pipeline que si elle débloque une table active, un gate conservé, une question analytique ou une lacune prioritaire. L'ordre cible est : historique officiel des résultats; règles juridiques manquantes; univers et grains; limites territoriales datées; lignées partisanes; résolution de conflits; candidatures; sièges; métriques admissibles.

Chaque acquisition doit avoir un grain, une autorité, une URL, une date, une empreinte, une licence, des identifiants et un apport documentés avant ingestion.

## Améliorations prioritaires

1. terminer l'extraction des évaluateurs du module de publication vers les modules de gates déclaratifs;
2. effectuer deux constructions propres indépendantes et comparer les empreintes logiques;
3. acquérir les textes juridiques qui couvrent les 354 scrutins non classés;
4. reprendre ensuite, une source à la fois, les autres acquisitions utiles ci-dessus.
