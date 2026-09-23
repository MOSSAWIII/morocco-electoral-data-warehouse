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

## Tentative du 23 septembre 2026

Deux nouvelles pistes HCP ont été examinées sans être ajoutées au registre,
car aucune ne relie les identifiants internes aux codes HCP :

- le [Code géographique du Maroc 2011](https://www.hcp.ma/region-marrakech/attachment/681918/)
  est bien une nomenclature institutionnelle. Il confirme toutefois directement
  les codes HCP déjà disponibles. Par exemple, `Ait Kamra` y porte
  `051.05.01`, comme dans le fichier RGPH utilisé par le build, tandis que
  l'identifiant interne non résolu est `MA-01-051-1101`. Le document ne
  contient pas `051.11.01` et ne fournit donc pas le pont recherché;
- l'URL HCP indexée comme
  [« Communes et arrondissements »](https://www.hcp.ma/file/233918/) a été
  téléchargée dans un espace temporaire. Le fichier obtenu compte
  28 159 809 octets, porte le SHA-256
  `d62869636e2fd31792455527d7909ed9afbacab0a1a8560cffac1b040d5f0d1b`
  et contient 453 pages numérisées. L'inspection visuelle de la couverture
  l'identifie comme l'`Annuaire statistique du Maroc 1983`; il ne s'agit pas
  d'une nomenclature de communes et il ne ferme aucun gate.

Ces deux fichiers restent exclus des sources actives. La recherche demeure
limitée à un export institutionnel contenant soit l'identifiant interne, soit
une clé stable commune aux deux systèmes; une seconde liste de noms et codes
HCP n'est pas suffisante.

La recherche des univers officiels de résultats n'a pas davantage produit de
source admissible :

- la page officielle des résultats législatifs 2016 sur `elections.ma` est
  repérable, mais son téléchargement automatisé est refusé par la protection
  du site (`HTTP 403`). Sans octets stables, aucun fichier ne peut être épinglé
  par taille et SHA-256 ni intégré à la chaîne de preuve;
- les pages de la Chambre des représentants consacrées à la composition des
  législatures 2011–2016 et 2016–2021 décrivent un état parlementaire postérieur
  au scrutin. Les remplacements et changements d'affiliation possibles les
  rendent impropres à servir de proclamation officielle des résultats.

Ces pages sont donc conservées comme pistes documentaires seulement. La levée
du gate exige toujours une proclamation ou un export institutionnel stable qui
déclare explicitement l'univers électoral et puisse être archivé, haché et
rejoué.

## Identifiants secondaires conservés

Les deux classeurs TAFRA épinglés de résultats communaux contiennent un champ
`idCommune` distinct de l'identifiant interne du warehouse. Le build conserve
désormais cette clé dans `dim_electoral_contest.source_contest_id` uniquement
lorsque le couple préfecture/province et commune est unique et identique après
normalisation. Il retrouve ainsi 1 530 concours sur 1 538 pour chacun des
scrutins de 2015 et 2021; les huit autres restent explicitement sans identifiant
source plutôt que de recevoir l'identifiant interne par défaut.

Pour les 177 identités communales encore non résolues, les deux classeurs
fournissent tous un identifiant secondaire unique et stable entre 2015 et 2021.
Par exemple, `MA-01-051-1101` (Ait Kamra) porte `idCommune = 968` dans les deux
sources. Ce constat fournit une clé d'acquisition concrète et préserve mieux la
provenance, mais ne change ni la confiance `0.9`, ni la méthode
`DOCUMENTED_CROSSWALK`, ni le statut du gate : TAFRA reste une copie secondaire
attribuée à `elections.ma`, et aucune source institutionnelle acquise ne relie
encore `968` au code HCP `01.051.05.01.`.

L'implémentation historique du portail a également été retrouvée dans la
[capture du 16 septembre 2015](https://web.archive.org/web/20150916012118id_/http://www.elections.ma/elections/communales/resultats.aspx).
Le formulaire officiel transmet les paramètres `Region`, `province`, `Commune`
et `Circ` au service `Electionweb.asmx/getListElus_Com`; `idCommune` est donc une
clé exploitable pour une acquisition ciblée. Cette piste ne fournit toutefois
pas encore de preuve : les captures archivées des méthodes du service ne
contiennent qu'une page « Request Rejected » de 189 octets, tandis que les
requêtes `POST` vers le service actif retournent `HTTP 403`. Aucun résultat de
service associant `968` à Ait Kamra n'est disponible dans les octets acquis.

Une troisième piste institutionnelle a été vérifiée auprès de la Cour des
comptes : la
[synthèse relative au scrutin législatif du 7 octobre 2016](https://www.courdescomptes.ma/wp-content/uploads/2018/11/Synthese-des-rapports-relatifs-aux-depenses-electorales-concernant-le-scrutin-du-7-octobre-2016-pour-lelection-des-membres-de-la-chambre-des-representants.pdf).
Le PDF obtenu compte 495 217 octets et porte le SHA-256
`ee8dc2771f27d0e7913e77213d8ee255a12db2ca4ad0ebc377ab16c369762bbb`.
Il confirme que 1 407 mandataires de listes briguaient 395 sièges et indique en
note que les résultats ont été proclamés le 8 octobre 2016.

Son tableau par parti ne constitue cependant pas une allocation de sièges : il
ventile les mandataires de listes selon le dépôt de leur déclaration de dépenses
et leur qualité d'élu ou de non-élu. Par exemple, ses 93 mandataires PJD ne sont
pas les 125 sièges généralement attribués au parti. Le document ne contient pas
non plus une chaîne de statuts ou de rectifications rattachable à chaque résultat
matérialisé. Il n'est donc ajouté ni comme univers officiel ni comme historique
de résultats. Il pourra seulement corroborer une date de proclamation lorsqu'une
publication des résultats au grain requis aura elle-même été acquise.
