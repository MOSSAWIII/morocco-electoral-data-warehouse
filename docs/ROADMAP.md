# Roadmap du warehouse électoral

Cette roadmap décrit des capacités et des blocages, pas des versions de produit.

## Capacités présentes

- une pipeline canonique produit un DuckDB, un catalogue de tables, un manifeste et un index cryptographique compact;
- dix vues de consommation dans ce DuckDB couvrent les quinze questions analytiques minimales sans dupliquer les faits;
- les 45 tables ont chacune un rôle, un grain, une clé logique, des relations autorisées, un usage et des limites dans le catalogue automatisé;
- la CLI unique construit, valide, audite, archive et résume le produit;
- les univers territoriaux, leurs membres, la matrice de couverture, les fichiers substantiels, les revues et les résultats des gates sont matérialisés dans DuckDB;
- les résultats, mobilisations, régimes juridiques couverts, populations et relations territoriales sont réconciliés lorsque les entrées le permettent;
- les fichiers, sources, licences, classes d'affirmation et contrôles de confidentialité sont vérifiés;
- une CI unique reconstruit et soumet le paquet aux mutations critiques.
- deux constructions propres indépendantes ont produit les mêmes 45 tables et sorties déterministes; le protocole et les empreintes sont consignés dans [CLEAN_REBUILD_PROOF.md](CLEAN_REBUILD_PROOF.md), et la CI répète cette comparaison;

## Blocages factuels

- rattachement juridique incomplet pour 354 concours : les règles et populations sont acquises, mais 177 communes répétées sur deux scrutins attendent une correspondance officielle entre identifiant hérité et code HCP;
- grains et dénominateurs officiels absents pour plusieurs couvertures;

Les historiques de révision, géométries datées, lignées partisanes, candidatures, allocations de sièges et validations scientifiques restent des propositions hors du contrat public. Leur absence ne bloque pas la publication du périmètre actuel.

## Acquisitions utiles après consolidation

Une source n'entre dans la pipeline que si elle débloque une table active, un gate conservé, une question analytique ou une lacune prioritaire. L'ordre cible est : historique officiel des résultats; règles juridiques manquantes; univers et grains; limites territoriales datées; lignées partisanes; résolution de conflits; candidatures; sièges; métriques admissibles.

Chaque acquisition doit avoir un grain, une autorité, une URL, une date, une empreinte, une licence, des identifiants et un apport documentés avant ingestion.

## Améliorations prioritaires

1. acquérir la correspondance institutionnelle d'identifiants qui permettra de classer les 177 communes, sans promouvoir une égalité de nom; le diagnostic et les tentatives sont consignés dans [INSTITUTIONAL_ACQUISITION.md](INSTITUTIONAL_ACQUISITION.md);
2. reprendre ensuite, une source à la fois, les autres acquisitions utiles ci-dessus.
