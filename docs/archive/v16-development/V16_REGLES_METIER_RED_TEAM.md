# Règles métier et garde-fous scientifiques pour l’analyse électorale marocaine

## Synthèse exécutive

Le socle V15 est déjà solide sur la reproductibilité technique : contrat canonique, formats réconciliés, provenance, valeurs manquantes explicites, précision temporelle, identités prudentes et couverture publiée. Le prochain gain de crédibilité ne viendra pas d’un indicateur supplémentaire isolé, mais d’un **contrat de validité électorale** qui distingue systématiquement le fait publié, la règle juridique applicable, le calcul reproduit, l’inférence analytique et le jugement normatif.

Le principal angle mort est le droit électoral versionné. Une même colonne `votes` ou `seats` ne porte pas la même signification analytique sous les régimes de 2002, 2011, 2016, 2021 et 2026. Pour les législatives de 2021, l’article 84 calcule le quotient local sur les **électeurs inscrits**, puis attribue les sièges restants au plus fort reste; la loi organique 53.25, applicable au prochain scrutin, modifie à nouveau de nombreuses dispositions.[^1][^2] Une analyse longitudinale qui ne fige pas la loi, le type de liste, la magnitude et le découpage attribuerait potentiellement au comportement électoral ce qui relève mécaniquement d’une réforme.

Le deuxième angle mort est la finalité du résultat. Les résultats annoncés ne sont pas nécessairement l’état juridictionnel final : la Cour constitutionnelle peut corriger les résultats, annuler une élection ou ordonner une partielle. Elle l’a fait après le scrutin de 2021.[^3][^4] Le modèle doit donc être bitemporel et conserver chaque état au lieu d’écraser la ligne antérieure.

Le troisième angle mort est l’univers statistique. « Complet dans le périmètre publié » ne signifie ni complet par rapport au scrutin officiel, ni représentatif de la population en âge de voter. En 2021, le HCP estimait 25,226 millions de Marocains en âge de voter, mais 17,509 millions seulement étaient inscrits; les écarts urbain/rural, femmes/hommes et par âge étaient importants.[^5] Les dénominateurs `population_18_plus`, `registered`, `voters`, `valid_votes`, `published_party_votes` et `legal_seats` doivent donc être séparés et nommés.

Enfin, au **14 septembre 2026**, l’élection législative prévue le **23 septembre 2026** n’a pas encore eu lieu.[^6] La V16 peut intégrer le cadre légal, le calendrier et les candidatures acceptées, mais aucun résultat, élu ou effet électoral 2026. Un garde-fou bloquant doit l’imposer.

## Diagnostic du projet actuel

### Forces à préserver

- RAW immuables, empreintes, source et date de récupération;
- contrat V15 unique pour 31 tables et contrôle des schémas;
- distinction entre `NULL`, `UNRESOLVED`, `PLANNED` et fait observé;
- matrices de couverture et limites injectées dans les analyses;
- corrections déclaratives, précision des dates et tests de mutation;
- séparation du résultat communal et du contrôle effectif de la présidence;
- pseudonymisation et refus des classements individuels lorsque les identités sont ambiguës;
- cubes réconciliés avec leurs tables de faits.

Ces choix sont cohérents avec la philosophie de TAFRA — source citée, transformations documentées, reproductibilité et identifiants communs — ainsi qu’avec les principes FAIR et les pratiques de recherche reproductible.[^7][^8][^9]

### Faiblesses structurantes observées

1. `dim_election.legal_framework_version` est un libellé, pas un registre de règles exécutables.
2. Aucun état explicite ne distingue résultat attendu, provisoire, proclamé, contesté, rectifié, annulé et définitif.
3. Les sièges officiels ne sont pas réconciliés avec une allocation reproduite selon le régime légal.
4. Les catégories juridiques de bulletins — valide, nul, contesté et non réglementaire — ne sont pas modélisées; la loi ne permet pas de les fusionner arbitrairement.[^10]
5. La couverture est souvent évaluée par rapport aux lignes déjà chargées, ce qui peut devenir tautologique sans registre externe de l’univers attendu.
6. Les résultats publiés ne descendent pas au bureau de vote. Cela interdit une vraie réconciliation verticale et limite fortement toute analyse d’intégrité; la publication au niveau bureau est une attente forte des standards d’ouverture.[^11][^12]
7. La moyenne non pondérée des parts communales est correctement nommée, mais reste facilement mal interprétable comme « part régionale ».
8. La comparabilité longitudinale ne possède pas encore de matrice bloquante `same_law × same_boundary × same_contest_type × same_party_lineage`.
9. Les indicateurs contextuels peuvent alimenter une erreur écologique si une corrélation communale est présentée comme un comportement individuel.[^13]
10. Les contrôles d’anomalies statistiques ne sont pas assortis d’un protocole empêchant de traduire « atypique » en « fraude »; les tests digitaux, notamment de type Benford, sont controversés et ne remplacent ni les procès-verbaux ni l’observation.[^14]
11. Le modèle ne couvre pas encore candidatures, financement, exposition médiatique, contentieux et décisions comme faits de première classe.
12. La pseudonymisation ne suffit pas à rendre des opinions ou affiliations politiques anonymes. La loi 09-08 les traite comme données sensibles.[^15]

## P0 — Règles bloquantes avant toute prétention scientifique

| ID | Règle métier à ajouter | Test d’acceptation minimal | Risque évité |
|---|---|---|---|
| BR-01 | Chaque `election_id` référence un `legal_regime_id` immuable, avec texte, article, date d’effet, type de scrutin, formule, seuil, magnitude, règle de reste, départage et catégories de sièges. | Aucune élection `PUBLISHED` sans régime complet et source officielle. | Calcul juridiquement faux. |
| BR-02 | Séparer `official_value`, `recomputed_value` et `difference`; un calcul interne ne remplace jamais le résultat officiel. | Pour chaque contest complet, allocation reproduite; différence = 0 ou exception sourcée. | Confusion preuve/calcul. |
| BR-03 | Versionner le statut du résultat : `SCHEDULED`, `POLL_CLOSED`, `PROVISIONAL`, `PROCLAIMED`, `CONTESTED`, `RECTIFIED`, `ANNULLED`, `FINAL`. | Transitions autorisées seulement; auteur, date de connaissance, date d’effet et décision obligatoires. | Écrasement du contentieux. |
| BR-04 | Bloquer toute ligne de résultat datée après la date d’observation du paquet. Pour 2026, seules loi, calendrier et candidatures sont admissibles avant le 23 septembre. | Mutation avec résultat 2026 au 14 septembre 2026 rejetée. | Donnée future présentée comme fait. |
| BR-05 | Le dénominateur est une dimension, jamais une convention implicite : `REGISTERED_FINAL_ROLL`, `VOTERS`, `VALID_BALLOTS`, `PUBLISHED_PARTY_VOTES`, `LEGAL_SEATS`, `PUBLISHED_SEATS`, `VAP_18_PLUS`. | Toute proportion porte `denominator_type`, `denominator_value`, source et date de gel. | Taux scientifiquement ambigu. |
| BR-06 | Le nombre d’inscrits est rattaché à la clôture définitive de la liste électorale et au contest exact. Il ne peut être remplacé par la population majeure. | `registered_voters` sans `register_snapshot_date` rejeté pour une allocation de sièges. | Quotient 2021/2026 erroné. |
| BR-07 | Préserver la taxonomie source des bulletins. Une correspondance `blank → null` n’est permise que si le texte/source le dit explicitement. | Identité comptable activée seulement pour des catégories compatibles et au même grain. | Faux taux de blancs/nuls. |
| BR-08 | Réconciliation comptable conditionnelle : inscrits ≥ émargements/votants ≥ bulletins/expressions compatibles ≥ valides; somme des voix partisanes = valides uniquement si la source affirme l’exhaustivité. | Chaque identité a `applicability_status`; jamais de zéro imputé. | Contrôles trop forts ou faux. |
| BR-09 | Séparer scrutins simultanés, bulletins et types de liste. Les législatives locale/régionale et les communales/régionales du même jour ne sont jamais sommées sans clé de contest. | Un agrégat mélangeant `contest_type` ou `list_type` échoue. | Double comptage. |
| BR-10 | Le découpage est temporel et légal : géométrie/crosswalk, décret, magnitude, population de référence et date d’effet. | Un résultat ne joint qu’une frontière valide le jour du scrutin. | Mauvaise carte ou faux swing. |
| BR-11 | Toute comparaison temporelle doit recevoir un statut `DIRECTLY_COMPARABLE`, `HARMONIZED`, `PARTIAL` ou `NOT_COMPARABLE`, calculé sur loi, limites, type de liste, couverture et lignée partisane. | Aucun `swing`, `volatility` ou tendance si statut non admissible. | Rupture de série masquée. |
| BR-12 | Définir un univers externe attendu par scrutin : contests, sièges, listes et, si disponibles, bureaux de vote. | Couverture = observé/attendu officiel; `COMPLETE_IN_PUBLISHED_SCOPE` ne vaut pas `OFFICIALLY_COMPLETE`. | Complétude tautologique. |
| BR-13 | Hiérarchie de preuve : décision juridictionnelle > proclamation officielle finale > procès-verbal signé > publication administrative > reproduction TAFRA > presse/agrégateur. Les conflits restent visibles. | Deux sources discordantes créent un conflit, pas un écrasement par date. | « Dernière source gagne ». |
| BR-14 | Les opinions politiques, identités et affiliations personnelles restent dans une zone contrôlée; publication agrégée, minimisation, finalité, durée de conservation et base juridique obligatoires. | Test de divulgation et revue CNDP avant export public. | Réidentification et non-conformité. |

### Registre juridique minimal

Ajouter au contrat canonique :

```text
dim_legal_regime(
  legal_regime_id, election_type, effective_from, effective_to,
  source_id, bulletin_officiel_number, law_number, article_number,
  allocation_method, quotient_denominator_type, threshold_pct,
  remainder_rule, tie_break_rule, single_list_minimum_rule,
  candidate_list_rule, seat_category_rule, review_status
)

fact_result_revision(
  revision_id, contest_id, authority_id, result_status,
  valid_time_from, valid_time_to, known_at, supersedes_revision_id,
  votes_json_digest, seats_json_digest, decision_id, evidence_id
)

fact_legal_decision(
  decision_id, court, case_number, decision_date, contest_id,
  remedy_type, affected_seats, corrected_values, source_id
)
```

Pour le régime 2021, encoder notamment : représentation proportionnelle, plus fort reste, quotient local `registered_voters / district_seats`, ordre de liste, départage prévu par la loi et règle spécifique de la liste/candidature unique.[^2] Pour 2026, la loi 53.25 et la décision de constitutionnalité doivent former une nouvelle version; les listes régionales comprennent exclusivement des candidates selon le texte publié.[^1][^16]

## P1 — Validité analytique et utilité décisionnelle

| ID | Règle métier à ajouter | Test d’acceptation minimal | Utilisateur principal |
|---|---|---|---|
| BR-15 | Publier deux ENP : `ENEP_votes = 1/Σvᵢ²` et `ENPP_seats = 1/Σsᵢ²`; ne jamais les confondre avec HHI sans échelle explicite.[^17] | Parts complètes, somme ≈ 1, résiduel documenté. | Recherche, think tanks. |
| BR-16 | Ajouter la disproportionnalité de Gallagher `LSq = √(0,5Σ(vᵢ-sᵢ)²)` au bon périmètre, avec traitement explicite des autres/indépendants.[^18] | Voix et sièges officiels complets au même niveau. | Institutions, chercheurs. |
| BR-17 | La part territoriale d’un parti est `Σvotes_party / Σvalid_votes_compatible`; la moyenne des parts communales demeure un descriptif de communes, jamais une part régionale. | Les deux mesures ont noms et unités distincts. | Cabinets, partis. |
| BR-18 | Ajouter `seat_bonus_pp`, rendement `seats_per_10k_votes`, voix non converties et coût marginal simulé, mais uniquement avec couverture complète et avertissement sur la règle légale. | Rejouer les sièges officiels avant publication de l’indicateur. | Stratégie, recherche. |
| BR-19 | Décomposer évolution observée en quatre composantes : comportement, participation/inscription, offre partisane et changement mécanique de loi/découpage. | Aucun commentaire causal à partir du seul delta brut. | Tous. |
| BR-20 | Les simulations contrefactuelles gèlent les voix et ne prétendent pas prédire le comportement sous une autre règle. | Résultat libellé `MECHANICAL_COUNTERFACTUAL`; hypothèse visible. | Partis, chercheurs. |
| BR-21 | Le rapprochement des partis encode continuité, changement de nom, alliance, scission, fusion et candidature commune avec probabilités/preuves distinctes. | Aucun swing à travers une lignée `UNRESOLVED`. | Recherche longitudinale. |
| BR-22 | Une association territoriale n’est jamais formulée comme comportement individuel; joindre un avertissement automatique d’erreur écologique et de MAUP aux analyses communales.[^13] | Le rapport bloque les formulations du type « les chômeurs votent X » sans microdonnées. | Recherche, médias. |
| BR-23 | Distinguer descriptif, associatif, prédictif et causal. Toute estimation causale déclare traitement, unité, estimand, identification, covariables prétraitement et diagnostics. | Pas de mot « effet » sans fiche causale validée. | Universités, cabinets. |
| BR-24 | Toute enquête/opinion publie sponsor, terrain, population cible, échantillonnage, taille, pondérations, non-réponse, questionnaire, design effect et incertitude.[^19] | Analyse refusée si fiche méthodologique incomplète. | Think tanks, sondages. |
| BR-25 | Les petits sous-groupes sont assortis de N, intervalle ou suppression; les comparaisons multiples déclarent famille de tests et correction. | Seuils configurables et rapportés. | Chercheurs. |
| BR-26 | Un score composite possède direction, normalisation, pondération, sensibilité et version. Aucun poids « expert » caché. | Analyse de sensibilité ±20 % des poids. | Cabinets, institutions. |
| BR-27 | Une anomalie n’est qu’un signal de revue. Aucun test statistique isolé ne produit `FRAUD`; résultat permis : `EXPECTED`, `ATYPICAL`, `DATA_ERROR_SUSPECTED`, `REQUIRES_DOCUMENT_REVIEW`.[^14] | Phrase « fraude détectée » interdite sans preuve externe qualifiée. | Observation, médias. |
| BR-28 | Les classements territoriaux publient couverture, incertitude, ex æquo, sensibilité et millésime. Les rangs individuels restent interdits. | Rang absent si couverture sous seuil ou écart non robuste. | Décideurs publics. |
| BR-29 | Chaque graphique/tableau embarque le périmètre, le grain, les filtres, la loi, le dénominateur, la couverture et la date de connaissance. | Test documentaire sur toute sortie de référence. | Tous. |

### Indicateurs utiles à contractualiser

| Famille | Mesure | Condition scientifique |
|---|---|---|
| Mobilisation | inscription/VAP, participation/inscrits, valides/votants, nuls/votants | Dénominateur daté, même univers et définition source. |
| Compétition | marge en voix et points, ENEP, ENPP, HHI, nombre de listes | Résultats exhaustifs au contest; HHI explicitement 0–10 000 ou 0–1. |
| Traduction voix-sièges | Gallagher, prime de sièges, rendement, voix non converties | Voix et sièges complets; règle légale et catégorie de siège identiques. |
| Territorialité | écart population/siège, magnitude, rural/urbain, accessibilité | Population HCP du millésime pertinent, frontière valide, pas d’inférence individuelle. |
| Représentation | candidatures, têtes de liste, élus par genre/âge/MRE/handicap si légalement publiable | Séparer candidatures, élus initiaux, remplacements et titulaires actifs. |
| Renouvellement | sortants candidats, réélus, entrants, durée de mandat | Identité prouvée et fenêtre d’exposition complète. |
| Gouvernance locale | parti arrivé premier, coalition, parti du président, délai de formation | Ne jamais déduire la présidence du seul gagnant électoral. |
| Activité parlementaire | questions par 100 jours de mandat observé, délai de réponse, thèmes | Corpus officiel attendu ou libellé strictement « publié ». |
| Financement | ressources, dépenses, plafond, dépôt à temps, réserves de la Cour | Données de contrôle, pas accusation; décision et période attachées. La Cour exigeait en 2021 le dépôt sous 60 jours après l’annonce définitive.[^20] |
| Médias | temps d’antenne, temps de parole, tonalité codée séparément, pluralisme | Fenêtres pré-campagne/campagne/jour du vote; média et rediffusion identifiés. La HACA fixe ces règles par scrutin.[^21][^22] |

## P2 — Extension institutionnelle et stratégique

| ID | Suggestion | Règle de prudence |
|---|---|---|
| BR-30 | Intégrer `fact_candidacy` : statut de dépôt/acceptation/retrait/rejet, ordre de liste, catégorie, investiture, titulaire/remplaçant. | Une candidature n’est ni un résultat ni un mandat. |
| BR-31 | Intégrer les procès-verbaux au plus petit grain disponible, avec image/PDF, OCR, valeur relue et signature/autorité. | OCR jamais canonique sans contrôle; garder le fac-similé. |
| BR-32 | Ajouter la chaîne de totalisation bureau → centralisateur → province/préfecture → région → national. | Chaque parent égale la somme de ses enfants ou porte une exception sourcée. |
| BR-33 | Modéliser le contentieux et les partielles comme événements modifiant les résultats et mandats. | Bitemporalité obligatoire; aucune réécriture silencieuse. |
| BR-34 | Intégrer comptes de campagne et financement public depuis la Cour des comptes. | Distinguer non-dépôt, retard, dépense non justifiée, dépassement et sanction définitive. |
| BR-35 | Intégrer le pluralisme audiovisuel HACA et, séparément, un corpus numérique. | Mesurer exposition ≠ persuasion; IA/désinformation seulement avec méthode et statut de vérification. |
| BR-36 | Ajouter un registre de promesses/programmes avec phrase source, thème, horizon, niveau compétent et statut de mesurabilité. | Ne pas noter la réalisation sans cible et source officielle comparables. |
| BR-37 | Créer un observatoire de disponibilité des données : délai de publication, granularité, format, licence, historique, stabilité URL. | Évalue la transparence de publication, pas automatiquement l’intégrité du scrutin. |
| BR-38 | Ajouter un protocole de prévision, seulement si demandé : date de gel, données disponibles à cette date, backtests, calibration, scénarios et intervalles. | Pas de probabilité sans validation hors échantillon; aucune micro-ciblage sensible. |
| BR-39 | Publier une API/semantic layer où les métriques sont versionnées et la requête exacte récupérable. | Même définition en SQL, API, tableau de bord et export. |

## Ce que les parties prenantes attendront d’un travail sérieux

### Chercheurs et revues scientifiques

Ils attendront un corpus cit-able et reproductible, des ruptures de séries explicitement traitées, des hypothèses préalables, une séparation claire entre descriptif et causal, des tests de robustesse et des données/code permettant la vérification indépendante. La disponibilité du code ne garantit pas la justesse; elle rend l’erreur inspectable, d’où la nécessité d’un contrôle substantiel en plus de la reproductibilité.[^9]

Livrables à prévoir : DOI par release, data paper, dictionnaire bilingue, cahier de validation, jeux de tests synthétiques, notebook entièrement régénérable et journal des résultats négatifs.

### Institutions de l’État

Elles valoriseront la conformité au Bulletin officiel, la population légale HCP, les états juridictionnels, la traçabilité des corrections, la protection des données et des indicateurs territoriaux stables. Le RGPH 2024 fournit désormais une population légale jusqu’à la commune; elle doit être liée par millésime et frontière, jamais substituée aux inscrits.[^23]

Livrables à prévoir : tableau de conformité juridique, réconciliation officielle, carte de couverture, registre des contestations/décisions, audit d’accès et notice CNDP.

### Partis politiques

Leurs besoins légitimes convergent sur la qualité des listes électorales, l’égalité de valeur du vote, le découpage, la participation, la représentation des femmes/jeunes/MRE, la conversion voix-sièges et la transparence des résultats. Ils divergent politiquement sur la formule. Le PJD demandait pour 2026 le retour à un quotient fondé sur les suffrages valides, tandis que la loi applicable conserve le cadre légal adopté; cette divergence doit être modélisée comme **scénarios**, jamais résolue par le dataset.[^24] L’USFP a également mis en avant inscription, abstention, découpage, supervision, dépouillement et contrôle.[^25]

Livrables à prévoir : simulateur mécanique multi-régimes, diagnostic de couverture et mobilisation, analyse de magnitude/découpage, recrutement/candidatures agrégé et scénarios de coalition — sans ciblage individuel fondé sur des données sensibles.

### Think tanks et société civile

Ils chercheront à relier confiance, participation, inclusion, transparence et action publique. Le CNDH observe aussi violences, discrimination envers les femmes, handicap, usage d’argent, impartialité, vie privée et conditions d’observation; ces thèmes montrent que l’intégrité ne se réduit pas aux résultats.[^26] Les enquêtes de confiance doivent rester séparées des faits électoraux et respecter leurs plans d’échantillonnage.[^27]

Livrables à prévoir : baromètre de transparence des données, tableau d’inclusion, analyse des écarts inscription/VAP, suivi des recommandations d’observation et dossiers méthodologiques publics.

### Cabinets de stratégie et directions data

Ils attendront une couche métrique stable, des segments territoriaux interprétables, des scénarios, des alertes de qualité, une API et des délais de mise à jour. Ils exigeront surtout que les mêmes chiffres soient obtenus dans le dashboard, le rapport et l’export. La règle à imposer est : une seule définition, versionnée, avec tests de réconciliation et journal de décision.

## Red-team — scénarios d’échec à tester

1. **Réforme confondue avec basculement électoral** : appliquer les voix 2016 sous la règle 2021 et montrer la part mécanique du changement avant tout commentaire politique.
2. **Résultat 2026 fabriqué avant le vote** : injecter une ligne datée du 23 septembre dans un paquet construit le 14; la CI doit échouer.
3. **Inscrits remplacés par majeurs HCP** : le quotient produit des sièges plausibles mais faux; le type de dénominateur doit bloquer le calcul.
4. **Moyenne communale vendue comme part régionale** : construire deux communes très inégales; la moyenne simple et la part pondérée divergent fortement.
5. **Commune renommée/fusionnée** : une jointure au nom crée un faux swing; seule une relation géographique datée est admissible.
6. **Alliance prise pour un parti continu** : des voix sont attribuées rétrospectivement à une composante; la lignée doit rester non comparable.
7. **Résultat proclamé ensuite annulé** : une décision de la Cour doit fermer la validité de la version, créer l’état `ANNULLED` et ouvrir la partielle.[^3]
8. **Couverture de 100 % auto-référentielle** : supprimer un contest avant la construction; le contrôle externe doit détecter l’absence.
9. **Doubles réponses parlementaires** : plusieurs réponses pour une question gonflent `COUNT(*)`; le cube doit compter `COUNT(DISTINCT question_id)` et déclarer le grain.
10. **Benford sur petits contests** : le système signale à tort une fraude; la sortie doit rester `NOT_APPLICABLE` ou `REQUIRES_REVIEW`.
11. **Corrélation pauvreté-vote transformée en profil d’électeur** : le générateur de texte doit refuser l’inférence individuelle.
12. **Réidentification** : combinaison commune rare × genre × mandat × date identifie une personne pseudonymisée; appliquer k-anonymat de publication ou suppression contextuelle.
13. **Source officielle corrigée** : la nouvelle version écrase l’ancienne; le test bitemporel et les digests doivent empêcher la perte.
14. **Catégories de bulletins fusionnées** : `blank_votes` et `invalid_votes` sont additionnés malgré des définitions incompatibles; le mapping doit échouer.
15. **Dashboard incohérent avec SQL** : une formule locale diverge du registre; le test de contrat sémantique doit échouer.

## Architecture d’ajout recommandée

### Lot 1 — V16.0 Validité juridique

- `dim_legal_regime`, `dim_contest_type`, `dim_seat_category`;
- `fact_result_revision`, `fact_legal_decision`;
- allocation reproductible des sièges et tests par mutations;
- garde-fou `as_of_date` et statut 2026;
- univers officiel attendu et couverture externe.

### Lot 2 — V16.1 Validité statistique

- registre des dénominateurs;
- comparabilité longitudinale calculée;
- ENEP/ENPP, Gallagher, part pondérée et décomposition mécanique;
- contrats descriptif/association/prédiction/causal;
- règles d’incertitude, petits N et anomalies.

### Lot 3 — V16.2 Intégrité du cycle électoral

- candidatures, procès-verbaux et chaîne de totalisation si les sources deviennent disponibles;
- contentieux et élections partielles;
- financement Cour des comptes;
- pluralisme HACA et observation CNDH;
- audit de confidentialité CNDP.

## Gate de publication proposé

Une analyse électorale ne reçoit le statut `PUBLICATION_READY` que si les assertions suivantes sont vraies :

```text
LEGAL_REGIME_PINNED
RESULT_STATUS_KNOWN
AS_OF_DATE_VALID
OFFICIAL_UNIVERSE_DECLARED
DENOMINATOR_TYPED
GRAIN_COMPATIBLE
BOUNDARY_COMPATIBLE
PARTY_LINEAGE_REVIEWED
SOURCE_CONFLICTS_RESOLVED_OR_EXPOSED
METRIC_RECONCILED
COVERAGE_DISCLOSED
UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE
PRIVACY_REVIEW_PASSED
CLAIM_CLASS_DECLARED
REPRODUCIBLE_FROM_CLEAN_ENVIRONMENT
```

Si une assertion échoue, le résultat peut rester exploratoire, mais son export doit porter `NOT_PUBLICATION_READY` et la raison exacte. C’est ce mécanisme — plus que le volume de données — qui fera reconnaître le projet comme scientifiquement prudent, contextuellement marocain et analytiquement utile.

## Sources

[^1]: Secrétariat général du Gouvernement, « [Loi organique n° 53.25 modifiant et complétant la loi organique n° 27.11 relative à la Chambre des représentants](https://www.sgg.gov.ma/Portals/1/lois/Loi_organique_53.25_ar.pdf) », Bulletin officiel n° 7478, 29 janvier 2026.
[^2]: Ministère de la Justice, « [Loi organique n° 27.11 relative à la Chambre des représentants, version consolidée au 1er juillet 2021](https://adala.justice.gov.ma/api/uploads/2024/12/18/DAHIRN_1%20%282%29-1734515609251.pdf) », notamment art. 79 et 84.
[^3]: Cour constitutionnelle du Maroc, « [Décision n° 190/22 relative à la circonscription de Driouch](https://www.courconstitutionnelle.ma/Decision?Page=Decision&id=2054) », 5 juillet 2022.
[^4]: Cour constitutionnelle du Maroc, « [Contentieux de l’élection des membres du Parlement](https://www.courconstitutionnelle.ma/Article?CC=6&Page=SPEC&id=56&tp=tx) », loi organique n° 066.13, art. 32–39.
[^5]: Haut-Commissariat au Plan, « [Quelques caractéristiques des primo-votants aux élections de 2021](https://www.hcp.ma/Quelques-caracteristiques-des-primo-votants-aux-elections-de-2021_a2742.html) », 7 septembre 2021.
[^6]: Portail officiel du Royaume du Maroc, « [Élections législatives marocaines 2026](https://www.maroc.ma/fr/elections-legislatives-marocaines-2026) », calendrier officiel consulté le 14 septembre 2026.
[^7]: TAFRA, « [Données — philosophie et catalogue](https://tafra.ma/donnees/) », consulté le 14 septembre 2026.
[^8]: Wilkinson et al., « [The FAIR Guiding Principles for scientific data management and stewardship](https://doi.org/10.1038/sdata.2016.18) », Scientific Data 3, 2016.
[^9]: Alan Turing Institute, « [The Turing Way](https://www.turing.ac.uk/research/research-projects/turing-way) », guide de recherche reproductible, éthique et collaborative.
[^10]: Ministère de la Justice, loi organique n° 27.11 consolidée, [article 79 et règles de conservation des bulletins](https://adala.justice.gov.ma/api/uploads/2024/12/18/DAHIRN_1%20%282%29-1734515609251.pdf), 2021.
[^11]: International IDEA, « [Open Data in Electoral Administration](https://www.idea.int/sites/default/files/publications/open-data-in-electoral-administration.pdf) », 2017.
[^12]: National Democratic Institute, « [Final Report on the 2011 Moroccan Parliamentary Elections](https://observationelections.cndh.ma/wp-content/uploads/2021/05/Morocco-Final-Election-Report-ENG.pdf) », recommandations sur le comptage et la publication détaillée.
[^13]: W. S. Robinson, « [Ecological Correlations and the Behavior of Individuals](https://fisher.stats.uwo.ca/faculty/aim/2015/9938/articles/Robinson1950AmericanSociologicalReview.pdf) », American Sociological Review 15(3), 1950.
[^14]: USAID, « [A Guide to Elections Forensics](https://pdf.usaid.gov/pdf_docs/PA00MXR7.pdf) », guide méthodologique et limites des tests d’anomalies.
[^15]: Commission nationale de contrôle de la protection des données à caractère personnel, « [Loi n° 09-08](https://www.cndp.ma/images/lois/Loi-09-08-Fr.pdf) », notamment la définition des données sensibles.
[^16]: Cour constitutionnelle du Maroc, « [Décision n° 259/25 sur la loi organique n° 53.25](https://www.courconstitutionnelle.ma/Decision?id=2123) », 24 décembre 2025.
[^17]: Markku Laakso et Rein Taagepera, « [Effective Number of Parties: A Measure with Application to West Europe](https://journals.sagepub.com/doi/pdf/10.1177/001041407901200101) », Comparative Political Studies 12(1), 1979.
[^18]: Michael Gallagher, « [Proportionality, Disproportionality and Electoral Systems](https://www.tcd.ie/Political_Science/about/people/michael_gallagher/ElectoralStudies1991.pdf) », Electoral Studies 10(1), 1991, p. 33–51, DOI 10.1016/0261-3794(91)90004-C.
[^19]: American Association for Public Opinion Research, « [Disclosure Standards](https://aapor.org/standards-and-ethics/disclosure-standards/) », standards minimaux de transparence méthodologique.
[^20]: Cour des comptes du Maroc, « [Production des comptes des campagnes électorales du scrutin du 8 septembre 2021](https://www.courdescomptes.ma/communique/communique-relatif-a-la-production-des-comptes-des-campagnes-electorales-aupres-de-la-cour-des-comptes-a-loccasion-du-scrutin-du-8-septembre-2021/) », 13 septembre 2021.
[^21]: Haute Autorité de la Communication Audiovisuelle, « [Rapport de suivi de la couverture médiatique des élections générales du 8 septembre 2021](https://www.haca.ma/fr/la-haca-rend-public-le-rapport-de-suivi-de-la-couverture-m%C3%A9diatique-des-%C3%A9lections-g%C3%A9n%C3%A9rales-du-8-0) », 22 novembre 2021.
[^22]: Haute Autorité de la Communication Audiovisuelle, « [Décision du CSCA n° 50-26](https://www.haca.ma/fr/node/8170/) », 16 juin 2026.
[^23]: Haut-Commissariat au Plan, « [Population légale du Royaume selon le RGPH 2024](https://www.hcp.ma/Population-legale-du-Royaume-du-Maroc-repartie-par-regions-provinces-et-prefectures-et-communes-selon-les-resultats-du_a3974.html) », 7 novembre 2024.
[^24]: Parti de la Justice et du Développement, « [Mémorandum dans le cadre des consultations pour les législatives 2026](https://www.pjd.ma/static/uploads/2025/09/%D9%85%D8%B0%D9%83%D8%B1%D8%A9-%D8%AD%D8%B2%D8%A8-%D8%A7%D9%84%D8%B9%D8%AF%D8%A7%D9%84%D8%A9-%D9%88%D8%A7%D9%84%D8%AA%D9%86%D9%85%D9%8A%D8%A9-%D9%81%D9%8A-%D8%A5%D8%B7%D8%A7%D8%B1-%D8%A7%D9%84%D9%85%D8%B4%D8%A7%D9%88%D8%B1%D8%A7%D8%AA-%D8%A7%D9%84%D8%B3%D9%8A%D8%A7%D8%B3%D9%8A%D8%A9-%D9%84%D9%84%D8%A5%D8%B9%D8%AF%D8%A7%D8%AF-%D9%84%D9%84%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8%D8%A7%D8%AA-%D8%A7%D9%84%D8%AA%D8%B4%D8%B1%D9%8A%D8%B9%D9%8A%D8%A9-%D9%84%D8%B3%D9%86%D8%A9-2026-1.pdf) », 2025.
[^25]: Union Socialiste des Forces Populaires, « [Mémorandum sur la réforme du système électoral](https://www.usfp.ma/fr/memorandum-de-lusfp-sur-la-reforme-du-systeme-electoral/) », 2020.
[^26]: Conseil national des droits de l’Homme, « [Conclusions de l’observation des élections 2021](https://www.cndh.ma/en/2021-elections-observation-cndh-conclusions-processing-3144-forms-related-campaign) », septembre 2021.
[^27]: Moroccan Institute for Policy Analysis, « [The Trust in Institutions Index IV 2023](https://mipa.institute/?lang=en&p=10689) », 2023.
