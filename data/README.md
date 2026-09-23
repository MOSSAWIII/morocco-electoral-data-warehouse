# Zones de données locales

Ce répertoire contient les données non versionnées. Seul ce contrat est suivi par Git.

- `raw/` : octets sources immuables, classés par producteur et domaine ;
- `seeds/historical/` : seed historique vérifié, extrait depuis l'archive épinglée ;
- `staging/` : données décodées et normalisées, recréables depuis les sources ;
- `processed/` : tables canoniques intermédiaires indépendantes du moteur ;
- `exports/open/warehouse/` : paquet canonique construit ;
- `tmp/` : travail temporaire supprimable.

Les acquisitions sont adressées par source et préfixe SHA-256. Les chemins, tailles et empreintes attendus résident dans les registres canoniques. La présence locale d'un fichier ne vaut jamais validation : tout octet consommé est revérifié avant lecture.

Les anciennes arborescences nommées par version sont historiques et ne font pas partie du parcours utilisateur actuel.
