from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def canonical_database(tmp_path: Path) -> Path:
    path = tmp_path / "canonical.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute("""
            CREATE TABLE analytics_party_results (
              analytical_result_id VARCHAR, election_id VARCHAR, ballot_type VARCHAR, contest_id VARCHAR,
              geo_id VARCHAR, party_id VARCHAR, source_id VARCHAR, votes BIGINT, seats BIGINT,
              vote_share_ratio DOUBLE, rank BIGINT, winner_flag BOOLEAN, seat_share_ratio DOUBLE,
              previous_vote_share_ratio DOUBLE, swing_ratio DOUBLE, vote_change BIGINT, seat_change BIGINT,
              quality_status VARCHAR, analytical_readiness_level VARCHAR, limitations VARCHAR
            );
            INSERT INTO analytics_party_results VALUES
              ('r1','COMM2021','LOCAL','c1','g1','PJD','s1',60,2,.6,1,true,.667,.5,.1,10,1,'verified','SOURCE_INTERNAL_COMPLETE',NULL),
              ('r2','COMM2021','LOCAL','c1','g1','PAM','s1',40,1,.4,2,false,.333,.3,.1,10,0,'verified','SOURCE_INTERNAL_COMPLETE',NULL),
              ('r3','LEG2021','NATIONAL','c2','g2','PJD','s2',100,3,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'observed','OBSERVED','No denominator'),
              ('r4','LEG2021','REGIONAL','c3','g3','RNI','s3',80,2,.8,1,true,1,NULL,NULL,NULL,NULL,'derived','SOURCE_INTERNAL_COMPLETE',NULL),
              ('r5','COMM2015','COMMUNAL','c4','g4','PAM','s4',30,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'observed','OBSERVED','Incomplete distribution');
            CREATE TABLE analytics_contest_metrics (
              contest_id VARCHAR, election_id VARCHAR, ballot_type VARCHAR, hhi DOUBLE,
              effective_number_of_parties DOUBLE, victory_margin_ratio DOUBLE, concentration_ratio DOUBLE,
              metric_status VARCHAR, missing_preconditions VARCHAR, party_identities_compatible BOOLEAN
            );
            INSERT INTO analytics_contest_metrics VALUES
              ('c1','COMM2021','LOCAL',.52,1.923,.2,1.0,'COMPUTED',NULL,true),
              ('c2','LEG2021','NATIONAL',NULL,NULL,NULL,NULL,'NOT_COMPUTED','No normalized distribution',false),
              ('c3','LEG2021','REGIONAL',.64,1.562,.6,.8,'COMPUTED',NULL,true),
              ('c4','COMM2015','COMMUNAL',NULL,NULL,NULL,NULL,'NOT_COMPUTED','Incomplete distribution',true);
            CREATE TABLE bridge_party_identity (
              analytical_result_id VARCHAR, party_id VARCHAR, source_id VARCHAR, identity_status VARCHAR
            );
            INSERT INTO bridge_party_identity VALUES
              ('r1','PJD','s1','RESOLVED'), ('r2','PAM','s1','RESOLVED'),
              ('r3','PJD','s2','UNRESOLVED'), ('r4','RNI','s3','RESOLVED'), ('r5','PAM','s4','RESOLVED');
            CREATE TABLE analytical_parliamentary_trajectory (
              trajectory_id VARCHAR, person_id VARCHAR, party_id VARCHAR, legislature VARCHAR,
              period_id VARCHAR, question_type VARCHAR, first_deposit_date DATE, last_deposit_date DATE,
              derivation_status VARCHAR, published_question_count BIGINT, published_response_date_count BIGINT,
              published_response_date_rate_pct DOUBLE, party_assignment_method VARCHAR
            );
            INSERT INTO analytical_parliamentary_trajectory VALUES
              ('t1','person1','PJD','XI','2021-2022','WRITTEN',DATE '2021-01-01',DATE '2022-01-01',
               'DERIVED_FROM_PUBLISHED_QUESTIONS',10,7,70.0,'RESOLVED');
        """)
    finally:
        connection.close()
    return path
