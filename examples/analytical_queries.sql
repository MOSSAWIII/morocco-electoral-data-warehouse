-- Requêtes de référence pour la couche de consommation canonique.

-- Q01. Liste des élections.
SELECT election_id, election_name, election_date, election_type, contest_count,
       quality_status, source_id
FROM analytics_elections
ORDER BY election_date;

-- Q02. Concours d'une élection.
SELECT contest_id, geo_id, geo_name, geo_type, list_type,
       legal_regime_id, legal_regime_status
FROM analytics_contests
WHERE election_id = 'COMM2015'
ORDER BY geo_name, contest_id;

-- Q03. Résultats d'un territoire (remplacer l'identifiant).
SELECT election_id, contest_id, party_id, votes, seats, source_id,
       coverage_status, validation_status
FROM analytics_party_results
WHERE geo_id = 'MA-01-051-0101'
ORDER BY election_id, votes DESC NULLS LAST;

-- Q04. Résultats d'un parti (remplacer l'identifiant).
SELECT election_id, contest_id, geo_id, votes, seats, quality_status,
       coverage_status
FROM analytics_party_results
WHERE party_id = 'PI'
ORDER BY election_id, geo_id;

-- Q05. Sièges disponibles; les absences restent visibles.
SELECT election_id, contest_id, party_id, seats, availability_status, source_id
FROM analytics_seats
ORDER BY election_id, contest_id, party_id;

-- Q06. Participation disponible et dénominateur utilisé.
SELECT election_id, contest_id, geo_id, registered_voters, voters,
       turnout_rate AS sourced_turnout_rate, recomputed_turnout_rate,
       turnout_denominator, denominator_status
FROM analytics_mobilization
ORDER BY election_id, contest_id;

-- Q07. Hiérarchie territoriale.
SELECT geo_id, geo_name, geo_type, parent_geo_id, verified_parent_geo_ids,
       hcp_link_status
FROM analytics_geographies
ORDER BY geo_type, geo_name;

-- Q08. Population disponible.
SELECT geo_id, geo_name, geo_type, population, census_date,
       population_source_id, hcp_link_status
FROM analytics_geographies
WHERE population IS NOT NULL
ORDER BY population DESC;

-- Q09. Couverture publiée.
SELECT scope_id, acquired, expected, covered, missing, non_comparable,
       redistribution_forbidden, status
FROM analytics_coverage
ORDER BY scope_id;

-- Q10. Données manquantes, sans conversion en zéro.
SELECT election_id, contest_id, geo_id,
       registered_voters IS NULL AS registered_voters_missing,
       voters IS NULL AS voters_missing,
       valid_votes IS NULL AS valid_votes_missing,
       denominator_status
FROM analytics_mobilization
WHERE registered_voters IS NULL OR voters IS NULL OR valid_votes IS NULL
ORDER BY election_id, contest_id;

-- Q11. Contrôles de rapprochement, y compris NOT_COMPUTABLE.
SELECT election_id, contest_id, metric, validation_status,
       not_computable_reason, missing_components, source_id
FROM analytics_quality_controls
ORDER BY election_id, contest_id, metric;

-- Q12. Provenance d'une valeur de résultat.
SELECT r.analytical_result_id, r.election_id, r.contest_id, r.party_id,
       r.votes, r.source_id, s.source_name, s.publisher, s.url, s.license
FROM analytics_party_results r
LEFT JOIN analytics_provenance s USING (source_id)
ORDER BY r.analytical_result_id;

-- Q13. Licences applicables.
SELECT source_id, source_name, publisher, license, status, url
FROM analytics_provenance
ORDER BY source_id;

-- Q14. Les 177 identifiants internes non reliés à l'univers HCP.
SELECT geo_id, geo_name, geo_type, official_geo_code, hcp_link_status,
       population, population_source_id
FROM analytics_geographies
WHERE hcp_link_status = 'UNRESOLVED'
ORDER BY geo_id;

-- Q15. Allocation nationale officielle des sièges en 2021, séparée des faits observés.
SELECT u.election_id, m.expected_id AS party_id,
       m.expected_value AS official_seats, m.unit, u.source_id
FROM coverage_universe u
JOIN coverage_universe_member m USING (universe_id)
WHERE u.universe_id = 'LEG2021:OFFICIAL:NATIONAL_PARTY_SEATS'
ORDER BY official_seats DESC, party_id;
