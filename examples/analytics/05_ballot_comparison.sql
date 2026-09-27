-- Local, national and regional ballots are compared as separate rows, never pooled.
SELECT election_id, ballot_type, count(DISTINCT contest_id) AS observed_contests,
       sum(votes) AS observed_votes, avg(vote_share_ratio) AS mean_vote_share_ratio,
       string_agg(DISTINCT source_id, ',' ORDER BY source_id) AS source_ids,
       'Ballot-specific observed totals; NULL shares remain unavailable.' AS limitations
FROM mart_contest_results
WHERE ballot_type IN ('LOCAL', 'NATIONAL', 'REGIONAL')
GROUP BY election_id, ballot_type
ORDER BY election_id, ballot_type;
