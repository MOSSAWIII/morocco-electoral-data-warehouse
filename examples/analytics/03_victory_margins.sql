-- Table ready for mapping after joining geo_id through the contest-results mart.
SELECT c.election_id, c.ballot_type, r.geo_id, c.contest_id,
       c.victory_margin_ratio, c.metric_status, c.metric_status_reason,
       string_agg(DISTINCT r.source_id, ',' ORDER BY r.source_id) AS source_ids,
       'Margins exist only for normalized source distributions with a runner-up.' AS limitations
FROM mart_contest_competitiveness c
JOIN mart_contest_results r USING (contest_id, election_id, ballot_type)
WHERE c.election_id = 'COMM2021'
GROUP BY ALL
ORDER BY victory_margin_ratio NULLS LAST;
