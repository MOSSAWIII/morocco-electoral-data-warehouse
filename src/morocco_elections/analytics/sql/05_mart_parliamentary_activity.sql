CREATE TABLE mart_parliamentary_activity AS
SELECT trajectory_id AS parliamentary_activity_id, person_id, party_id, legislature,
       period_id, question_type, first_deposit_date, last_deposit_date,
       published_question_count, published_response_date_count,
       published_response_date_rate_pct / 100.0 AS published_response_date_ratio,
       CASE WHEN derivation_status = 'DERIVED_FROM_PUBLISHED_QUESTIONS'
            THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
       CASE WHEN derivation_status <> 'DERIVED_FROM_PUBLISHED_QUESTIONS'
            THEN coalesce(derivation_status, 'No derivation status supplied.') END AS metric_status_reason,
       party_assignment_method AS identity_status, derivation_status AS fact_status,
       'QUALIFIED' AS quality_status, 'UNKNOWN' AS longitudinal_compatibility_status,
       'Published-document coverage; no official exhaustive denominator is claimed.' AS limitations
FROM canonical.analytical_parliamentary_trajectory
ORDER BY trajectory_id;
