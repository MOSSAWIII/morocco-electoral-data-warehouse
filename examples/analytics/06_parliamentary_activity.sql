-- Descriptive parliamentary activity from published documents.
SELECT legislature, question_type, party_id,
       sum(published_question_count) AS published_questions,
       sum(published_response_date_count) AS questions_with_published_response_date,
       avg(published_response_date_ratio) AS mean_published_response_date_ratio,
       CASE WHEN bool_or(metric_status = 'NOT_AVAILABLE') THEN 'NOT_AVAILABLE'
            WHEN bool_or(metric_status = 'LIMITED') THEN 'LIMITED'
            ELSE 'AVAILABLE' END AS metric_status,
       'Canonical parliamentary published documents' AS source_scope,
       'Coverage is descriptive; no official exhaustive document denominator is claimed.' AS limitations
FROM mart_parliamentary_activity
GROUP BY legislature, question_type, party_id
ORDER BY legislature, question_type, published_questions DESC;
