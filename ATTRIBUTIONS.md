# Sources et attributions

Les fichiers sources ne sont pas redistribués dans ce dépôt. Les registres canoniques `metadata/source_manifest.json` et `metadata/warehouse/official_source_registry.json` conservent leurs URLs, producteurs, versions, licences déclarées, chemins et empreintes SHA-256.

Les principales familles de sources sont :

- TAFRA / elections.ma : résultats communaux 2015 et 2021, composition des conseils communaux 2015 et 2021, membres de la Chambre des représentants 2007–2026 et archives électorales nationales et régionales ;
- Haut-Commissariat au Plan : populations légales RGPH 2014 et 2024 ;
- SIG-Maroc : couche géographique communale dérivée des données HCP RGPH 2024, dont les conditions de réutilisation doivent être revérifiées avant redistribution ;
- Secrétariat général du gouvernement : Bulletin officiel n° 7037 du 8 novembre 2021 et autres textes juridiques identifiés dans le registre officiel ;
- Parlement du Royaume du Maroc via data.gov.ma : questions écrites et orales publiées sous la licence déclarée par la source.

Chaque fichier diffusé est identifié par son empreinte dans les tables de provenance du warehouse. Les anciens contrats de release et rapports de qualification sont conservés sous `archive/legacy-metadata/` et `archive/legacy-docs/`; ils ne constituent pas le contrat actif.

Une mention de licence dans ce dépôt décrit la source concernée ; elle ne constitue pas une licence générale du code ou de l'ensemble du warehouse.

La politique applicable au paquet composite est détaillée dans [`LICENSES/DATA.md`](LICENSES/DATA.md). Les attributions doivent conserver le producteur, le titre ou identifiant de source, l'URL et la licence inscrits dans le warehouse. Les transformations du projet ne doivent pas être présentées comme des résultats officiels du producteur source.
