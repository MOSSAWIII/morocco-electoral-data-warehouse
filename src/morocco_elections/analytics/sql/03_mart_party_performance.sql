CREATE TABLE mart_party_performance AS
SELECT concat(election_id, ':', ballot_type, ':', party_id) AS party_performance_id,
       election_id, ballot_type, party_id,
       count(DISTINCT contest_id) AS observed_contest_count,
       sum(votes) AS observed_votes, sum(seats) AS observed_seats,
       avg(vote_share_ratio) AS mean_vote_share_ratio,
       sum(CASE WHEN winner_flag THEN 1 ELSE 0 END) FILTER (WHERE winner_flag IS NOT NULL) AS won_contest_count,
       CASE WHEN count(vote_share_ratio) = count(*) THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
       CASE WHEN count(vote_share_ratio) <> count(*)
            THEN 'At least one contest has no identified vote-share denominator.' END AS metric_status_reason,
       CASE WHEN count(seats) = count(*) AND count(seat_share_ratio) = count(*)
            THEN 'AVAILABLE' ELSE 'LIMITED' END AS seat_metric_status,
       CASE WHEN count(seats) <> count(*) OR count(seat_share_ratio) <> count(*)
            THEN 'At least one result lacks a seat count or seat-share denominator; observed_seats may be partial.' END
            AS seat_metric_status_reason,
       CASE WHEN bool_and(identity_status = 'RESOLVED') THEN 'RESOLVED' ELSE 'UNRESOLVED' END AS identity_status,
       'DERIVED' AS fact_status,
       CASE WHEN bool_and(quality_status IN ('VERIFIED', 'QUALIFIED', 'OBSERVED', 'DERIVED'))
            THEN 'QUALIFIED' ELSE 'LIMITED' END AS quality_status,
       string_agg(DISTINCT source_id, ',' ORDER BY source_id) AS source_ids,
       'Observed contests only; no official-universe exhaustiveness is inferred.' AS limitations
FROM mart_contest_results
GROUP BY election_id, ballot_type, party_id
ORDER BY party_performance_id;
