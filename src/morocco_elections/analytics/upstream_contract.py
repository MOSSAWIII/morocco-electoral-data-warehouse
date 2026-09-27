from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class UpstreamRelation:
    columns: dict[str, str]
    key: tuple[str, ...]
    required_non_null: tuple[str, ...]
    vocabularies: dict[str, frozenset[str]]


UPSTREAM_RELATIONS = {
    "analytics_party_results": UpstreamRelation(
        columns={
            "analytical_result_id": "VARCHAR", "election_id": "VARCHAR", "ballot_type": "VARCHAR",
            "contest_id": "VARCHAR", "geo_id": "VARCHAR", "party_id": "VARCHAR", "source_id": "VARCHAR",
            "votes": "BIGINT", "seats": "BIGINT", "vote_share_ratio": "DOUBLE", "rank": "BIGINT",
            "winner_flag": "BOOLEAN", "seat_share_ratio": "DOUBLE", "previous_vote_share_ratio": "DOUBLE",
            "swing_ratio": "DOUBLE", "vote_change": "BIGINT", "seat_change": "BIGINT",
            "quality_status": "VARCHAR", "analytical_readiness_level": "VARCHAR", "limitations": "VARCHAR",
        },
        key=("analytical_result_id",),
        required_non_null=("analytical_result_id", "election_id", "ballot_type", "contest_id", "geo_id", "party_id", "source_id"),
        vocabularies={"ballot_type": frozenset({"LOCAL", "NATIONAL", "REGIONAL", "COMMUNAL"})},
    ),
    "analytics_contest_metrics": UpstreamRelation(
        columns={
            "contest_id": "VARCHAR", "election_id": "VARCHAR", "ballot_type": "VARCHAR", "hhi": "DOUBLE",
            "effective_number_of_parties": "DOUBLE", "victory_margin_ratio": "DOUBLE", "concentration_ratio": "DOUBLE",
            "metric_status": "VARCHAR", "missing_preconditions": "VARCHAR", "party_identities_compatible": "BOOLEAN",
        },
        key=("contest_id", "election_id", "ballot_type"),
        required_non_null=("contest_id", "election_id", "ballot_type", "metric_status"),
        vocabularies={
            "ballot_type": frozenset({"LOCAL", "NATIONAL", "REGIONAL", "COMMUNAL"}),
            "metric_status": frozenset({"COMPUTED", "NOT_COMPUTED"}),
        },
    ),
    "bridge_party_identity": UpstreamRelation(
        columns={"analytical_result_id": "VARCHAR", "party_id": "VARCHAR", "source_id": "VARCHAR", "identity_status": "VARCHAR"},
        key=("analytical_result_id", "party_id", "source_id"),
        required_non_null=("analytical_result_id", "party_id", "source_id", "identity_status"),
        vocabularies={"identity_status": frozenset({"RESOLVED", "UNRESOLVED"})},
    ),
    "bridge_geo_identity": UpstreamRelation(
        columns={
            "geo_id": "VARCHAR", "official_geo_code": "VARCHAR", "matching_method": "VARCHAR",
            "source_id": "VARCHAR", "confidence": "DOUBLE", "valid_from": "DATE", "valid_to": "DATE",
            "identity_status": "VARCHAR", "longitudinally_compatible": "BOOLEAN",
        },
        key=("geo_id",),
        required_non_null=(
            "geo_id", "matching_method", "source_id", "identity_status", "longitudinally_compatible",
        ),
        vocabularies={
            "identity_status": frozenset({"RESOLVED_OFFICIAL", "UNRESOLVED", "NOT_APPLICABLE"}),
        },
    ),
    "analytics_geographies": UpstreamRelation(
        columns={
            "geo_id": "VARCHAR", "geo_name": "VARCHAR", "geo_type": "VARCHAR",
            "region_name": "VARCHAR", "province_prefecture": "VARCHAR",
            "constituency_name": "VARCHAR", "commune_name": "VARCHAR",
            "boundary_version": "VARCHAR", "valid_from": "DATE", "valid_to": "DATE",
        },
        key=("geo_id",),
        required_non_null=("geo_id", "geo_name", "geo_type"),
        vocabularies={},
    ),
    "analytical_parliamentary_trajectory": UpstreamRelation(
        columns={
            "trajectory_id": "VARCHAR", "person_id": "VARCHAR", "party_id": "VARCHAR", "legislature": "VARCHAR",
            "period_id": "VARCHAR", "question_type": "VARCHAR", "first_deposit_date": "DATE", "last_deposit_date": "DATE",
            "derivation_status": "VARCHAR", "published_question_count": "BIGINT", "published_response_date_count": "BIGINT",
            "published_response_date_rate_pct": "DOUBLE", "party_assignment_method": "VARCHAR",
        },
        key=("trajectory_id",),
        required_non_null=(
            "trajectory_id", "person_id", "legislature", "period_id", "question_type", "derivation_status",
            "party_assignment_method",
        ),
        vocabularies={
            "party_assignment_method": frozenset({
                "MANDATE_INTERVAL_AT_DEPOSIT_DATE", "UNRESOLVED_OR_MULTIPLE_WITHIN_TRAJECTORY",
            }),
        },
    ),
}


class UpstreamContractError(ValueError):
    pass


def _fail(relation: str, column: str, rule: str, observed: object) -> None:
    raise UpstreamContractError(f"relation={relation}; column={column}; rule={rule}; observed={observed!r}")


def validate_upstream_database(source: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"canonical warehouse is missing: {source}")
    connection = duckdb.connect(str(source.resolve()), read_only=True)
    try:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        for relation, contract in UPSTREAM_RELATIONS.items():
            if relation not in tables:
                _fail(relation, "*", "RELATION_REQUIRED", "missing")
            observed_columns = {row[0]: row[1].upper() for row in connection.execute(f"DESCRIBE {relation}").fetchall()}
            for column, expected_type in contract.columns.items():
                if column not in observed_columns:
                    _fail(relation, column, "COLUMN_REQUIRED", "missing")
                if observed_columns[column] != expected_type:
                    _fail(relation, column, f"TYPE={expected_type}", observed_columns[column])
            for column in contract.required_non_null:
                count = connection.execute(f'SELECT count(*) FROM "{relation}" WHERE "{column}" IS NULL').fetchone()[0]
                if count:
                    _fail(relation, column, "NOT_NULL", count)
            key_sql = ", ".join(f'"{column}"' for column in contract.key)
            duplicates = connection.execute(
                f'SELECT count(*) FROM (SELECT {key_sql} FROM "{relation}" GROUP BY ALL HAVING count(*) > 1)'
            ).fetchone()[0]
            if duplicates:
                _fail(relation, ",".join(contract.key), "KEY_UNIQUE", duplicates)
            for column, allowed in contract.vocabularies.items():
                placeholders = ", ".join("?" for _ in allowed)
                invalid = connection.execute(
                    f'SELECT "{column}", count(*) FROM "{relation}" '
                    f'WHERE "{column}" IS NOT NULL AND "{column}" NOT IN ({placeholders}) GROUP BY 1 ORDER BY 1',
                    list(sorted(allowed)),
                ).fetchall()
                if invalid:
                    _fail(relation, column, f"VOCABULARY={','.join(sorted(allowed))}", invalid)
        unmatched_results = connection.execute("""
            SELECT count(*)
            FROM analytics_party_results r
            LEFT JOIN bridge_party_identity p USING (analytical_result_id, party_id, source_id)
            WHERE p.analytical_result_id IS NULL
        """).fetchone()[0]
        if unmatched_results:
            _fail("bridge_party_identity", "analytical_result_id,party_id,source_id", "RESULT_COVERAGE_ONE_TO_ONE", unmatched_results)
        orphan_identities = connection.execute("""
            SELECT count(*)
            FROM bridge_party_identity p
            LEFT JOIN analytics_party_results r USING (analytical_result_id, party_id, source_id)
            WHERE r.analytical_result_id IS NULL
        """).fetchone()[0]
        if orphan_identities:
            _fail("bridge_party_identity", "analytical_result_id,party_id,source_id", "NO_ORPHANS", orphan_identities)
        unmatched_geographies = connection.execute("""
            SELECT count(DISTINCT r.geo_id)
            FROM analytics_party_results r
            LEFT JOIN bridge_geo_identity g USING (geo_id)
            WHERE g.geo_id IS NULL
        """).fetchone()[0]
        if unmatched_geographies:
            _fail("bridge_geo_identity", "geo_id", "RESULT_GEOGRAPHY_COVERAGE_ONE_TO_ONE", unmatched_geographies)
        unmatched_geography_dimensions = connection.execute("""
            SELECT count(DISTINCT r.geo_id)
            FROM analytics_party_results r
            LEFT JOIN analytics_geographies g USING (geo_id)
            WHERE g.geo_id IS NULL
        """).fetchone()[0]
        if unmatched_geography_dimensions:
            _fail("analytics_geographies", "geo_id", "RESULT_GEOGRAPHY_COVERAGE_ONE_TO_ONE", unmatched_geography_dimensions)
    finally:
        connection.close()
