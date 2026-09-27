CREATE TABLE mart_contest_competitiveness AS
SELECT contest_id, election_id, ballot_type, hhi, effective_number_of_parties,
       victory_margin_ratio, concentration_ratio,
       CASE WHEN metric_status = 'COMPUTED' THEN 'AVAILABLE' ELSE 'NOT_AVAILABLE' END AS metric_status,
       CASE WHEN metric_status <> 'COMPUTED'
            THEN coalesce(missing_preconditions, 'Canonical preconditions are not satisfied.') END AS metric_status_reason,
       CASE WHEN party_identities_compatible THEN 'RESOLVED' ELSE 'UNRESOLVED' END AS identity_status,
       'DERIVED' AS fact_status, 'QUALIFIED' AS quality_status,
       'UNKNOWN' AS longitudinal_compatibility_status
FROM canonical.analytics_contest_metrics
ORDER BY election_id, ballot_type, contest_id;
