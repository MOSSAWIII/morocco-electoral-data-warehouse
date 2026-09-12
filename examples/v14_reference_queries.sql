-- 1. Volume publié de questions par année et type.
SELECT
    year(deposit_date::DATE) AS deposit_year,
    question_type,
    COUNT(*) AS published_questions
FROM fact_parliamentary_question
GROUP BY ALL
ORDER BY deposit_year, question_type;

-- 2. Taux de réponse publié par période et type, sans supposer l'exhaustivité.
SELECT
    q.legislature,
    q.question_type,
    COUNT(*) AS published_questions,
    COUNT(r.response_id) AS questions_with_published_response_date,
    ROUND(100.0 * COUNT(r.response_id) / COUNT(*), 2) AS published_response_rate_pct
FROM fact_parliamentary_question AS q
LEFT JOIN fact_parliamentary_response AS r USING (question_id)
GROUP BY ALL
ORDER BY q.legislature, q.question_type;

-- 3. Trajectoires dérivées uniquement lorsque person_id est raccordé exactement.
SELECT
    person_id,
    legislature,
    period_id,
    question_type,
    question_count,
    answered_question_count,
    response_rate_pct
FROM analytical_parliamentary_trajectory
ORDER BY question_count DESC, person_id, legislature, period_id, question_type;
