# V14 — Parlement longitudinal

V14 conserve le modèle public V13 et remplace son sous-ensemble parlementaire 2023–2024 par l'union dédupliquée de ce corpus et des nouvelles questions écrites ou orales publiées entre le 25 janvier 2017 et le 24 avril 2024.

## Apports

- 65 748 questions canoniques issues de 66 974 occurrences source ;
- 40 225 questions écrites et 25 523 questions orales ;
- 30 257 dates de réponse publiées ;
- 59 fichiers physiques uniques appartenant à huit familles de sources ;
- 26 932 questions raccordées exactement à 365 personnes canoniques ;
- 3 142 trajectoires dérivées au grain `personne × législature × période × type` ;
- provenance ligne à ligne, CSV, Parquet, DuckDB, manifeste et checksums.

## Limites

La couverture mesure exclusivement les fichiers publiés et acquis; elle ne démontre pas l'exhaustivité de l'activité parlementaire. Les 38 816 questions dont l'auteur n'est pas raccordé restent conservées avec `person_id=NULL`. Aucun rapprochement flou n'est appliqué.

Une date de réponse absente signifie seulement qu'aucune date n'est publiée dans les fichiers disponibles. Elle ne prouve pas qu'aucune réponse n'a existé.

Les libellés nominatifs d'auteur restent hors du paquet public. Les textes des questions, objets, groupes et institutions demeurent des valeurs source et ne constituent pas une taxonomie éditoriale du projet.

## Compatibilité

Les quinze tables publiques V13 autres que l'ancienne activité partielle sont conservées sans changement logique. La table `fact_parliamentary_activity` est retirée afin d'éviter une double définition; elle est remplacée par les dimensions, faits et ponts parlementaires V14.
