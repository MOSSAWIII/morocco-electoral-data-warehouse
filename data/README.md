# Zones de données locales

Ce répertoire contient des données non versionnées. Seul ce contrat est suivi par Git.

- `raw/` : octets sources immuables, classés par producteur et domaine.
- `legacy/` : entrées historiques nécessaires à la reproductibilité, notamment V8.
- `staging/` : données décodées et normalisées, recréables depuis RAW.
- `processed/` : tables canoniques intermédiaires indépendantes du moteur de stockage.
- `exports/` : produits dérivés, notamment les classeurs Excel.
- `tmp/` : travail temporaire supprimable.

Les chemins, empreintes et dimensions attendus sont définis dans `metadata/source_manifest.json`. `ELECTIONS_DATA_DIR` permet de placer cette arborescence sur un autre volume sans modifier le code.

Les sources HCP promues par V11 résident sous `raw/hcp/rgph/2014/` et `raw/hcp/rgph/2024/`. Une promotion déplace les octets qualifiés sans les transformer; les candidats restés `NO_GO` demeurent sous `staging/`.
