# V14.1 — Validité analytique

V14.1 est une correction du modèle public V14. Aucun fichier source et aucune observation parlementaire n'ont été ajoutés, supprimés ou modifiés.

Les métriques décrivent maintenant explicitement des questions et dates de réponse **publiées dans le corpus disponible**. `author_source_id` désigne une unité d'auteur publiée; seule une relation démontrée vers `person_id` désigne une personne canonique.

La dimension des législatures remplace la frontière codée en dur. Le début de la dixième législature est attesté par la [séance officielle du 14 octobre 2016](https://www.chambredesrepresentants.ma/fr/node/238313), et celui de la onzième par [l'ouverture officielle du 8 octobre 2021](https://www.chambredesrepresentants.ma/fr/taxonomy/term/10833?page=1). L'article 65 de la [Constitution de 2011](https://www.sgg.gov.ma/Portals/0/constitution/constitution_2011_Fr.pdf) encadre l'ouverture des sessions. Les périodes utilisent la législature, le type et les bornes de dépôt observées. Ces bornes ne sont jamais présentées comme les dates officielles de clôture des sessions.

La matrice de couverture reste intégralement `UNKNOWN`, car aucun dénominateur officiel des fichiers ou questions attendus n'est démontré. La spine d'exposition inclut les députés sans question observée et rapporte exclusivement des jours de mandat compris dans la fenêtre documentaire observée.

L'auteur source associé à 2 446 questions a été contrôlé localement : libellé individuel, raccordement exact au mandat, activité répartie sur 2021–2024 et 18 sources distinctes. La valeur est conservée sans suppression ni winsorisation.

Les dénominateurs de groupe, calendriers officiels complets, réponses textuelles, statuts riches, majorité/opposition, ministres, Chambre des conseillers et autres activités ne sont pas simulés. Ils attendent une source crédible.
