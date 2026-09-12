MOROCCO ELECTORAL DATA WAREHOUSE — PAQUET OUVERT V14.1

Généré le : 2026-09-12
Baseline immuable : V14

PORTÉE ANALYTIQUE

V14.1 mesure le volume et le contenu des questions publiées dans les fichiers disponibles.
Il ne mesure ni la performance globale d'un député, ni le taux réel de réponse gouvernementale,
ni l'activité exhaustive du Parlement marocain.

CORRECTIONS

- Les métriques portent désormais le préfixe published_ lorsqu'elles décrivent le corpus publié.
- author_source_id représente un libellé source; person_id reste une personne canonique raccordée.
- Les périodes incluent la législature et les bornes observées du corpus, jamais présentées comme
  dates officielles de session.
- La couverture reste UNKNOWN faute de dénominateur officiel de fichiers ou de questions attendus.
- La spine d'exposition inclut les personnes mandatées sans question observée dans une fenêtre couverte.
- Le parti d'une question est attribué seulement lorsqu'un intervalle de mandat couvre deposit_date.

LIMITES NON MASQUÉES

- observed_through_date reste NULL : retrieved_at ne prouve pas la date réelle de censure.
- Les fins officielles des sessions ne sont pas déduites des seules dates de questions.
- La correspondance historique groupe-mandat n'est pas démontrée; aucun member-day de groupe n'est publié.
- Les coauteurs ne sont pas séparés sans convention source explicite.
- Les réponses textuelles, statuts riches, ministres, majorité/opposition, Chambre des conseillers,
  votes, commissions et impacts exigent de nouvelles sources et ne reçoivent aucune table vide.

CONTRÔLES

Questions publiées dédupliquées : 65748
Questions avec date de réponse publiée : 30257
Cellules d'exposition personne × période × type : 23424
Cellules de couverture documentaire : 61
