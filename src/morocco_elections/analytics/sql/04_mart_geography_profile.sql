CREATE TABLE mart_geography_profile AS
WITH contests AS (
    SELECT DISTINCT election_id, ballot_type, geo_id, contest_id
    FROM mart_contest_results
), competition AS (
    SELECT g.election_id, g.ballot_type, g.geo_id,
           count(c.contest_id) AS matched_contest_count,
           avg(c.hhi) AS mean_hhi,
           avg(c.victory_margin_ratio) AS mean_victory_margin_ratio
    FROM contests g
    LEFT JOIN mart_contest_competitiveness c USING (contest_id, election_id, ballot_type)
    GROUP BY g.election_id, g.ballot_type, g.geo_id
)
SELECT concat(r.election_id, ':', r.ballot_type, ':', r.geo_id) AS geography_profile_id,
       r.election_id, r.ballot_type, r.geo_id,
       count(DISTINCT r.contest_id) AS observed_contest_count,
       count(DISTINCT r.party_id) AS observed_party_count,
       sum(r.votes) AS observed_votes, sum(r.seats) AS observed_seats,
       max(c.mean_hhi) AS mean_hhi,
       max(c.mean_victory_margin_ratio) AS mean_victory_margin_ratio,
       CASE WHEN max(c.matched_contest_count) = count(DISTINCT r.contest_id) AND max(c.mean_hhi) IS NOT NULL
            THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
       CASE WHEN max(c.matched_contest_count) <> count(DISTINCT r.contest_id) OR max(c.mean_hhi) IS NULL
            THEN 'At least one contest lacks a normalized source distribution.' END AS metric_status_reason,
       CASE WHEN bool_and(r.identity_status = 'RESOLVED') THEN 'RESOLVED' ELSE 'UNRESOLVED' END AS identity_status,
       'DERIVED' AS fact_status,
       CASE WHEN bool_and(r.quality_status IN ('VERIFIED', 'QUALIFIED', 'OBSERVED', 'DERIVED'))
            THEN 'QUALIFIED' ELSE 'LIMITED' END AS quality_status,
       string_agg(DISTINCT r.source_id, ',' ORDER BY r.source_id) AS source_ids,
       'Observed contests only; unavailable measures remain NULL.' AS limitations
FROM mart_contest_results r
JOIN competition c USING (election_id, ballot_type, geo_id)
GROUP BY r.election_id, r.ballot_type, r.geo_id
ORDER BY geography_profile_id;
