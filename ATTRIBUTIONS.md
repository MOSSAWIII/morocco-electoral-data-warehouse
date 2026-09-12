# Sources et attributions

Les fichiers sources ne sont pas redistribués dans ce dépôt. Le manifeste `metadata/source_manifest.json` conserve leurs URLs, producteurs, versions, licences déclarées, dimensions, anciens/nouveaux chemins et empreintes SHA-256.

Sources historiques de la baseline V9 :

- TAFRA / elections.ma, résultats communaux 2015 et 2021 — CC BY 4.0 selon la fiche source.
- TAFRA / elections.ma, composition des conseils communaux 2021 — CC BY 4.0 selon la fiche source.
- TAFRA et sources parlementaires, membres de la Chambre des représentants 2007–2026 — CC BY 4.0 selon la fiche source.
- Haut-Commissariat au Plan, population légale du RGPH 2024 — publication officielle publique.
- SIG-Maroc, couche géographique communale dérivée des données HCP RGPH 2024 — source secondaire publique ; conditions de réutilisation à revérifier avant redistribution.
- Haut-Commissariat au Plan, tables officielles de population légale RGPH 2014 et 2024 — utilisées pour valider cinq codes géographiques V10.
- Secrétariat général du gouvernement, Bulletin officiel n°7037 du 8 novembre 2021, arrêté n°3267.21 — utilisé pour documenter les vacances de sièges d’Ait Abdallah et Talgjount.

Le cœur électoral V13 ajoute six archives TAFRA/openAFRICA couvrant les législatives 2007, 2011, 2016 et 2021 ainsi que les régionales 2015 et 2021. Les URLs, empreintes et conditions déclarées sont conservées dans `metadata/source_manifest.json` et dans la table `SOURCES`; seules les mesures autorisées par `metadata/v13_electoral_qualification.json` sont diffusées.

V14 réunit 59 fichiers uniques de questions écrites et orales publiés par le Parlement du Royaume du Maroc via data.gov.ma sous licence ODbL déclarée. Les huit familles, URLs et conditions sont inscrites dans `metadata/acquisition_catalog.json`; chaque fichier diffusé est identifié par son SHA-256 dans `metadata/v14_open_distribution.json` et dans `dim_parliamentary_source`.

Une mention de licence dans ce dépôt décrit la source concernée ; elle ne constitue pas une licence générale du code ou de l'ensemble du warehouse.

La politique applicable au paquet composite est détaillée dans [`LICENSES/DATA.md`](LICENSES/DATA.md); elle ne remplace jamais les droits attachés à chaque contenu source. Les attributions doivent conserver le producteur, le titre ou identifiant de source, l'URL et la licence indiqués dans `SOURCES`. Les transformations du projet ne doivent pas être présentées comme des résultats officiels du producteur source.
