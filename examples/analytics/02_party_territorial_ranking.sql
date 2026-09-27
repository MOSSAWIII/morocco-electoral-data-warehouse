-- Territorial ranking for one party. Scope and ballot remain explicit.
SELECT election_id, ballot_type, party_id, geo_id, sum(votes) AS observed_votes,
       avg(vote_share_ratio) AS mean_vote_share_ratio,
       min(metric_status) AS metric_status,
       string_agg(DISTINCT source_id, ',' ORDER BY source_id) AS source_ids,
       'Observed territorial results for one party; NULL shares remain unavailable.' AS limitations
FROM mart_contest_results
WHERE party_id = 'PJD' AND election_id = 'COMM2021'
GROUP BY election_id, ballot_type, party_id, geo_id
ORDER BY observed_votes DESC NULLS LAST, geo_id;
