# Archives immuables du projet

Ce répertoire conserve les anciens pipelines, tests et documents pour la provenance et la consultation historique. Rien sous `archive/` n'est importé, distribué comme code actif, découvert par pytest ou requis par la construction du warehouse canonique.

Les snapshots de données publiés restent dans les assets de release avec leurs checksums. Le code archivé n'est modifié que pour une correction de conservation explicitement documentée; toute évolution métier se fait dans `src/morocco_elections/warehouse/`.

Le produit actif est défini par `src/morocco_elections/warehouse/`, `metadata/warehouse/`, `metadata/source_manifest.json` et la documentation fonctionnelle de premier niveau. Les anciens noms de versions et récits de release ne sont conservés ici que pour l'auditabilité.

Les anciens scripts de `tools/` sont conservés sous `archive/legacy-code/tools/`. L'interface active unique est `python -m morocco_elections`.
