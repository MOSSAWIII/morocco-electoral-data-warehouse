# V16 — checklist d’intégrité électorale

Ce document est la liste de contrôle normative de V16. Une case n’est cochée que si un artefact et un test automatisé apportent une preuve. Les données officielles non encore acquises restent explicitement inconnues : l’existence d’un schéma ne vaut jamais preuve de couverture.

## P0 — Intégrité électorale

### 1. Préserver l’immuabilité de V15

- [x] Manifeste SHA-256 des artefacts V15 suivis dans Git (`metadata/v16/v15_immutable_checksums.json`).
- [x] Vérificateur qui échoue si un artefact V15 change (`morocco_elections.v16.immutability`).
- [x] Limites connues de V15 publiées (`docs/v16/V15_LIMITATIONS.md`).
- [x] Politique interdisant la réécriture silencieuse de `15.0.0` et exigeant une version distincte pour toute correction.
- [x] Vérifier les empreintes du paquet V15 public lors de chaque publication V16 (taille et SHA-256 épinglés).

### 2. Garantir la cohérence sémantique des faits

- [x] `fact.election_id = contest.election_id` validé avec erreur explicite.
- [x] `fact.geo_id = contest.geo_id` validé avec erreur explicite.
- [x] Année du fait égale à l’année de l’élection.
- [x] Parent régional attendu validé pour chaque territoire régionalisé.
- [x] Gate `SEMANTIC_FACTS_VALIDATED` recalculé ligne par ligne à partir des faits, concours, élections et géographies.
- [x] Violations couvertes par tests de mutation.
- [x] Gate sémantique lié en lecture seule aux trois tables factuelles et aux dimensions élection/concours/territoire de la base DuckDB déclarée; une ligne omise, même sans fait associé, échoue malgré un bundle régénéré et valide. Test d'intégration sur le seed V15 : 33 576 faits, 9 élections, 3 715 concours et 1 825 territoires comparés sans omission de liaison; les violations historiques restent visibles.
- [ ] Exécuter le validateur sur 100 % du paquet V16 final.

### 3. Introduire des univers électoraux externes

- [x] Contrat de table `coverage_universe`.
- [x] Source, date d’acquisition, type, statut de vérification et caractère externe obligatoires pour chaque dénominateur.
- [x] Couvertures acquise, officielle, territoriale, temporelle, documentaire et par champ publiées séparément.
- [x] Chaque ligne de matrice expose les `universe_id` vérifiés utilisés; une substitution d'identifiant échoue même si tous les totaux sont inchangés.
- [x] Univers territorial HCP RGPH 2014 extrait depuis 1 538 codes officiels explicites pour `COMM2015`, y compris quatre lignes à population `pm`; audit exact `PARTIAL` : 1 361 couverts, 177 attendus manquants, 177 observés inattendus.
- [x] Statut `UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR` sans dénominateur fiable.
- [x] Rejet des complétudes nationales fondées sur un dénominateur autoréférentiel.
- [x] Audit séparant les 1 538 concours communaux V15 (1 497 communes et 41 arrondissements) du total DGCL de 1 503 conseils : les six parents observés des arrondissements sont typés préfectures/provinces, non communes. La coïncidence arithmétique `1 497 + 6 = 1 503` est publiée comme non vérifiée et ne prouve aucun grain de conseil ni couverture complète.
- [x] Les 41 codes d'arrondissements explicitement étiquetés dans le classeur HCP RGPH 2014 concordent exactement avec les 41 arrondissements `COMM2015` V15; ce contrôle ne déduit ni l'identifiant ni le conseil de leurs communes de rattachement.
- [x] Sources officielles acquises : loi organique 113-14 publiée en juillet 2015, décret 2-15-577 publié au BO SGG n° 6381 avant le scrutin et guide DGCL historique de 2010. L'annexe du décret et les codes HCP produisent 41 liens candidats vers six communes nommées, avec sources vérifiées, confiance `0.9` et statut `PENDING_HUMAN_REVIEW_AND_BOUNDARY_ORDER`; une mutation de code ou de volume échoue.
- [x] BO 6374 original acquis et vérifié par taille/SHA-256 : le décret 2.15.402 publié avant `COMM2015` et son annexe (p. 6105–6136) énumèrent les désignations légales des communes et les membres à élire; PDF numérisé, aucune ligne d'univers n'est encore déclarée vérifiée.
- [x] Sonde OCR arabe reproductible pour les pages numérisées 6105–6136, à source SHA-256 épinglée et sortie `CANDIDATE_OCR_NOT_VERIFIED`; tests de rejet d'une source modifiée et d'une page hors annexe, sans production d'univers.
- [x] Lecture visuelle directe et transcription candidate des 46 lignes de la page 6105 : 12 Tanger–Assilah, 5 M’diq–Fnideq, 22 Tétouan, 7 Fahs–Anjra. Un test lie l'artefact au BO épinglé et rejette toute promotion en univers officiel ou tout identifiant électoral inventé; la graphie et les sièges restent à confirmer indépendamment.
- [x] Lecture visuelle directe et transcription candidate des 48 lignes de la page 6106 : 19 Larache et 29 Al Hoceïma, avec test de source, pagination et refus de `OFFICIAL_COMPLETE`.
- [x] Lecture visuelle directe et transcription candidate des 52 lignes de la page 6107 : 7 Al Hoceïma (suite), 28 Chefchaouen et 17 Ouezzane; pagination consécutive vérifiée.
- [x] Lecture visuelle directe et transcription candidate des 57 lignes de la page 6108 : 11 Oujda–Angad, 23 Nador et 23 Driouch; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 54 lignes de la page 6109 : 14 Jerada, 16 Berkane, 14 Taourirt et 10 Guercif; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 55 lignes de la page 6110 : 13 Figuig, 5 Fès, 21 Meknès et 16 El Hajeb; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 44 lignes de la page 6111 : 10 Ifrane, 11 Moulay Yaacoub et 23 Sefrou; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 53 lignes de la page 6112 : 21 Boulemane et 32 Taounate; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 55 lignes de la page 6113 : 17 Taounate (suite) et 38 Taza; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 59 lignes de la page 6114 : 2 Rabat, 4 Salé, 10 Skhirat–Témara, 23 Kénitra et 20 Khémisset; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 44 lignes de la page 6115 : 15 Khémisset (suite) et 29 Sidi Kacem; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 52 lignes de la page 6116 : 11 Sidi Slimane, 22 Beni Mellal et 19 Azilal; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 41 lignes de la page 6117 : 25 Azilal (suite) et 16 Fquih Ben Salah; source et sièges conservés.
- [x] Lecture visuelle directe et transcription candidate des 53 lignes de la page 6118 : 22 Khénifra et 31 Khouribga; source et sièges conservés.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 45 lignes de la page 6119 : 2 Casablanca, 6 Mohammedia, 27 El Jadida, 5 Nouaceur et 5 Mediouna; source et sièges conservés, sans promotion en univers officiel.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 37 lignes de la page 6120 : 15 Benslimane et 22 Berrechid. Les écarts de sièges Lahsasna (13 contre 27) et Laghnimyine (23 contre 17) restent exposés comme conflits, sans correction forcée.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 46 lignes de la page 6121 pour Settat. L'écart Bouguargouh (13 contre 16 sièges) reste exposé comme conflit, sans correction forcée.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 40 lignes de la page 6122 : 25 Sidi Bennour et 15 Marrakech. Les trois écarts de sièges de Sidi Bennour restent exposés et le conseil de Marrakech reste relié uniquement à son parent vérifié, sans être forcé sur les arrondissements TAFRA.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 53 lignes de la page 6123 : 35 Chichaoua et 18 Al Haouz. L'écart Tighedouine (23 contre 26 sièges) reste exposé comme conflit, sans correction forcée.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 53 lignes de la page 6124 : 22 Al Haouz et 31 El Kelâa des Sraghna; les 53 lignes se rapprochent sans nouveau conflit de sièges.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 43 lignes de la page 6125 : 12 El Kelâa des Sraghna et 31 Essaouira; les 43 lignes se rapprochent sans nouveau conflit de sièges.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 51 lignes de la page 6126 : 26 Essaouira et 25 Rehamna. L'écart Labrikiyne (13 contre 16 sièges) reste exposé comme conflit, sans correction forcée.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 36 lignes de la page 6127 : 25 Safi et 11 Youssoufia; les 36 lignes se rapprochent sans nouveau conflit de sièges.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 46 lignes de la page 6128 : 29 Errachidia et 17 Ouarzazate; les 46 lignes se rapprochent sans nouveau conflit de sièges.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 43 lignes de la page 6129 : 29 Midelt et 14 Tinghir; les 43 lignes se rapprochent sans nouveau conflit de sièges.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 49 lignes de la page 6130 : 11 Tinghir, 25 Zagora et 13 Agadir–Ida-Ou-Tanane. L'écart Takounite (23 contre 26 sièges) reste exposé comme conflit, sans correction forcée.
- [x] Lecture visuelle directe, assistée par la sonde OCR arabe épinglée, des 52 lignes de la page 6131 : 6 Inezgane–Ait Melloul, 22 Chtouka–Ait Baha et 24 Taroudant; les 52 lignes se rapprochent sans nouveau conflit de sièges.
- [ ] Lire et contrôler visuellement les autres pages de l'annexe BO 6374 (6132–6136) et obtenir une seconde revue des 1 307 lignes candidates des pages 6105–6131.
- [ ] Extraire et contrôler chaque désignation de commune, préfecture/province et nombre de sièges de l'annexe BO 6374; rapprocher ces désignations des identifiants électoraux et tester la couverture exacte avant toute prétention `COMPLETE`.
- [ ] Acquérir l'arrêté ministériel des limites auquel renvoie le décret 2-15-577, revoir humainement les 41 correspondances individuelles et obtenir les identifiants officiels des six conseils avant de matérialiser le grain conseil ou de prétendre à une couverture complète.
- [ ] Acquérir et vérifier les univers officiels nécessaires à la release.

L'univers HCP ci-dessus décrit les unités territoriales du recensement, pas la liste juridiquement attendue des concours ni les résultats officiels. Le BO 6374 fournit une liste juridique extérieure potentiellement utilisable pour les conseils communaux, mais ses lignes numérisées ne sont pas encore extraites, contrôlées ni reliées aux identifiants électoraux. Aucune de ces sources ne démontre donc actuellement une complétude électorale nationale; l'univers HCP n'est appliqué qu'à la dimension territoriale de `COMM2015`.

### 4. Recalculer et réconcilier les résultats

- [x] Contrôles inscrits/votants/valides/invalides/blancs.
- [x] Somme des voix comparée aux suffrages valides.
- [x] Somme des sièges comparée aux sièges à pourvoir.
- [x] Parts, rangs, gagnants, marges, HHI et ENP recalculés.
- [x] Rapprochement détail/agrégat.
- [x] Sortie normalisée `official_value`, `recomputed_value`, `difference`, `tolerance`, `validation_status`.
- [x] Valeur officielle de chaque rapprochement reliée à un `source_id` dont les octets et le SHA-256 sont revérifiés par le gate.
- [x] Gate lié au multiset complet de `fact_result_reconciliation` matérialisé; omission et mutation couvertes par tests malgré bundle/manifeste valides.
- [x] `turnout_rate` officiellement enregistré et recalculé depuis la ligne de mobilisation du paquet; une mutation coordonnée du registre et du contexte échoue avec bundle/manifeste valides.
- [x] Quatre contrôles de base possèdent exactement un statut par concours déclaré; l'omission d'un contrôle échoue avec identifiant de concours et métrique.
- [x] Motif `NOT_COMPUTABLE` contrôlé par vocabulaire et confronté aux composants de mobilisation matérialisés; une mutation coordonnée des faits et du contexte change le motif attendu et échoue.
- [x] Totaux partisans et indicateurs de vecteur `NOT_COMPUTABLE` sans ensemble attendu d'identifiants distincts et exactement concordant, avec test de somme partielle.
- [ ] Étendre la dérivation matérielle à chaque contrôle applicable et l'exécuter sur chaque concours du paquet final.
- [ ] Dériver chaque `recomputed_value` des faits du paquet et vérifier l'ensemble attendu des partis depuis une source électorale officielle externe.
- [ ] Exécuter les rapprochements sur tous les concours V16 finaux et résoudre/exposer chaque écart.

### 5. Imposer des vocabulaires contrôlés

- [x] Référentiels versionnés pour tous les champs structurants V16.
- [x] Validation automatique des valeurs.
- [x] Codes et significations documentés dans le contrat.
- [x] Nouvelle valeur impossible sans modification explicite du contrat et des tests.

### 6. Historiser les versions des résultats

- [x] Contrat distinct pour versions provisoires, définitives, rectifiées et annulées.
- [x] Statut, validité et source obligatoires; versions antérieures conservées.
- [x] Décisions juridiques reliables aux révisions affectées.
- [x] Décisions et révisions reliées à des sources officielles dont les octets sont vérifiés; une version remplacée doit être fermée sans chevauchement de validité.
- [x] Sélection déterministe de la version applicable à une date donnée.
- [ ] Charger l’historique officiel disponible et documenter ses lacunes.

## P1 — Reproductibilité institutionnelle

### 7. Structurer les régimes juridiques

- [x] Contrats `dim_legal_regime`, `bridge_election_legal_regime`, `bridge_contest_legal_regime`, `dim_contest_type`, `dim_seat_category`.
- [x] Contrats `fact_geo_population` et `bridge_geo_official_identifier` pour sourcer les seuils démographiques et leur correspondance territoriale.
- [x] Validité, article, base légale et source officielle obligatoires.
- [x] Octets des sources juridiques et démographiques vérifiés par taille et SHA-256 dans le gate juridique.
- [x] Seuils, formules d’attribution et types de listes structurés.
- [x] Validation qu’une élection couverte possède un régime applicable et vérifiable.
- [x] Gate juridique rapprochant chaque ligne et tous les champs du contrat, obligatoires et facultatifs (`valid_to`, seuils, sources de soutien et classification compris), du contexte aux trois tables matérialisées dans la base DuckDB déclarée. Test d'intégration indépendant sur le build V16 de développement : 15 régimes, 15 liens d'élection et 3 361 liens de concours concordent; une formule ou une règle de classification modifiée dans un bundle valide échoue.
- [x] Les 1 538 populations et 1 538 correspondances territoriales extraites indépendamment du classeur HCP concordent, ligne par ligne et sur tous les champs du contrat, avec les deux tables matérialisées du build V16 de développement. Le gate juridique lie exhaustivement ces tables au paquet et rejette une population modifiée dans un bundle valide.
- [x] Le gate juridique réextrait toutes les populations et correspondances depuis les octets HCP épinglés, la méthode déclarée et les géographies lues dans la base publiée sous SHA-256. Une falsification cohérente des tables, du manifeste, des rapports de build et du bundle, sans modification du classeur source, échoue sur les lignes source-dérivées; le build de développement vérifie 1 538 lignes de chaque type.
- [ ] Acquérir et encoder chaque texte officiel applicable.

### 8. Modéliser candidatures et attribution des sièges

- [x] Contrats séparés pour listes, candidatures, candidats et sièges attribués.
- [x] Chaque siège relié à un concours et une règle juridique.
- [x] Résultat reproduit comparé à l’officiel via le registre de rapprochement.
- [x] Écarts non résolus conservés avec statut et justification.
- [ ] Charger les candidatures et allocations officielles disponibles.

### 9. Historiser partis, coalitions et affiliations

- [x] Contrats versionnés et bornes de validité obligatoires.
- [x] Fusions, scissions, changements de nom et coalitions typés et traçables.
- [x] Validation temporelle empêchant une affiliation actuelle rétroactive.
- [x] Méthode de rapprochement de personne obligatoire et rejet de `NAME_ONLY`.
- [ ] Réviser humainement les lignées utilisées par les analyses longitudinales.

### 10. Historiser les géographies électorales

- [x] Découpages avec périodes de validité.
- [x] Relations parent-enfant et successions territoriales documentées.
- [x] Comparaisons directes limitées aux territoires compatibles.
- [x] Gate de comparaison directe interversions liant versions/successions à la base, vérifiant leurs sources et exigeant deux géométries GeoJSON du paquet à SHA-256 vérifié et contenu identique; tests de mutation de forme, d'inventaire, de CRS et de polygone mal fermé.
- [ ] Réextraire/reconstituer les géométries finales depuis les arrêtés et plans officiels, puis attester leur méthode et date d'effet; l'identité de deux fichiers dérivés ne prouve pas seule la fidélité aux limites juridiques.
- [x] Correspondances avec méthode, source et confiance.
- [x] Les correspondances code officiel exact ont confiance `1`; les rapprochements nom-parent à `0.9` restent exclus du gate juridique sans revue.
- [x] BO 6304 original acquis et vérifié par taille/SHA-256 : arrêtés 3375.14 (Fès), 3400.14 (Salé), 3401.14 (Tanger) relatifs aux pourtours des communes urbaines; source brute exclue du paquet public et test d'intégration de l'empreinte.
- [x] BO 6980 bis original acquis et vérifié par taille/SHA-256 : arrêtés 2019.20 (Tanger) et 2022.20 (Marrakech) publiés avant `COMM2021`, avec tableaux de limites de neuf arrondissements; géométries finales et date d'effet non attestées par cette case.
- [ ] Acquérir les arrêtés applicables à `COMM2015` pour Rabat, Casablanca et Marrakech ainsi que les cartes annexées et les limites juridiquement applicables à chaque arrondissement.
- [ ] Acquérir les géométries/découpages officiels redistribuables.

## P2 — Analyses scientifiquement valides

### 11. Corriger les cubes analytiques

- [x] Part régionale pondérée `SUM(party_votes) / SUM(valid_votes)`.
- [x] Moyenne communale non pondérée conservée sous un nom explicite.
- [x] HHI et ENP seulement si les parts respectent les préconditions.
- [x] Clé de grain explicite empêchant la duplication parlementaire.
- [x] Taux parlementaire nommé pour le corpus publié observé.
- [ ] Matérialiser les cubes sur le paquet V16 final et réconcilier leurs volumes.

### 12. Ajouter les indicateurs scientifiques sous conditions

- [x] Préconditions formalisées pour Gallagher, ENEP, ENPP, volatilité et fragmentation.
- [x] Formule, dénominateur et périmètre documentés.
- [x] Indicateur non calculé si une précondition échoue.
- [x] Résultat accompagné de sa couverture et de ses limites.
- [x] Aucun score de fraude ni conclusion causale produit par l’API.
- [ ] Calculer les indicateurs uniquement sur les périmètres finaux admissibles.

## Objectif transversal — publication vérifiable

### 13. Rendre chaque affirmation vérifiable

- [x] Contrat exigeant provenance, acquisition et licence pour chaque fichier publié.
- [x] Gate recalculant la redistribuabilité depuis une décision de licence sourcée; `METADATA_ONLY`, `UNKNOWN` et `FORBIDDEN` sont exclus des octets du paquet public.
- [x] Matrice par release : acquis, attendu, couvert, manquant, non comparable, redistribution interdite.
- [x] Génération/vérification des checksums et contrat de données versionné.
- [x] Procédure de reproduction documentée.
- [x] Preuve structurée de deux espaces de travail propres distincts; un booléen libre `clean_environment` ne suffit pas.
- [x] Tests de non-régression des nouvelles règles.
- [x] Gate interdisant de présenter prévisions, inférences IA ou données insuffisamment sourcées comme faits observés.
- [x] Gates distincts pour cohérence sémantique, candidatures/sièges, admissibilité analytique et redistribution légale.
- [ ] Étendre la liaison exhaustive désormais appliquée aux trois tables factuelles sémantiques à toutes les autres entrées du `PublicationContext` et aux fichiers du paquet final, avec comparaison des clés, nombres de lignes et valeurs; le bundle seul ne prouve pas cette exhaustivité.
- [ ] Produire puis vérifier le paquet public V16 complet dans un environnement propre.

## Gate final de publication

La publication reste `NOT_PUBLICATION_READY` tant qu’une case dépendant des données finales ou du paquet construit reste ouverte. Le validateur doit donner la raison exacte; aucune case ouverte ne peut être masquée par un score global.
