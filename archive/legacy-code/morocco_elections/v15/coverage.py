from __future__ import annotations

from typing import Any

import duckdb

from morocco_elections.v15.queries import ANALYSES
from morocco_elections.v15.schema import PARTIAL_DATE_POLICIES


def _rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def coverage_matrix(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    registered = _rows(
        connection,
        """SELECT election_id, COUNT(*)::BIGINT AS expected_rows,
                  COUNT(registered_voters)::BIGINT AS published_rows,
                  (COUNT(*) - COUNT(registered_voters))::BIGINT AS unresolved_rows,
                  CASE WHEN COUNT(registered_voters)=COUNT(*) THEN 'COMPLETE_IN_PUBLISHED_SCOPE'
                       WHEN COUNT(registered_voters)=0 THEN 'UNAVAILABLE'
                       ELSE 'PARTIAL' END AS status
           FROM fact_electoral_mobilization GROUP BY election_id ORDER BY election_id""",
    )
    registered_by_territory = _rows(
        connection,
        """SELECT m.election_id, COALESCE(g.region_name, 'UNKNOWN') AS region,
                  COUNT(*)::BIGINT AS expected_rows,
                  COUNT(m.registered_voters)::BIGINT AS published_rows,
                  (COUNT(*) - COUNT(m.registered_voters))::BIGINT AS unresolved_rows,
                  CASE WHEN COUNT(m.registered_voters)=COUNT(*) THEN 'COMPLETE_IN_PUBLISHED_SCOPE'
                       WHEN COUNT(m.registered_voters)=0 THEN 'UNAVAILABLE'
                       ELSE 'PARTIAL' END AS status
           FROM fact_electoral_mobilization m JOIN dim_geo g USING (geo_id)
           GROUP BY m.election_id, COALESCE(g.region_name, 'UNKNOWN')
           ORDER BY m.election_id, region""",
    )
    governance = _rows(
        connection,
        """SELECT year, COUNT(*)::BIGINT AS commune_contests,
                  COUNT(president_party_id)::BIGINT AS resolved_presidencies,
                  (COUNT(*) - COUNT(president_party_id))::BIGINT AS unresolved_presidencies,
                  CASE WHEN COUNT(president_party_id)=COUNT(*) THEN 'COMPLETE_IN_PUBLISHED_SCOPE'
                       WHEN COUNT(president_party_id)=0 THEN 'UNRESOLVED'
                       ELSE 'PARTIAL' END AS status
           FROM fact_commune_election_summary GROUP BY year ORDER BY year""",
    )
    governance_by_territory = _rows(
        connection,
        """SELECT s.year, COALESCE(g.region_name, 'UNKNOWN') AS region,
                  COUNT(*)::BIGINT AS commune_contests,
                  COUNT(s.president_party_id)::BIGINT AS resolved_presidencies,
                  (COUNT(*) - COUNT(s.president_party_id))::BIGINT AS unresolved_presidencies,
                  CASE WHEN COUNT(s.president_party_id)=COUNT(*) THEN 'COMPLETE_IN_PUBLISHED_SCOPE'
                       WHEN COUNT(s.president_party_id)=0 THEN 'UNRESOLVED'
                       ELSE 'PARTIAL' END AS status
           FROM fact_commune_election_summary s JOIN dim_geo g USING (geo_id)
           GROUP BY s.year, COALESCE(g.region_name, 'UNKNOWN') ORDER BY s.year, region""",
    )
    affiliations = _rows(
        connection,
        """WITH classified AS (
               SELECT m.legislature, a.validity_method,
                      CASE WHEN a.source_id IS NOT NULL AND a.valid_from IS NOT NULL AND a.party_id IS NOT NULL
                                THEN 'PROVEN_INTERVAL'
                           WHEN a.source_id IS NOT NULL OR a.valid_from IS NOT NULL OR a.party_id IS NOT NULL
                                THEN 'PARTIAL_INTERVAL'
                           ELSE 'UNKNOWN_INTERVAL' END AS evidence_status,
                      a.party_id, a.group_id
               FROM bridge_person_parliamentary_affiliation a JOIN fact_mandate m USING (mandate_id)
           )
           SELECT legislature, validity_method, evidence_status, COUNT(*)::BIGINT AS affiliation_periods,
                  COUNT(a.party_id)::BIGINT AS periods_with_party,
                  COUNT(a.group_id)::BIGINT AS periods_with_group,
                  (COUNT(*) - COUNT(a.party_id))::BIGINT AS unresolved_party_periods,
                  (COUNT(*) - COUNT(a.group_id))::BIGINT AS unresolved_group_periods
           FROM classified a
           GROUP BY legislature, validity_method, evidence_status
           ORDER BY legislature, validity_method, evidence_status""",
    )
    affiliation_status_totals = {status: 0 for status in ("PROVEN_INTERVAL", "PARTIAL_INTERVAL", "UNKNOWN_INTERVAL")}
    for row in affiliations:
        affiliation_status_totals[row["evidence_status"]] += row["affiliation_periods"]
    questions_by_period = _rows(
        connection,
        """SELECT year(deposit_date)::BIGINT AS calendar_year, question_type,
                  COUNT(*)::BIGINT AS published_questions,
                  NULL::BIGINT AS official_expected_questions,
                  'UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR'::VARCHAR AS status
           FROM fact_parliamentary_question
           GROUP BY year(deposit_date), question_type ORDER BY calendar_year, question_type""",
    )
    analysis_queries = {
        "COMMUNAL_RESULTS_PUBLISHED_SCOPE": (
            "SELECT COUNT(*) FROM fact_communal_election_result", "SELECT COUNT(*) FROM fact_communal_election_result"
        ),
        "COMMUNAL_SUMMARY_PUBLISHED_SCOPE": (
            "SELECT COUNT(*) FROM fact_commune_election_summary", "SELECT COUNT(*) FROM fact_commune_election_summary"
        ),
        "COMMUNAL_CONTROL": (
            "SELECT COUNT(president_party_id) FROM fact_commune_election_summary",
            "SELECT COUNT(*) FROM fact_commune_election_summary",
        ),
        "PARLIAMENTARY_MANDATES_PUBLISHED_SCOPE": (
            "SELECT COUNT(*) FROM fact_mandate", "SELECT COUNT(*) FROM fact_mandate"
        ),
        "PARLIAMENTARY_QUESTIONS": ("SELECT COUNT(*) FROM fact_parliamentary_question", None),
    }
    analyses = []
    for analysis in ANALYSES:
        numerator_sql, denominator_sql = analysis_queries[analysis["coverage_id"]]
        numerator = connection.execute(numerator_sql).fetchone()[0]
        denominator = connection.execute(denominator_sql).fetchone()[0] if denominator_sql else None
        status = (
            "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR"
            if denominator is None
            else "COMPLETE_IN_PUBLISHED_SCOPE" if numerator == denominator else "PARTIAL"
        )
        analyses.append(
            {
                "analysis_id": analysis["id"],
                "coverage_id": analysis["coverage_id"],
                "numerator": numerator,
                "denominator": denominator,
                "status": status,
                "missing_values_are_zero": False,
            }
        )
    temporal_precision = []
    for policy in PARTIAL_DATE_POLICIES:
        table = policy["table_name"]
        column = policy["column"]
        precision = policy["precision_column"]
        counts = {
            (label or "NULL"): count
            for label, count in connection.execute(
                f'SELECT "{precision}", COUNT(*)::BIGINT FROM "{table}" '
                f'GROUP BY "{precision}" ORDER BY "{precision}"'
            ).fetchall()
        }
        temporal_precision.append(
            {
                "table_name": table,
                "column": column,
                "precision_column": precision,
                "raw_column": policy.get("raw_column"),
                "bound_semantics": "LOWER_BOUND" if policy["start_or_end"] == "START" else "UPPER_BOUND",
                "counts": counts,
                "unconvertible_rows": counts.get("UNRESOLVED", 0),
            }
        )
    return {
        "release": "V15",
        "policy": "Missing or unresolved values are never interpreted as zero.",
        "registered_voters": registered,
        "registered_voters_by_territory": registered_by_territory,
        "communal_governance": governance,
        "communal_governance_by_territory": governance_by_territory,
        "parliamentary_affiliations": affiliations,
        "affiliation_evidence_status_definitions": {
            "PROVEN_INTERVAL": "source, lower bound and party affiliation are all published",
            "PARTIAL_INTERVAL": "at least one required proof component is published but the interval is incomplete",
            "UNKNOWN_INTERVAL": "no required proof component is published",
        },
        "affiliation_evidence_status_totals": affiliation_status_totals,
        "parliamentary_question_corpus": {
            "published_questions": connection.execute("SELECT COUNT(*) FROM fact_parliamentary_question").fetchone()[0],
            "official_expected_questions": None,
            "status": "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR",
        },
        "parliamentary_questions_by_period": questions_by_period,
        "temporal_precision": temporal_precision,
        "analyses": analyses,
    }
