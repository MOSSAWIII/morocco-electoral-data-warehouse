# Acquisition institutionnelle ciblée

Ce journal commence après la consolidation et la preuve de reconstruction propre. Une source n'est ajoutée au registre et à la pipeline que si elle apporte une preuve nécessaire à une table active ou à un gate conservé.

## Blocage juridique réellement observé

L'audit de la révision `ae3e4b2` laisse 354 concours sans lien dans `bridge_contest_legal_regime`. Il ne s'agit pas de 354 règles juridiques absentes : ce sont les mêmes 177 communes présentes dans `COMM2015` et `COMM2021`.

Les seuils applicables sont déjà épinglés par les textes officiels : 35 000 habitants en 2015 et 50 000 en 2021. La population RGPH 2014 existe aussi pour chacune des 177 communes. Le blocage est l'identité territoriale : leur identifiant hérité ne correspond pas au code HCP, et le rapprochement actuel repose sur un nom normalisé unique dans la même préfecture ou province. Il reste donc `DOCUMENTED_CROSSWALK` avec une confiance de `0.9`, alors que le gate exige une correspondance officielle ou revue à `1.0`.

Répartition des 177 communes :

| Préfecture ou province | Communes |
|---|---:|
| Settat | 30 |
| El Kelâa des Sraghna | 27 |
| Essaouira | 24 |
| Driouch | 20 |
| Al Hoceima | 13 |
| Sidi Bennour | 13 |
| Taroudannt | 11 |
| Jerada | 7 |
| Ouezzane | 6 |
| Tanger-Assilah | 5 |
| Tinghir | 5 |
| Errachidia | 4 |
| Figuig | 3 |
| Midelt | 3 |
| Berrechid | 2 |
| Chefchaouen | 2 |
| Salé | 2 |

## Tentative du 22 septembre 2026

Les cibles primaires examinées sont le [portail officiel des élections](https://www.elections.ma/), sa page des résultats communaux et sa page de découpage communal. Le portail confirme que ces domaines sont publiés, mais leur acquisition automatisée retourne un challenge Cloudflare exigeant JavaScript et cookies. Aucun extrait de moteur de recherche ni contenu de challenge n'est accepté comme donnée source.

Le classeur HCP officiel « Population légale … RGPH 2014 (16 régions) », à l'URL `https://www.rgph2014.hcp.ma/file/166315/`, a été téléchargé dans un espace temporaire : 162 951 octets, SHA-256 `502bc26c81d94bb7d23e507139e365de3c9a57aaec19af4113fff717e9e7d2bf`. Sa comparaison avec la version officielle à 12 régions confirme des codes HCP cohérents, mais ne fournit pas les anciens codes de groupes portés par les 177 identifiants hérités. Il n'est donc pas ajouté au registre : il ne fermerait aucun gate actif.

## Preuve encore requise

La prochaine acquisition admissible doit fournir, depuis le ministère de l'Intérieur, la DGCT ou le HCP, au moins l'un des éléments suivants :

- une table officielle reliant les identifiants hérités aux codes HCP complets;
- un export officiel du découpage ou des résultats communaux contenant un identifiant stable qui puisse être relié aux deux systèmes;
- une nomenclature versionnée des communes et de leurs changements de code.

Une simple égalité de nom, même unique dans une préfecture, ne sera pas promue à `1.0`. Toute acquisition devra enregistrer URL, date, taille, SHA-256, licence, grain et méthode de rapprochement, puis subir un test de mutation avant de modifier le gate.
