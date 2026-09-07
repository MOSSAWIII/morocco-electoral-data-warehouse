# Zones de données locales

Ce répertoire contient des données non versionnées. Seul ce contrat est suivi par Git.

- `raw/` : octets sources immuables, classés par producteur et domaine.
- `legacy/` : entrées historiques nécessaires à la reproductibilité, notamment V8.
- `staging/` : données décodées et normalisées, recréables depuis RAW.
- `processed/` : tables canoniques intermédiaires avant chargement PostgreSQL.
- `exports/` : produits dérivés, notamment les classeurs Excel.
- `tmp/` : travail temporaire supprimable.

Les chemins, empreintes et dimensions attendus sont définis dans `metadata/source_manifest.json`. `ELECTIONS_DATA_DIR` permet de placer cette arborescence sur un autre volume sans modifier le code.

