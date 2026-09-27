-- Political concentration by commune.
SELECT c.election_id, r.geo_id, c.contest_id, c.hhi, c.effective_number_of_parties,
       c.concentration_ratio, c.metric_status, c.metric_status_reason,
       string_agg(DISTINCT r.source_id, ',' ORDER BY r.source_id) AS source_ids,
       'Source-distribution metrics; not an official-universe completeness claim.' AS limitations
FROM mart_contest_competitiveness c
JOIN mart_contest_results r USING (contest_id, election_id, ballot_type)
WHERE c.ballot_type = 'COMMUNAL'
GROUP BY ALL
ORDER BY c.election_id, c.hhi DESC NULLS LAST;
