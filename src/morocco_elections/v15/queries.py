from __future__ import annotations

from typing import Any


CUBES: tuple[dict[str, Any], ...] = (
    {
        "name": "cube_party_territorial_evolution",
        "status": "AVAILABLE",
        "grain": "region × election year × party",
        "dimensions": ["region_name", "election_year", "party_id"],
        "output_columns": [
            ["region_name", "VARCHAR", True], ["election_year", "BIGINT", True], ["party_id", "VARCHAR", True],
            ["published_votes", "BIGINT", True], ["unweighted_mean_commune_vote_share_pct", "DOUBLE", True],
            ["published_seats", "BIGINT", True], ["commune_party_rows", "BIGINT", True],
        ],
        "measures": [
            {"name": "published_votes", "unit": "votes", "formula": "SUM(votes)", "denominator": "not applicable: additive published vote total"},
            {
                "name": "unweighted_mean_commune_vote_share_pct",
                "unit": "percent_0_100",
                "formula": "AVG(vote_share)",
                "denominator": "commune-party rows with a published vote share; explicitly unweighted",
            },
            {"name": "published_seats", "unit": "seats", "formula": "SUM(seats)", "denominator": "not applicable: additive published seat total"},
            {"name": "commune_party_rows", "unit": "rows", "formula": "COUNT(*)", "denominator": "not applicable: row count"},
        ],
        "view_sql": """CREATE VIEW cube_party_territorial_evolution AS
            SELECT g.region_name, r.year AS election_year, r.party_id,
                   SUM(r.votes)::BIGINT AS published_votes,
                   AVG(r.vote_share) AS unweighted_mean_commune_vote_share_pct,
                   SUM(r.seats)::BIGINT AS published_seats,
                   COUNT(*)::BIGINT AS commune_party_rows
            FROM fact_communal_election_result r
            JOIN dim_geo g USING (geo_id)
            GROUP BY g.region_name, r.year, r.party_id""",
        "reconciliation_sql": """SELECT CASE WHEN
            (SELECT SUM(published_votes) FROM cube_party_territorial_evolution) =
            (SELECT SUM(r.votes) FROM fact_communal_election_result r JOIN dim_geo g USING (geo_id))
            AND (SELECT SUM(commune_party_rows) FROM cube_party_territorial_evolution) =
            (SELECT COUNT(*) FROM fact_communal_election_result r JOIN dim_geo g USING (geo_id))
            THEN 0 ELSE 1 END AS violations""",
    },
    {
        "name": "cube_electoral_competitiveness",
        "status": "AVAILABLE",
        "grain": "commune contest",
        "dimensions": ["contest_id", "geo_id", "election_id", "year", "concentration_band"],
        "output_columns": [
            ["contest_id", "VARCHAR", False], ["geo_id", "VARCHAR", False], ["election_id", "VARCHAR", False],
            ["year", "BIGINT", False], ["hhi", "DOUBLE", True], ["enp", "DOUBLE", True],
            ["victory_margin_votes", "BIGINT", True], ["victory_margin_pp", "DOUBLE", True],
            ["winning_vote_share", "DOUBLE", True], ["concentration_band", "VARCHAR", True],
        ],
        "measures": [
            {"name": "hhi", "unit": "index_0_10000", "formula": "SUM(vote_share_pct²)", "denominator": "published valid party vote shares"},
            {"name": "enp", "unit": "effective_parties", "formula": "10000 / HHI", "denominator": "published valid party vote shares"},
            {"name": "victory_margin_pp", "unit": "percentage_points", "formula": "winner share − runner-up share", "denominator": "published valid party vote shares"},
            {"name": "victory_margin_votes", "unit": "votes", "formula": "winner votes − runner-up votes", "denominator": "published valid party vote totals"},
            {"name": "winning_vote_share", "unit": "percent_0_100", "formula": "published winner vote share", "denominator": "published valid votes for the contest"},
        ],
        "view_sql": """CREATE VIEW cube_electoral_competitiveness AS
            SELECT contest_id, geo_id, election_id, year, hhi, enp,
                   victory_margin_votes, victory_margin_pp, winning_vote_share,
                   CASE WHEN hhi IS NULL THEN 'UNKNOWN'
                        WHEN hhi < 1500 THEN 'LOW_CONCENTRATION'
                        WHEN hhi < 2500 THEN 'MODERATE_CONCENTRATION'
                        ELSE 'HIGH_CONCENTRATION' END AS concentration_band
            FROM fact_commune_election_summary""",
        "reconciliation_sql": """SELECT abs(
            (SELECT COUNT(*) FROM cube_electoral_competitiveness) -
            (SELECT COUNT(*) FROM fact_commune_election_summary)
        ) AS violations""",
    },
    {
        "name": "cube_communal_control",
        "status": "AVAILABLE",
        "grain": "commune contest",
        "dimensions": [
            "contest_id", "geo_id", "election_id", "year", "winner_party_id", "president_party_id",
            "control_change", "result_control_alignment",
        ],
        "output_columns": [
            ["contest_id", "VARCHAR", False], ["geo_id", "VARCHAR", False], ["election_id", "VARCHAR", False],
            ["year", "BIGINT", False], ["winner_party_id", "VARCHAR", True], ["president_party_id", "VARCHAR", True],
            ["control_change", "VARCHAR", True], ["result_control_alignment", "VARCHAR", True],
            ["contest_count", "BIGINT", True],
        ],
        "measures": [
            {"name": "contest_count", "unit": "commune_contests", "formula": "constant 1 per contest-grain row", "denominator": "all published commune contests; unresolved evidence remains a category"},
        ],
        "view_sql": """CREATE VIEW cube_communal_control AS
            SELECT contest_id, geo_id, election_id, year, winner_party_id,
                   president_party_id, control_change,
                   CASE WHEN winner_party_id IS NULL OR president_party_id IS NULL THEN 'UNRESOLVED'
                        WHEN winner_party_id = president_party_id THEN 'ALIGNED'
                        ELSE 'NOT_ALIGNED' END AS result_control_alignment,
                   1::BIGINT AS contest_count
            FROM fact_commune_election_summary""",
        "reconciliation_sql": """SELECT CASE WHEN
            (SELECT COUNT(*) FROM cube_communal_control) = (SELECT COUNT(*) FROM fact_commune_election_summary)
            AND (SELECT SUM(contest_count) FROM cube_communal_control) = (SELECT COUNT(*) FROM fact_commune_election_summary)
            THEN 0 ELSE 1 END AS violations""",
    },
    {
        "name": "cube_mandate_representation",
        "status": "AVAILABLE",
        "grain": "legislature × region × party × gender",
        "dimensions": ["legislature", "region", "party_id", "gender"],
        "output_columns": [
            ["legislature", "VARCHAR", True], ["region", "VARCHAR", True], ["party_id", "VARCHAR", True],
            ["gender", "VARCHAR", True], ["published_mandates", "BIGINT", True],
            ["region_legislature_published_mandates", "BIGINT", True],
            ["share_of_region_legislature_pct", "DOUBLE", True],
        ],
        "measures": [
            {"name": "published_mandates", "unit": "mandates", "formula": "COUNT(mandate_id)", "denominator": "not applicable: group mandate count"},
            {"name": "region_legislature_published_mandates", "unit": "mandates", "formula": "SUM(group mandate counts) over legislature and region", "denominator": "not applicable: exposed denominator count"},
            {
                "name": "share_of_region_legislature_pct",
                "unit": "percent_0_100",
                "formula": "100 × group mandates / region-legislature published mandates",
                "denominator": "all published mandates in the same legislature and region",
            },
        ],
        "view_sql": """CREATE VIEW cube_mandate_representation AS
            WITH grouped AS (
                SELECT legislature, region, party_id, gender, COUNT(*)::BIGINT AS published_mandates
                FROM fact_mandate
                GROUP BY legislature, region, party_id, gender
            )
            SELECT *,
                   SUM(published_mandates) OVER (PARTITION BY legislature, region)::BIGINT AS region_legislature_published_mandates,
                   100.0 * published_mandates /
                       SUM(published_mandates) OVER (PARTITION BY legislature, region) AS share_of_region_legislature_pct
            FROM grouped""",
        "reconciliation_sql": """SELECT CASE WHEN
            (SELECT SUM(published_mandates) FROM cube_mandate_representation) =
            (SELECT COUNT(*) FROM fact_mandate)
            THEN 0 ELSE 1 END AS violations""",
    },
    {
        "name": "cube_parliamentary_publication",
        "status": "AVAILABLE",
        "grain": "calendar year × question type",
        "dimensions": ["calendar_year", "question_type", "coverage_status"],
        "output_columns": [
            ["calendar_year", "BIGINT", True], ["question_type", "VARCHAR", True],
            ["published_question_count", "BIGINT", True], ["published_response_date_count", "BIGINT", True],
            ["published_response_date_rate_pct", "DOUBLE", True], ["coverage_status", "VARCHAR", True],
        ],
        "measures": [
            {"name": "published_question_count", "unit": "questions", "formula": "COUNT(question_id)", "denominator": "questions found in acquired public files"},
            {"name": "published_response_date_count", "unit": "questions", "formula": "COUNT(response_id)", "denominator": "questions found in acquired public files"},
            {"name": "published_response_date_rate_pct", "unit": "percent_0_100", "formula": "100 × response-date count / question count", "denominator": "questions found in acquired public files; not the official expected corpus"},
        ],
        "view_sql": """CREATE VIEW cube_parliamentary_publication AS
            SELECT year(q.deposit_date)::BIGINT AS calendar_year, q.question_type,
                   COUNT(*)::BIGINT AS published_question_count,
                   COUNT(r.response_id)::BIGINT AS published_response_date_count,
                   CASE WHEN COUNT(*) = 0 THEN NULL ELSE 100.0 * COUNT(r.response_id) / COUNT(*) END AS published_response_date_rate_pct,
                   'UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR'::VARCHAR AS coverage_status
            FROM fact_parliamentary_question q
            LEFT JOIN fact_parliamentary_response r USING (question_id)
            GROUP BY year(q.deposit_date), q.question_type""",
        "reconciliation_sql": """SELECT CASE WHEN
            (SELECT SUM(published_question_count) FROM cube_parliamentary_publication) =
            (SELECT COUNT(*) FROM fact_parliamentary_question)
            AND (SELECT SUM(published_response_date_count) FROM cube_parliamentary_publication) =
            (SELECT COUNT(*) FROM fact_parliamentary_response)
            THEN 0 ELSE 1 END AS violations""",
    },
    {"name": "cube_group_member_days", "status": "PLANNED", "reason": "dated parliamentary-group membership source unavailable"},
    {"name": "cube_official_question_coverage", "status": "DERIVABLE", "reason": "requires an official expected-corpus denominator"},
)


ANALYSES: tuple[dict[str, Any], ...] = (
    {
        "id": "territorial_party_evolution",
        "title": "Évolution électorale territoriale des partis",
        "tables": ["cube_party_territorial_evolution", "fact_communal_election_result", "dim_geo"],
        "filters": "années électorales publiées; agrégation région × année × parti; aperçu de 10 lignes",
        "units": {"published_votes": "votes", "unweighted_mean_commune_vote_share_pct": "percent_0_100"},
        "coverage_id": "COMMUNAL_RESULTS_PUBLISHED_SCOPE",
        "limitations": "La moyenne des parts communales est explicitement non pondérée; les cellules absentes ne sont pas imputées à zéro.",
        "sql": "SELECT * FROM cube_party_territorial_evolution ORDER BY region_name, party_id, election_year LIMIT 10",
    },
    {
        "id": "fragmentation_competitiveness",
        "title": "Fragmentation, HHI et compétitivité",
        "tables": ["cube_electoral_competitiveness", "fact_commune_election_summary"],
        "filters": "contests communaux avec métriques publiées; agrégation par année",
        "units": {"mean_hhi": "index_0_10000", "mean_enp": "effective_parties", "mean_margin_pp": "percentage_points"},
        "coverage_id": "COMMUNAL_SUMMARY_PUBLISHED_SCOPE",
        "limitations": "HHI et ENP utilisent uniquement les parts publiées dans le paquet.",
        "sql": "SELECT year, count(*) contests, avg(hhi) mean_hhi, avg(enp) mean_enp, avg(victory_margin_pp) mean_margin_pp FROM cube_electoral_competitiveness GROUP BY year ORDER BY year",
    },
    {
        "id": "results_vs_communal_control",
        "title": "Résultats versus contrôle communal",
        "tables": ["cube_communal_control", "fact_commune_election_summary"],
        "filters": "tous contests communaux; statut UNRESOLVED conservé",
        "units": {"contests": "commune contests"},
        "coverage_id": "COMMUNAL_CONTROL",
        "limitations": "Toute présidence non prouvée reste UNRESOLVED; aucune propagation hors période.",
        "sql": "SELECT year, result_control_alignment, count(*) contests FROM cube_communal_control GROUP BY year, result_control_alignment ORDER BY year, result_control_alignment",
    },
    {
        "id": "mandates_territorial_representation",
        "title": "Mandats et représentation territoriale",
        "tables": ["cube_mandate_representation", "fact_mandate"],
        "filters": "agrégation législature × région × genre; aucun classement individuel",
        "units": {"published_mandates": "mandates"},
        "coverage_id": "PARLIAMENTARY_MANDATES_PUBLISHED_SCOPE",
        "limitations": "Les personnes sont pseudonymisées et les affiliations ambiguës restent NULL.",
        "sql": "SELECT legislature, region, gender, sum(published_mandates)::BIGINT published_mandates FROM cube_mandate_representation GROUP BY legislature, region, gender ORDER BY legislature, region, gender LIMIT 25",
    },
    {
        "id": "published_parliamentary_questions",
        "title": "Questions parlementaires publiées",
        "tables": ["cube_parliamentary_publication", "fact_parliamentary_question", "fact_parliamentary_response"],
        "filters": "année de dépôt × type de question dans les fichiers acquis",
        "units": {"published_question_count": "questions", "published_response_date_rate_pct": "percent_0_100"},
        "coverage_id": "PARLIAMENTARY_QUESTIONS",
        "limitations": "Couverture UNKNOWN sans dénominateur officiel; le taux décrit seulement une date de réponse publiée.",
        "sql": "SELECT * FROM cube_parliamentary_publication ORDER BY calendar_year, question_type",
    },
)


def available_cubes() -> tuple[dict[str, Any], ...]:
    return tuple(cube for cube in CUBES if cube["status"] == "AVAILABLE")


def render_reference_queries() -> str:
    lines = ["-- V15: cinq analyses de référence issues du registre SQL canonique.", ""]
    for index, analysis in enumerate(ANALYSES, start=1):
        lines.extend([f"-- {index}. {analysis['title']}", analysis["sql"] + ";", ""])
    return "\n".join(lines)
