from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import duckdb

from morocco_elections.analytics import ANALYTICS_SCHEMA_VERSION


MART_SPECS = {
    "mart_contest_results": ("one party/list result in one contest and ballot", ("analytical_result_id",)),
    "mart_contest_competitiveness": ("one contest and ballot", ("contest_id",)),
    "mart_party_performance": ("one party, election and ballot", ("party_performance_id",)),
    "mart_geography_profile": ("one geography, election and ballot", ("geography_profile_id",)),
    "mart_parliamentary_activity": ("one person, party, legislature, period and question type", ("parliamentary_activity_id",)),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_identity(source: Path) -> tuple[str | None, str | None]:
    manifest = source.parent / "package-manifest.json"
    if not manifest.is_file():
        return None, None
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return str(payload.get("release_id")), _sha256(manifest)


def _create_marts(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE mart_contest_results AS
        SELECT r.analytical_result_id, r.election_id, r.ballot_type, r.contest_id,
               r.geo_id, r.party_id, r.source_id, r.votes, r.seats,
               r.vote_share_ratio, r.rank, r.winner_flag, r.seat_share_ratio,
               r.previous_vote_share_ratio, r.swing_ratio, r.vote_change, r.seat_change,
               CASE WHEN r.vote_share_ratio IS NOT NULL THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
               CASE WHEN r.vote_share_ratio IS NULL
                    THEN 'Vote-share denominator is not identified for this source.' END AS metric_status_reason,
               CASE WHEN r.analytical_readiness_level = 'SOURCE_INTERNAL_COMPLETE'
                    THEN 'SOURCE_DISTRIBUTION_NORMALIZED' ELSE 'OBSERVED' END AS distribution_status,
               p.identity_status, 'OBSERVED' AS fact_status, r.quality_status,
               'UNKNOWN' AS longitudinal_compatibility_status,
               r.limitations
        FROM canonical.analytics_party_results r
        JOIN canonical.bridge_party_identity p USING (analytical_result_id, party_id, source_id)
        ORDER BY r.analytical_result_id
    """)
    connection.execute("""
        CREATE TABLE mart_contest_competitiveness AS
        SELECT contest_id, election_id, ballot_type, hhi, effective_number_of_parties,
               victory_margin_ratio, concentration_ratio,
               CASE WHEN metric_status = 'COMPUTED' THEN 'AVAILABLE' ELSE 'NOT_AVAILABLE' END AS metric_status,
               CASE WHEN metric_status <> 'COMPUTED' THEN missing_preconditions END AS metric_status_reason,
               CASE WHEN party_identities_compatible THEN 'RESOLVED' ELSE 'UNRESOLVED' END AS identity_status,
               'DERIVED' AS fact_status, 'QUALIFIED' AS quality_status,
               'UNKNOWN' AS longitudinal_compatibility_status
        FROM canonical.analytics_contest_metrics
        ORDER BY contest_id
    """)
    connection.execute("""
        CREATE TABLE mart_party_performance AS
        SELECT concat(election_id, ':', ballot_type, ':', party_id) AS party_performance_id,
               election_id, ballot_type, party_id,
               count(DISTINCT contest_id) AS observed_contest_count,
               sum(votes) AS observed_votes, sum(seats) AS observed_seats,
               avg(vote_share_ratio) AS mean_vote_share_ratio,
               sum(CASE WHEN winner_flag THEN 1 ELSE 0 END) FILTER (WHERE winner_flag IS NOT NULL) AS won_contest_count,
               CASE WHEN count(vote_share_ratio) = count(*) THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
               CASE WHEN count(vote_share_ratio) <> count(*)
                    THEN 'At least one contest has no identified vote-share denominator.' END AS metric_status_reason,
               CASE WHEN bool_and(identity_status = 'RESOLVED') THEN 'RESOLVED' ELSE 'UNRESOLVED' END AS identity_status,
               'DERIVED' AS fact_status,
               CASE WHEN bool_and(quality_status IN ('verified', 'qualified')) THEN 'QUALIFIED' ELSE 'LIMITED' END AS quality_status,
               string_agg(DISTINCT source_id, ',' ORDER BY source_id) AS source_ids,
               'Observed contests only; no official-universe exhaustiveness is inferred.' AS limitations
        FROM mart_contest_results
        GROUP BY election_id, ballot_type, party_id
        ORDER BY party_performance_id
    """)
    connection.execute("""
        CREATE TABLE mart_geography_profile AS
        SELECT concat(r.election_id, ':', r.ballot_type, ':', r.geo_id) AS geography_profile_id,
               r.election_id, r.ballot_type, r.geo_id,
               count(DISTINCT r.contest_id) AS observed_contest_count,
               count(DISTINCT r.party_id) AS observed_party_count,
               sum(r.votes) AS observed_votes, sum(r.seats) AS observed_seats,
               avg(c.hhi) AS mean_hhi, avg(c.victory_margin_ratio) AS mean_victory_margin_ratio,
               CASE WHEN count(c.hhi) = count(DISTINCT r.contest_id) THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
               CASE WHEN count(c.hhi) <> count(DISTINCT r.contest_id)
                    THEN 'At least one contest lacks a normalized source distribution.' END AS metric_status_reason,
               CASE WHEN bool_and(r.identity_status = 'RESOLVED') THEN 'RESOLVED' ELSE 'UNRESOLVED' END AS identity_status,
               'DERIVED' AS fact_status,
               CASE WHEN bool_and(r.quality_status IN ('verified', 'qualified')) THEN 'QUALIFIED' ELSE 'LIMITED' END AS quality_status,
               string_agg(DISTINCT r.source_id, ',' ORDER BY r.source_id) AS source_ids,
               'Observed contests only; unavailable measures remain NULL.' AS limitations
        FROM mart_contest_results r
        LEFT JOIN mart_contest_competitiveness c USING (contest_id, election_id, ballot_type)
        GROUP BY r.election_id, r.ballot_type, r.geo_id
        ORDER BY geography_profile_id
    """)
    connection.execute("""
        CREATE TABLE mart_parliamentary_activity AS
        SELECT trajectory_id AS parliamentary_activity_id, person_id, party_id, legislature,
               period_id, question_type, first_deposit_date, last_deposit_date,
               published_question_count, published_response_date_count,
               published_response_date_rate_pct / 100.0 AS published_response_date_ratio,
               CASE WHEN derivation_status = 'DERIVED_FROM_PUBLISHED_QUESTIONS'
                    THEN 'AVAILABLE' ELSE 'LIMITED' END AS metric_status,
               CASE WHEN derivation_status <> 'DERIVED_FROM_PUBLISHED_QUESTIONS'
                    THEN derivation_status END AS metric_status_reason,
               party_assignment_method AS identity_status, derivation_status AS fact_status,
               'QUALIFIED' AS quality_status,
               'Published-document coverage; no official exhaustive denominator is claimed.' AS limitations
        FROM canonical.analytical_parliamentary_trajectory
        ORDER BY trajectory_id
    """)


def _create_catalogs(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("CREATE TABLE analytics_table_catalog (table_name VARCHAR PRIMARY KEY, grain VARCHAR NOT NULL, key_columns VARCHAR NOT NULL)")
    connection.executemany(
        "INSERT INTO analytics_table_catalog VALUES (?, ?, ?)",
        [(name, grain, ",".join(keys)) for name, (grain, keys) in MART_SPECS.items()],
    )
    connection.execute("""
        CREATE TABLE analytics_column_catalog AS
        SELECT c.table_name, c.column_name, c.data_type,
               CASE
                 WHEN c.column_name LIKE '%_ratio' OR c.column_name IN ('hhi', 'concentration_ratio') THEN 'ratio_0_1'
                 WHEN c.column_name LIKE '%_count' OR c.column_name IN ('votes', 'seats', 'observed_votes', 'observed_seats') THEN 'count'
                 WHEN c.column_name LIKE '%_date' THEN 'date'
                 WHEN c.column_name LIKE '%_id' OR c.column_name = 'source_ids' THEN 'identifier'
                 WHEN c.column_name LIKE '%status%' THEN 'status'
                 ELSE 'text_or_category'
               END AS unit,
               replace(c.column_name, '_', ' ') AS meaning
        FROM information_schema.columns c
        JOIN analytics_table_catalog t USING (table_name)
        WHERE c.table_schema = 'main'
        ORDER BY c.table_name, c.ordinal_position
    """)
    connection.execute("""
        CREATE TABLE analytics_join_contracts (
          left_table VARCHAR NOT NULL, right_table VARCHAR NOT NULL,
          join_keys VARCHAR NOT NULL, cardinality VARCHAR NOT NULL,
          PRIMARY KEY (left_table, right_table, join_keys)
        )
    """)
    connection.execute("""
        INSERT INTO analytics_join_contracts VALUES
          ('mart_contest_results', 'mart_contest_competitiveness',
           'contest_id,election_id,ballot_type', 'MANY_TO_ONE')
    """)


def build_analytics_database(source: Path, output: Path, *, replace: bool = False) -> dict[str, object]:
    """Build an autonomous analytics database while opening the canonical source read-only."""
    source = source.resolve()
    output = output.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"canonical warehouse is missing: {source}")
    if output.exists() and not replace:
        raise FileExistsError(f"analytics database already exists: {output}; pass --replace")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".building")
    if temporary.exists():
        temporary.unlink()
    source_sha256 = _sha256(source)
    release_id, manifest_sha256 = _manifest_identity(source)
    build_identity = hashlib.sha256(
        f"{ANALYTICS_SCHEMA_VERSION}:{source_sha256}:{manifest_sha256}".encode()
    ).hexdigest()
    connection = duckdb.connect(str(temporary))
    try:
        quoted_source = str(source).replace("'", "''")
        connection.execute(f"ATTACH '{quoted_source}' AS canonical (READ_ONLY)")
        _create_marts(connection)
        _create_catalogs(connection)
        connection.execute("""
            CREATE TABLE analytics_build_metadata (
              build_id VARCHAR PRIMARY KEY, analytics_schema_version INTEGER NOT NULL,
              source_database_path VARCHAR NOT NULL, source_database_sha256 VARCHAR NOT NULL,
              canonical_snapshot_id VARCHAR, source_manifest_sha256 VARCHAR,
              canonical_access_mode VARCHAR NOT NULL
            )
        """)
        connection.execute(
            "INSERT INTO analytics_build_metadata VALUES (?, ?, ?, ?, ?, ?, 'READ_ONLY')",
            [build_identity, ANALYTICS_SCHEMA_VERSION, str(source), source_sha256, release_id, manifest_sha256],
        )
        connection.execute("DETACH canonical")
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    os.replace(temporary, output)
    return {
        "status": "BUILT", "database": str(output), "build_id": build_identity,
        "source_database_sha256": source_sha256, "source_manifest_sha256": manifest_sha256,
        "marts": list(MART_SPECS),
    }
