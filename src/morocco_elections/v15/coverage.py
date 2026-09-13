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
    affiliations = _rows(
        connection,
        """SELECT validity_method, COUNT(*)::BIGINT AS affiliation_periods,
                  COUNT(party_id)::BIGINT AS periods_with_party,
                  COUNT(group_id)::BIGINT AS periods_with_group,
                  (COUNT(*) - COUNT(party_id))::BIGINT AS unresolved_party_periods,
                  (COUNT(*) - COUNT(group_id))::BIGINT AS unresolved_group_periods
           FROM bridge_person_parliamentary_affiliation
           GROUP BY validity_method ORDER BY validity_method""",
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
        analyses.append(
            {
                "analysis_id": analysis["id"],
                "coverage_id": analysis["coverage_id"],
                "numerator": numerator,
                "denominator": denominator,
                "status": "PUBLISHED_SCOPE" if denominator is not None else "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR",
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
        "communal_governance": governance,
        "parliamentary_affiliations": affiliations,
        "parliamentary_question_corpus": {
            "published_questions": connection.execute("SELECT COUNT(*) FROM fact_parliamentary_question").fetchone()[0],
            "official_expected_questions": None,
            "status": "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR",
        },
        "temporal_precision": temporal_precision,
        "analyses": analyses,
    }
