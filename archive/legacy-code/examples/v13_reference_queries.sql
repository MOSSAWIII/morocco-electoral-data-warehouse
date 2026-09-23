-- 1. Voix observées par parti, élection et type de liste.
SELECT
    r.election_id,
    c.list_type,
    r.party_id,
    SUM(r.votes) AS observed_votes
FROM fact_election_result AS r
JOIN dim_electoral_contest AS c USING (contest_id)
GROUP BY ALL
ORDER BY r.election_id, c.list_type, observed_votes DESC;

-- 2. Nombre effectif de partis (ENP) dérivé des voix observées par contest.
WITH party_shares AS (
    SELECT
        contest_id,
        votes / NULLIF(SUM(votes) OVER (PARTITION BY contest_id), 0) AS vote_share
    FROM fact_election_result
    WHERE votes IS NOT NULL
)
SELECT
    contest_id,
    1.0 / NULLIF(SUM(vote_share * vote_share), 0) AS enp_observed_votes
FROM party_shares
GROUP BY contest_id
ORDER BY contest_id;

-- 3. Couverture réelle des dénominateurs de mobilisation par élection.
SELECT
    election_id,
    COUNT(*) AS contests,
    COUNT(registered_voters) AS contests_with_registered_voters,
    COUNT(turnout_rate) AS contests_with_turnout_rate,
    COUNT(valid_votes) AS contests_with_valid_votes
FROM fact_electoral_mobilization
GROUP BY election_id
ORDER BY election_id;
