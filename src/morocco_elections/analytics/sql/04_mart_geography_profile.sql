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
       d.geo_name, d.geo_type, d.region_name, d.province_prefecture,
       d.constituency_name, d.commune_name, d.boundary_version,
       d.valid_from AS geography_valid_from, d.valid_to AS geography_valid_to,
       g.official_geo_code,
       CASE g.identity_status
            WHEN 'RESOLVED_OFFICIAL' THEN 'RESOLVED'
            WHEN 'UNRESOLVED' THEN 'UNRESOLVED'
            ELSE 'NOT_APPLICABLE'
       END AS geography_identity_status,
       g.matching_method AS geography_identity_method,
       g.source_id AS geography_identity_source_id,
       CASE WHEN g.longitudinally_compatible THEN 'COMPATIBLE' ELSE 'NOT_COMPATIBLE' END
            AS geography_longitudinal_compatibility_status,
       count(DISTINCT r.contest_id) AS observed_contest_count,
       count(DISTINCT r.party_id) AS observed_party_count,
       sum(r.votes) AS observed_votes, sum(r.seats) AS observed_seats,
       max(c.mean_hhi) AS mean_hhi,
       max(c.mean_victory_margin_ratio) AS mean_victory_margin_ratio,
       CASE WHEN max(c.matched_contest_count) = count(DISTINCT r.contest_id) AND max(c.mean_hhi) IS NOT NULL
            THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
       CASE WHEN max(c.matched_contest_count) <> count(DISTINCT r.contest_id) OR max(c.mean_hhi) IS NULL
            THEN 'At least one contest lacks a normalized source distribution.' END AS metric_status_reason,
       CASE WHEN count(r.seats) = count(*) AND count(r.seat_share_ratio) = count(*)
            THEN 'AVAILABLE' ELSE 'LIMITED' END AS seat_metric_status,
       CASE WHEN count(r.seats) <> count(*) OR count(r.seat_share_ratio) <> count(*)
            THEN 'At least one result lacks a seat count or seat-share denominator; observed_seats may be partial.' END
            AS seat_metric_status_reason,
       CASE WHEN bool_and(r.identity_status = 'RESOLVED') THEN 'RESOLVED' ELSE 'UNRESOLVED' END AS party_identity_status,
       'DERIVED' AS fact_status,
       CASE WHEN bool_and(r.quality_status IN ('VERIFIED', 'QUALIFIED', 'OBSERVED', 'DERIVED'))
            THEN 'QUALIFIED' ELSE 'LIMITED' END AS quality_status,
       string_agg(DISTINCT r.source_id, ',' ORDER BY r.source_id) AS source_ids,
       'Observed contests only; unavailable measures remain NULL.' AS limitations
FROM mart_contest_results r
JOIN competition c USING (election_id, ballot_type, geo_id)
JOIN canonical.bridge_geo_identity g USING (geo_id)
JOIN canonical.analytics_geographies d USING (geo_id)
GROUP BY r.election_id, r.ballot_type, r.geo_id, d.geo_name, d.geo_type, d.region_name,
         d.province_prefecture, d.constituency_name, d.commune_name, d.boundary_version,
         d.valid_from, d.valid_to, g.official_geo_code, g.identity_status,
         g.matching_method, g.source_id, g.longitudinally_compatible
ORDER BY geography_profile_id;
