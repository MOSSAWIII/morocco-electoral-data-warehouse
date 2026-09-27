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
            CREATE TABLE bridge_geo_identity (
              geo_id VARCHAR, official_geo_code VARCHAR, matching_method VARCHAR, source_id VARCHAR,
              confidence DOUBLE, valid_from DATE, valid_to DATE, identity_status VARCHAR,
              longitudinally_compatible BOOLEAN
            );
            INSERT INTO bridge_geo_identity VALUES
              ('g1','01.001.01.01','OFFICIAL_IDENTIFIER','geo-s1',1.0,DATE '2015-01-01',NULL,'RESOLVED_OFFICIAL',true),
              ('g2',NULL,'UNRESOLVED','geo-s2',0.0,NULL,NULL,'NOT_APPLICABLE',false),
              ('g3','03.003.03.03','DOCUMENTED_CROSSWALK','geo-s3',0.5,DATE '2021-01-01',NULL,'UNRESOLVED',false),
              ('g4','04.004.04.04','OFFICIAL_IDENTIFIER','geo-s4',1.0,DATE '2015-01-01',NULL,'RESOLVED_OFFICIAL',true);
            CREATE TABLE analytics_geographies (
              geo_id VARCHAR, geo_name VARCHAR, geo_type VARCHAR, region_name VARCHAR,
              province_prefecture VARCHAR, constituency_name VARCHAR, commune_name VARCHAR,
              boundary_version VARCHAR, valid_from DATE, valid_to DATE
            );
            INSERT INTO analytics_geographies VALUES
              ('g1','Geo 1','commune','Region A','Province A',NULL,'Commune 1','2015',DATE '2015-01-01',NULL),
              ('g2','Geo 2','country',NULL,NULL,NULL,NULL,'2021',DATE '2021-01-01',NULL),
              ('g3','Geo 3','region','Region C',NULL,NULL,NULL,'2021',DATE '2021-01-01',NULL),
              ('g4','Geo 4','commune','Region D','Province D',NULL,'Commune 4','2015',DATE '2015-01-01',NULL);
            CREATE TABLE analytical_parliamentary_trajectory (
              trajectory_id VARCHAR, person_id VARCHAR, party_id VARCHAR, legislature VARCHAR,
              period_id VARCHAR, question_type VARCHAR, first_deposit_date DATE, last_deposit_date DATE,
              derivation_status VARCHAR, published_question_count BIGINT, published_response_date_count BIGINT,
              published_response_date_rate_pct DOUBLE, party_assignment_method VARCHAR
            );
            INSERT INTO analytical_parliamentary_trajectory VALUES
              ('t1','person1','PJD','XI','2021-2022','WRITTEN',DATE '2021-01-01',DATE '2022-01-01',
               'DERIVED_FROM_PUBLISHED_QUESTIONS',10,7,70.0,'MANDATE_INTERVAL_AT_DEPOSIT_DATE'),
              ('t2','person2',NULL,'XI','2021-2022','WRITTEN',DATE '2021-02-01',DATE '2022-02-01',
               'LIMITED_SOURCE_COVERAGE',2,1,50.0,'UNRESOLVED_OR_MULTIPLE_WITHIN_TRAJECTORY'),
              ('t3','person3','PJD','XI','2021-2022','WRITTEN',DATE '2021-03-01',DATE '2022-03-01',
               'LIMITED_SOURCE_COVERAGE',3,1,33.0,'MANDATE_INTERVAL_AT_DEPOSIT_DATE');
        """)
    finally:
        connection.close()
    return path
