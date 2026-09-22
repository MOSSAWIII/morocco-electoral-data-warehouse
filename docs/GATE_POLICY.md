# Politique des contrôles de publication

Un gate protège un risque observable. Il ne valide jamais une approbation qu'a produite la même exécution sans preuve externe. Les contraintes locales simples appartiennent au schéma DuckDB ou aux tests; la reproductibilité du build appartient à la CI. Un gate `DOMAIN_BLOCKING` n'est exécuté que si le domaine correspondant est publié.

| Gate actuel | Classe cible | Domaine | Risque empêché et données inspectées | Mutation minimale détectée | Coût | Décision |
|---|---|---|---|---|---|---|
| `EVIDENCE_BUNDLE_VERIFIED` | REDUNDANT | preuves | modification ou fichier non inventorié; bundle et fichiers | altérer un octet d'un fichier publié | élevé (JSON massif) | remplacer par manifeste compact + empreintes DuckDB |
| `SEMANTIC_FACTS_VALIDATED` | CORE_BLOCKING | tous | violation de contrat; tables DuckDB | valeur hors vocabulaire, clé ou invariant | élevé | conserver, découper par domaine et lire DuckDB |
| `LEGAL_REGIME_PINNED` | DOMAIN_BLOCKING | élections | régime absent ou non sourcé; tables légales et sources | changer une règle ou son SHA-256 | moyen | conserver si résultats publiés |
| `RESULT_STATUS_KNOWN` | DOMAIN_BLOCKING | résultats | statut officiel inventé; révisions et décisions | déclarer `FINAL` sans preuve structurée | faible | conserver si historique publié; sinon lacune informative |
| `AS_OF_DATE_VALID` | CORE_BLOCKING | tous | fuite temporelle; dates de connaissance/effet | dater un fait après le snapshot | faible | conserver |
| `OFFICIAL_UNIVERSE_DECLARED` | DOMAIN_BLOCKING | couverture | fausse complétude; univers et membres | retirer un identifiant attendu | moyen | conserver lorsque complétude revendiquée |
| `DENOMINATOR_TYPED` | REDUNDANT | couverture | dénominateur ambigu; mêmes univers | modifier le dénominateur sans les membres | faible | fusionner dans `OFFICIAL_UNIVERSE_DECLARED` |
| `GRAIN_COMPATIBLE` | CORE_BLOCKING | tous | doublon ou grain incohérent; clés DuckDB | dupliquer une clé métier | moyen | conserver, déplacer les unicités simples en contraintes/tests |
| `BOUNDARY_COMPATIBLE` | DOMAIN_BLOCKING | territoires | comparaison de frontières incompatibles | marquer comparable une géométrie différente | élevé | conserver seulement pour analyses intertemporelles |
| `PARTY_LINEAGE_REVIEWED` | DOMAIN_BLOCKING | partis | filiation non sourcée | ajouter une lignée sans revue | faible | conserver conditionnel; absent tant que le domaine n'est pas publié |
| `SOURCE_CONFLICTS_RESOLVED_OR_EXPOSED` | CORE_BLOCKING | provenance | arbitrage silencieux entre sources | masquer un conflit détecté | moyen | conserver |
| `CANDIDACY_AND_SEATS_VALIDATED` | DOMAIN_BLOCKING | candidatures | candidat ou siège incohérent | siège sans liste/régime | moyen | conserver hors registre actif tant que domaine exclu |
| `METRIC_RECONCILED` | DOMAIN_BLOCKING | résultats | divergence entre valeur officielle et recalcul | modifier votes, sièges ou tolérance | élevé | conserver |
| `ANALYTIC_METRICS_ADMISSIBLE` | DOMAIN_BLOCKING | indicateurs | métrique calculée malgré préconditions échouées | forcer `COMPUTED` avec couverture partielle | faible | conserver si métriques analytiques publiées |
| `COVERAGE_DISCLOSED` | DOMAIN_BLOCKING | couverture | lacune masquée; matrice et univers | diminuer `missing` sans ajouter de faits | moyen | conserver et lire les tables DuckDB |
| `UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE` | DOMAIN_BLOCKING | analyses | affirmation prédictive/causale sans limites | supprimer l'avertissement d'une telle affirmation | faible | conserver conditionnel; sans effet pour faits descriptifs |
| `PRIVACY_REVIEW_PASSED` | CORE_BLOCKING | personnes | publication de donnée personnelle non revue; fichiers | ajouter un fichier sans décision de confidentialité | faible | conserver, revue externe traçable requise |
| `CLAIM_CLASS_DECLARED` | CORE_BLOCKING | preuves | fait inféré présenté comme observé | changer la classe en `OBSERVED_FACT` | faible | conserver |
| `REDISTRIBUTION_PERMITTED` | CORE_BLOCKING | licences | redistribution interdite ou inconnue | rendre redistribuable une source sans décision | faible | conserver |
| `REPRODUCIBLE_FROM_CLEAN_ENVIRONMENT` | REMOVE | build | build non reproductible; rapport auto-attesté | modifier le rapport produit par le build | élevé | déplacer en CI, où deux builds sont réellement comparés |
| `V15_IMMUTABILITY_VERIFIED` | REMOVE | archives | altération du snapshot historique V15 | modifier un fichier archivé | moyen | remplacer par test d'archive/checksums, hors publication courante |

## Registre cible

Le registre actif contient donc les gates CORE et les gates DOMAIN dont le domaine est publié. Les deux contrôles `REMOVE` deviennent respectivement une preuve CI et un test d'archive. `DENOMINATOR_TYPED` est absorbé par le contrôle d'univers. `EVIDENCE_BUNDLE_VERIFIED` disparaît lorsque le manifeste compact vérifie les fichiers et les empreintes logiques des tables.

Chaque implémentation exposera la même interface minimale :

```text
Gate.evaluate(package) -> GateResult
```

avec un identifiant, une classe, un domaine, les tables et sources requises, les preuves produites et le caractère bloquant ou conditionnel. Le registre ne contient aucune logique métier et les modules de gates ne s'importent pas mutuellement.
