# Roadmap du warehouse électoral

Cette roadmap décrit des capacités et des blocages, pas des versions de produit.

## Capacités présentes

- une pipeline canonique produit un DuckDB, un catalogue de tables, un manifeste et un index cryptographique compact;
- la CLI unique construit, valide, audite, archive et résume le produit;
- les univers territoriaux, leurs membres et la matrice de couverture sont matérialisés dans DuckDB;
- les résultats, mobilisations, régimes juridiques couverts, populations et relations territoriales sont réconciliés lorsque les entrées le permettent;
- les fichiers, sources, licences, classes d'affirmation et contrôles de confidentialité sont vérifiés;
- une CI unique reconstruit et soumet le paquet aux mutations critiques.

## Blocages factuels

- statuts officiels et historique de révision des résultats insuffisamment structurés;
- régimes juridiques incomplets pour certains scrutins ou types de listes;
- grains et dénominateurs officiels absents pour plusieurs couvertures;
- géométries datées insuffisantes pour des comparaisons territoriales;
- lignées de partis et affiliations historiques non documentées à un niveau publiable;
- conflits entre sources encore exposés mais non résolus;
- candidatures et allocations de sièges non matérialisées;
- métriques scientifiques bloquées lorsque comparabilité ou couverture échoue.

## Acquisitions utiles après consolidation

Une source n'entre dans la pipeline que si elle débloque une table active, un gate conservé, une question analytique ou une lacune prioritaire. L'ordre cible est : historique officiel des résultats; règles juridiques manquantes; univers et grains; limites territoriales datées; lignées partisanes; résolution de conflits; candidatures; sièges; métriques admissibles.

Chaque acquisition doit avoir un grain, une autorité, une URL, une date, une empreinte, une licence, des identifiants et un apport documentés avant ingestion.

## Améliorations prioritaires

1. finir de matérialiser fichiers publiés, résultats de gates et revues nécessaires dans DuckDB;
2. retirer du contrat actif les schémas anticipatifs sans faits et les conserver comme propositions;
3. terminer l'extraction du validateur monolithique vers les modules de gates déclaratifs;
4. supprimer les wrappers `tools/` après une période de transition;
5. déplacer le code historique restant vers une archive lisible et prouver que le build canonique n'en dépend pas;
6. effectuer deux constructions propres indépendantes et comparer manifeste et empreintes logiques;
7. reprendre ensuite, une source à la fois, les acquisitions utiles ci-dessus.
