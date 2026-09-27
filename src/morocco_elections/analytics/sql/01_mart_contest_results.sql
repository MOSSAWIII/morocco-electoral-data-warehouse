CREATE TABLE mart_contest_results AS
SELECT r.analytical_result_id, r.election_id, r.ballot_type, r.contest_id,
       r.geo_id, r.party_id, r.source_id, r.votes, r.seats,
       r.vote_share_ratio, r.rank, r.winner_flag, r.seat_share_ratio,
       r.previous_vote_share_ratio, r.swing_ratio, r.vote_change, r.seat_change,
       CASE WHEN r.vote_share_ratio IS NOT NULL THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
       CASE WHEN r.vote_share_ratio IS NULL
            THEN 'Vote-share denominator is not identified for this source.' END AS metric_status_reason,
       CASE WHEN r.analytical_readiness_level = 'SOURCE_INTERNAL_COMPLETE'
            THEN 'SOURCE_DISTRIBUTION_NORMALIZED' ELSE 'OBSERVED' END AS distribution_status,
       p.identity_status, 'OBSERVED' AS fact_status, upper(r.quality_status) AS quality_status,
       'UNKNOWN' AS longitudinal_compatibility_status, r.limitations
FROM canonical.analytics_party_results r
JOIN canonical.bridge_party_identity p USING (analytical_result_id, party_id, source_id)
ORDER BY r.analytical_result_id;
