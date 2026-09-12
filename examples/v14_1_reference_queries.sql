-- 1. Volume publié, toujours accompagné de la couverture documentaire.
SELECT
    calendar_year,
    question_type,
    SUM(published_question_count) AS published_question_count,
    MIN(coverage_status) AS coverage_status
FROM analytical_parliamentary_coverage
GROUP BY ALL
ORDER BY calendar_year, question_type;

-- 2. Mesure correctement nommée de présence d'une date de réponse publiée.
SELECT
    legislature,
    question_type,
    SUM(published_question_count) AS published_question_count,
    SUM(published_response_date_count) AS published_response_date_count,
    ROUND(
        100.0 * SUM(published_response_date_count) / SUM(published_question_count), 2
    ) AS published_response_date_rate_pct
FROM analytical_parliamentary_trajectory
GROUP BY ALL
ORDER BY legislature, question_type;

-- 3. Intensité sur jours de mandat dans la seule fenêtre effectivement observée.
SELECT
    person_id,
    period_id,
    question_type,
    observed_mandate_days,
    published_question_count,
    published_questions_per_100_observed_mandate_days,
    denominator_status
FROM analytical_person_period_exposure
ORDER BY published_questions_per_100_observed_mandate_days DESC, person_id;
