from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from morocco_elections.warehouse.coverage import DIMENSIONS, UNKNOWN


SEMANTIC_CHECKS = {
    "fact_election_result.election": "SELECT count(*) FROM fact_election_result f LEFT JOIN dim_electoral_contest c USING(contest_id) WHERE c.contest_id IS NULL OR f.election_id IS DISTINCT FROM c.election_id",
    "fact_election_result.geography": "SELECT count(*) FROM fact_election_result f LEFT JOIN dim_electoral_contest c USING(contest_id) WHERE c.contest_id IS NULL OR f.geo_id IS DISTINCT FROM c.geo_id",
    "fact_election_result.historical_regional_parent": "SELECT count(*) FROM fact_election_result f JOIN dim_electoral_contest c USING(contest_id) JOIN dim_geo g ON g.geo_id=f.geo_id WHERE c.region_geo_id IS NOT NULL AND g.geo_type='province_prefecture_snapshot' AND g.parent_geo_id IS NULL",
    "fact_electoral_mobilization.election": "SELECT count(*) FROM fact_electoral_mobilization f LEFT JOIN dim_electoral_contest c USING(contest_id) WHERE c.contest_id IS NULL OR f.election_id IS DISTINCT FROM c.election_id",
    "fact_electoral_mobilization.geography": "SELECT count(*) FROM fact_electoral_mobilization f LEFT JOIN dim_electoral_contest c USING(contest_id) WHERE c.contest_id IS NULL OR f.geo_id IS DISTINCT FROM c.geo_id",
    "fact_communal_election_result.election": "SELECT count(*) FROM fact_communal_election_result f LEFT JOIN dim_electoral_contest c USING(contest_id) WHERE c.contest_id IS NULL OR f.election_id IS DISTINCT FROM c.election_id",
    "fact_communal_election_result.geography": "SELECT count(*) FROM fact_communal_election_result f LEFT JOIN dim_electoral_contest c USING(contest_id) WHERE c.contest_id IS NULL OR f.geo_id IS DISTINCT FROM c.geo_id",
    "fact_communal_election_result.year": "SELECT count(*) FROM fact_communal_election_result f LEFT JOIN dim_election e USING(election_id) WHERE e.election_id IS NULL OR f.year IS DISTINCT FROM e.cycle_year",
}


RECONCILIATION_CHECKS = {
    "party_votes_vs_valid_votes": "WITH p AS (SELECT contest_id, sum(votes) AS recomputed FROM fact_election_result GROUP BY 1) SELECT count(*), count(*) FILTER (WHERE m.valid_votes IS NOT NULL AND p.recomputed IS NOT NULL), count(*) FILTER (WHERE m.valid_votes IS NOT NULL AND p.recomputed IS NOT NULL AND p.recomputed <> m.valid_votes) FROM p LEFT JOIN fact_electoral_mobilization m USING(contest_id)",
    "party_seats_vs_contest_seats": "WITH p AS (SELECT contest_id, sum(seats) AS recomputed FROM fact_election_result GROUP BY 1) SELECT count(*), count(*) FILTER (WHERE m.contest_seats IS NOT NULL AND p.recomputed IS NOT NULL), count(*) FILTER (WHERE m.contest_seats IS NOT NULL AND p.recomputed IS NOT NULL AND p.recomputed <> m.contest_seats) FROM p LEFT JOIN fact_electoral_mobilization m USING(contest_id)",
}


COMMUNAL_COUNCIL_UNIVERSE = {
    "election_id": "COMM2015",
    "official_council_count": 1503,
    "source_id": "MA_DGCL_GUIDE_COLLECTIVITES_TERRITORIALES_2015",
}


def audit_v15_seed(database: Path) -> dict[str, Any]:
    """Read every applicable V15 fact and disclose what cannot yet be validated for WAREHOUSE."""
    connection = duckdb.connect(str(database), read_only=True)
    try:
        semantic = [
            {"check": name, "violations": connection.execute(sql).fetchone()[0]}
            for name, sql in SEMANTIC_CHECKS.items()
        ]
        reconciliation = []
        for name, sql in RECONCILIATION_CHECKS.items():
            eligible, provisional_compared, provisional_mismatches = connection.execute(sql).fetchone()
            reconciliation.append({
                "check": name,
                "eligible": eligible,
                "compared": 0,
                "not_computable": eligible,
                "violations": 0,
                "validation_status": "NOT_COMPUTABLE",
                "reason": "No verified external universe of expected party or seat-allocation identifiers proves that the V15 detail is exhaustive.",
                "official_detail_universe_id": None,
                "provisional_compared": provisional_compared,
                "provisional_mismatches": provisional_mismatches,
            })
        fact_rows = {
            table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result")
        }
        mobilization = connection.execute(
            "SELECT count(*) total, count(voters) voters, count(valid_votes) valid_votes, "
            "count(invalid_votes) invalid_votes, count(blank_votes) blank_votes "
            "FROM fact_electoral_mobilization"
        ).fetchone()
        ballot_fields = dict(zip(("total", "voters", "valid_votes", "invalid_votes", "blank_votes"), mobilization, strict=True))
        communal_grain = connection.execute(
            "SELECT count(*) AS contest_rows, "
            "count(*) FILTER (WHERE g.geo_type='commune') AS ordinary_commune_contests, "
            "count(*) FILTER (WHERE g.geo_type='arrondissement') AS arrondissement_contests, "
            "count(DISTINCT g.parent_geo_id) FILTER (WHERE g.geo_type='arrondissement') AS represented_parent_territories, "
            "count(DISTINCT g.parent_geo_id) FILTER (WHERE g.geo_type='arrondissement' AND p.geo_type='commune') AS represented_parent_communes, "
            "count(DISTINCT g.parent_geo_id) FILTER (WHERE g.geo_type='arrondissement' AND p.geo_type='province_prefecture') AS represented_parent_prefectures, "
            "count(*) FILTER (WHERE g.geo_type='commune') + "
            "count(DISTINCT g.parent_geo_id) FILTER (WHERE g.geo_type='arrondissement' AND p.geo_type='commune') AS implied_council_units, "
            "count(*) FILTER (WHERE g.geo_type='commune') + "
            "count(DISTINCT g.parent_geo_id) FILTER (WHERE g.geo_type='arrondissement') AS unverified_collapsed_units "
            "FROM dim_electoral_contest c JOIN dim_geo g USING(geo_id) "
            "LEFT JOIN dim_geo p ON p.geo_id=g.parent_geo_id WHERE c.election_id=?",
            [COMMUNAL_COUNCIL_UNIVERSE["election_id"]],
        ).fetchone()
        communal_grain_audit = {
            **COMMUNAL_COUNCIL_UNIVERSE,
            **dict(zip(
                (
                    "contest_rows", "ordinary_commune_contests", "arrondissement_contests",
                    "represented_parent_territories", "represented_parent_communes",
                    "represented_parent_prefectures", "implied_council_units", "unverified_collapsed_units",
                ),
                communal_grain,
                strict=True,
            )),
        }
        communal_grain_audit["aggregate_count_matches_official"] = (
            communal_grain_audit["implied_council_units"] == communal_grain_audit["official_council_count"]
            and communal_grain_audit["represented_parent_territories"] == communal_grain_audit["represented_parent_communes"]
        )
        communal_grain_audit["unverified_count_coincidence"] = (
            communal_grain_audit["unverified_collapsed_units"] == communal_grain_audit["official_council_count"]
        )
        communal_grain_audit["arrondissement_parents"] = [
            {"geo_id": row[0], "geo_type": row[1], "geo_name": row[2]}
            for row in connection.execute(
                "SELECT DISTINCT p.geo_id, p.geo_type, p.geo_name "
                "FROM dim_electoral_contest c JOIN dim_geo g USING(geo_id) "
                "LEFT JOIN dim_geo p ON p.geo_id=g.parent_geo_id "
                "WHERE c.election_id=? AND g.geo_type='arrondissement' ORDER BY 1",
                [COMMUNAL_COUNCIL_UNIVERSE["election_id"]],
            ).fetchall()
        ]
        communal_grain_audit["council_grain_materialized"] = (
            communal_grain_audit["contest_rows"] == communal_grain_audit["official_council_count"]
            and communal_grain_audit["arrondissement_contests"] == 0
        )
        coverage = [
            {"coverage_dimension": dimension, "numerator": None, "denominator": None, "status": UNKNOWN}
            for dimension in DIMENSIONS
        ]
        blockers = []
        if not all(ballot_fields[name] == ballot_fields["total"] for name in ("voters", "valid_votes", "invalid_votes", "blank_votes")):
            blockers.append("BALLOT_COMPONENTS_INCOMPLETE")
        if any(row["check"] == "fact_election_result.historical_regional_parent" and row["violations"] for row in semantic):
            blockers.append("HISTORICAL_GEO_PARENTS_MISSING_FROM_V15_SEED")
        if not communal_grain_audit["council_grain_materialized"]:
            blockers.append("COMMUNAL_COUNCIL_GRAIN_NOT_MATERIALIZED")
        if communal_grain_audit["represented_parent_territories"] != communal_grain_audit["represented_parent_communes"]:
            blockers.append("ARRONDISSEMENT_PARENT_NOT_COMMUNE")
        blockers.extend(("OFFICIAL_UNIVERSES_NOT_LOADED", "RESULT_REVISION_HISTORY_NOT_LOADED", "LEGAL_REGIME_EVIDENCE_NOT_NATIVE_TO_V15_SEED"))
        return {
            "source_release": "V15",
            "target_release": "WAREHOUSE",
            "audit_mode": "READ_ONLY_FULL_SEED",
            "fact_rows": fact_rows,
            "semantic_checks": semantic,
            "reconciliation_checks": reconciliation,
            "ballot_field_coverage": ballot_fields,
            "communal_grain_audit": communal_grain_audit,
            "coverage": coverage,
            "publication_status": "NOT_PUBLICATION_READY",
            "blockers": blockers,
        }
    finally:
        connection.close()
