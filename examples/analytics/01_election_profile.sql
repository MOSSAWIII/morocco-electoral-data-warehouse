-- Election profile. Scope: observed canonical results; limitations are retained per row.
SELECT election_id, ballot_type, count(DISTINCT contest_id) AS observed_contests,
       count(DISTINCT party_id) AS observed_parties, sum(votes) AS observed_votes,
       string_agg(DISTINCT source_id, ',' ORDER BY source_id) AS source_ids,
       'Observed results; official-universe exhaustiveness is not inferred.' AS limitations
FROM mart_contest_results
WHERE election_id = 'COMM2021'
GROUP BY election_id, ballot_type
ORDER BY ballot_type;
