# Zones de données locales

Ce répertoire contient des données non versionnées. Seul ce contrat est suivi par Git.

- `raw/` : octets sources immuables, classés par producteur et domaine.
- `legacy/` : entrées historiques nécessaires à la reproductibilité, notamment V8.
- `staging/` : données décodées et normalisées, recréables depuis RAW.
- `processed/` : tables canoniques intermédiaires indépendantes du moteur de stockage.
- `exports/` : produits dérivés, notamment Excel et le paquet V13 CSV/Parquet/DuckDB.
- `tmp/` : travail temporaire supprimable.

Les acquisitions génériques sont placées sous `raw/<domaine>/acquisitions/<source_id>/<préfixe_sha256>/`. Chaque version contient les octets originaux et un `acquisition.json` local avec provenance et profil. Deux fichiers différents ne peuvent donc jamais s'écraser. Leur présence en RAW ne vaut pas validation ni ingestion dans le warehouse.

Les chemins, empreintes et dimensions attendus sont définis dans `metadata/source_manifest.json`. `ELECTIONS_DATA_DIR` permet de placer cette arborescence sur un autre volume sans modifier le code.

Les sources HCP promues par V11 résident sous `raw/hcp/rgph/2014/` et `raw/hcp/rgph/2024/`. Une promotion déplace les octets qualifiés sans les transformer; les candidats restés `NO_GO` demeurent sous `staging/`.

Les quatre ressources parlementaires promues par V12 résident sous `raw/parliament/questions/written/2023/`. Elles restent dans leurs octets officiels d'origine; V12 ne copie dans la table canonique que leur contenu observé et ses clés de raccordement explicites.
