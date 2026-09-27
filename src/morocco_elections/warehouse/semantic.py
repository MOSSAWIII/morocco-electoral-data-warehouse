"""Small, read-only semantic layer for direct DuckDB consumption."""

from __future__ import annotations

from typing import Any

import duckdb


# The logical grain is deliberately explicit for every one of the 45 materialized
# tables.  This registry enriches the generated catalog; it is not another store.
TABLE_GRAINS: dict[str, tuple[str, tuple[str, ...]]] = {
    "analytical_parliamentary_coverage": ("one observed coverage slice", ("coverage_id",)),
    "analytical_parliamentary_trajectory": ("one person, party, legislature, period and question type", ("trajectory_id",)),
    "analytical_person_period_exposure": ("one person, period and question type", ("person_period_exposure_id",)),
    "bridge_contest_legal_regime": ("one applicable legal regime per contest", ("contest_id", "legal_regime_id")),
    "bridge_election_legal_regime": ("one applicable legal regime per election", ("election_id", "legal_regime_id")),
    "bridge_geo_official_identifier": ("one reviewed geography identifier crosswalk", ("crosswalk_id",)),
    "bridge_geo_parent": ("one dated reviewed parent relation", ("relation_id",)),
    "bridge_person_parliamentary_affiliation": ("one dated mandate affiliation", ("affiliation_id",)),
    "bridge_question_author": ("one question-author link", ("question_author_id",)),
    "bridge_question_source": ("one question-source link", ("question_source_id",)),
    "coverage_universe": ("one externally defined coverage universe", ("universe_id",)),
    "coverage_universe_member": ("one expected identifier in an external universe", ("universe_id", "expected_id")),
    "data_dictionary": ("one documented metric", ("metric_id",)),
    "dim_election": ("one election", ("election_id",)),
    "dim_electoral_contest": ("one territorial electoral contest", ("contest_id",)),
    "dim_geo": ("one internal geography identity", ("geo_id",)),
    "dim_indicator": ("one indicator definition", ("indicator_id",)),
    "dim_institution": ("one public institution", ("institution_id",)),
    "dim_legal_regime": ("one legal regime", ("legal_regime_id",)),
    "dim_legislature": ("one parliamentary legislature", ("legislature_id",)),
    "dim_parliamentary_group": ("one parliamentary group in a legislature", ("group_id",)),
    "dim_parliamentary_period": ("one parliamentary period", ("period_id",)),
    "dim_parliamentary_source": ("one parliamentary source file", ("parliamentary_source_id",)),
    "dim_parliamentary_source_author": ("one source-scoped author identity", ("author_source_id",)),
    "dim_parliamentary_subject": ("one normalized parliamentary subject", ("subject_id",)),
    "dim_party": ("one party identity", ("party_id",)),
    "dim_person_public": ("one public person identity", ("person_id",)),
    "dim_time": ("one time identity", ("time_id",)),
    "fact_communal_election_result": ("one party result per communal contest", ("contest_id", "party_id")),
    "fact_commune_election_summary": ("one descriptive summary per communal contest", ("contest_id",)),
    "fact_election_result": ("one sourced party result", ("result_id",)),
    "fact_electoral_mobilization": ("one mobilization record per contest", ("contest_id",)),
    "fact_geo_population": ("one official geography population observation", ("geo_population_id",)),
    "fact_mandate": ("one public mandate", ("mandate_id",)),
    "fact_observation": ("one indicator observation", ("observation_id",)),
    "fact_parliamentary_question": ("one published parliamentary question", ("question_id",)),
    "fact_parliamentary_response": ("one published parliamentary response", ("response_id",)),
    "fact_result_reconciliation": ("one metric check per contest", ("reconciliation_id",)),
    "parliamentary_outlier_audit": ("one reviewed parliamentary outlier", ("outlier_audit_id",)),
    "publication_file": ("one file in one release", ("release_id", "relative_path")),
    "publication_gate_result": ("one gate result per release", ("release_id", "gate_id")),
    "publication_review": ("one review type per release file", ("release_id", "relative_path", "review_type")),
    "release_coverage_matrix": ("one coverage scope per release", ("release_id", "scope_id")),
    "sources": ("one declared source", ("source_id",)),
    "warehouse_metadata": ("one warehouse snapshot", ("release",)),
}


def table_semantics(name: str, columns: list[str]) -> dict[str, Any]:
    """Return user-facing semantics and authorized direct relations for a table."""
    grain, key = TABLE_GRAINS.get(
        name, ("one physical row (test or extension table)", tuple(columns[:1]))
    )
    if name.startswith("dim_"):
        role, usage = "dimension", "analytical context"
    elif name.startswith("fact_"):
        role, usage = "fact", "analytical measure or validation evidence"
    elif name.startswith("bridge_"):
        role, usage = "bridge", "authorized relationship"
    elif name.startswith("analytical_"):
        role, usage = "derived analytical table", "descriptive analysis"
    elif name.startswith("publication_") or name in {"release_coverage_matrix", "coverage_universe", "coverage_universe_member", "warehouse_metadata"}:
        role, usage = "publication evidence", "quality, coverage or provenance evidence"
    elif name == "sources":
        role, usage = "source registry", "provenance and licensing context"
    else:
        role, usage = "reference or audit", "context or evidence"
    known_limits = "Interpret NULL as unavailable, never as zero. Respect quality and coverage fields."
    if name.startswith("analytical_parliamentary_"):
        known_limits = "Published-document coverage is not an official exhaustive denominator."
    elif name in {"fact_election_result", "fact_communal_election_result", "fact_commune_election_summary"}:
        known_limits = "Observed results are not exhaustive unless a verified external universe says so."
    elif name in {"bridge_geo_official_identifier", "fact_geo_population"}:
        known_limits = "177 internal commune identifiers are not linked to the verified HCP universe."
    elif name == "fact_result_reconciliation":
        known_limits = "NOT_COMPUTABLE is evidence of unavailable inputs and must remain visible."
    targets = {
        "election_id": "dim_election", "contest_id": "dim_electoral_contest",
        "geo_id": "dim_geo", "parent_geo_id": "dim_geo", "region_geo_id": "dim_geo",
        "party_id": "dim_party", "person_id": "dim_person_public",
        "indicator_id": "dim_indicator", "time_id": "dim_time",
        "question_id": "fact_parliamentary_question",
        "period_id": "dim_parliamentary_period", "institution_id": "dim_institution",
        "subject_id": "dim_parliamentary_subject", "legal_regime_id": "dim_legal_regime",
        "group_id": "dim_parliamentary_group", "legislature_id": "dim_legislature",
        "mandate_id": "fact_mandate",
        "author_source_id": "dim_parliamentary_source_author",
        "universe_id": "coverage_universe", "source_id": "sources",
        "parliamentary_source_id": "dim_parliamentary_source",
    }
    relations = sorted(
        column for column in columns
        if column in targets and column not in key and targets[column] != name
    )
    return {
        "role": role,
        "grain": grain,
        "logical_key": list(key),
        "authorized_relation_keys": relations,
        "authorized_relations": [
            {"field": field, "target_table": targets[field]}
            for field in relations
        ],
        "usage": usage,
        "known_limits": known_limits,
    }


VIEW_SEMANTICS: dict[str, dict[str, Any]] = {
    "dim_ballot_type": {"purpose": "Canonical ballot vocabulary.", "grain": "one canonical ballot type", "logical_key": ["ballot_type"], "dependencies": []},
    "bridge_party_identity": {"purpose": "Result-to-party identity decision used to guard sensitive comparisons.", "grain": "one analytical result", "logical_key": ["analytical_result_id"], "dependencies": ["fact_election_result", "fact_communal_election_result", "dim_party"]},
    "bridge_geo_identity": {"purpose": "Explicit geography identity decision with evidence and validity.", "grain": "one internal geography", "logical_key": ["geo_id"], "dependencies": ["dim_geo", "bridge_geo_official_identifier"]},
    "analytics_elections": {"purpose": "Election inventory with contest counts and source provenance.", "grain": "one election", "logical_key": ["election_id"], "dependencies": ["dim_election", "dim_electoral_contest", "sources"]},
    "analytics_contests": {"purpose": "Contest inventory with territory and applicable legal regime.", "grain": "one electoral contest", "logical_key": ["contest_id"], "dependencies": ["dim_electoral_contest", "dim_election", "dim_geo", "bridge_contest_legal_regime", "dim_legal_regime"]},
    "analytics_party_results": {"purpose": "Party/list results at their original contest grain; no completeness is inferred.", "grain": "one party/list result per contest and result family", "logical_key": ["analytical_result_id"], "dependencies": ["fact_election_result", "fact_communal_election_result"]},
    "analytics_seats": {"purpose": "Available seat observations only; missing seats remain NULL and unavailable.", "grain": "one party/list seat observation per contest", "logical_key": ["analytical_result_id"], "dependencies": ["analytics_party_results"]},
    "analytics_mobilization": {"purpose": "Mobilization inputs with an explicitly guarded turnout denominator.", "grain": "one mobilization record per contest", "logical_key": ["contest_id"], "dependencies": ["fact_electoral_mobilization", "dim_election", "dim_geo"]},
    "analytics_geographies": {"purpose": "Geographies, population, hierarchy and HCP linkage status.", "grain": "one internal geography", "logical_key": ["geo_id"], "dependencies": ["dim_geo", "bridge_geo_official_identifier", "fact_geo_population", "bridge_geo_parent"]},
    "analytics_quality_controls": {"purpose": "All reconciliation outcomes, including NOT_COMPUTABLE.", "grain": "one metric check per contest", "logical_key": ["reconciliation_id"], "dependencies": ["fact_result_reconciliation", "dim_electoral_contest", "dim_geo"]},
    "analytics_coverage": {"purpose": "Published coverage scopes and their verified or unknown denominators.", "grain": "one scope per release", "logical_key": ["release_id", "scope_id"], "dependencies": ["release_coverage_matrix"]},
    "analytics_provenance": {"purpose": "Source, licence and coverage metadata.", "grain": "one declared source", "logical_key": ["source_id"], "dependencies": ["sources"]},
    "analytics_national_summary": {"purpose": "Observed national aggregates labelled non-exhaustive without an official denominator.", "grain": "one election and ballot type", "logical_key": ["election_id", "ballot_type"], "dependencies": ["dim_election", "analytics_party_results"]},
    "analytics_contest_metrics": {"purpose": "Guarded concentration metrics with explicit failed preconditions.", "grain": "one contest", "logical_key": ["contest_id"], "dependencies": ["analytics_party_results"]},
}


def create_analytical_views(connection: duckdb.DuckDBPyConnection) -> None:
    """Create a compact semantic layer over canonical tables, without copying facts."""
    required_tables = {
        "dim_election", "dim_electoral_contest", "dim_geo", "sources",
        "bridge_contest_legal_regime", "dim_legal_regime",
        "fact_election_result", "fact_communal_election_result",
        "fact_electoral_mobilization", "bridge_geo_official_identifier",
        "fact_geo_population", "bridge_geo_parent", "fact_result_reconciliation",
        "release_coverage_matrix",
    }
    available = {
        row[0] for row in connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_catalog = current_database() AND table_schema = 'main' "
            "AND table_type = 'BASE TABLE'"
        ).fetchall()
    }
    if not required_tables <= available:
        return
    statements = {
        "dim_ballot_type": """
            SELECT * FROM (VALUES
              ('LOCAL', 'Local legislative ballot'),
              ('NATIONAL', 'National legislative ballot'),
              ('REGIONAL', 'Regional ballot'),
              ('COMMUNAL', 'Communal ballot')
            ) AS t(ballot_type, ballot_type_label)
        """,
        "bridge_geo_identity": """
            SELECT g.geo_id, x.official_geo_code,
                   coalesce(x.matching_method, 'UNRESOLVED') AS matching_method,
                   coalesce(x.source_id, g.source_id) AS source_id,
                   coalesce(x.confidence, 0.0) AS confidence,
                   g.valid_from, g.valid_to,
                   CASE WHEN x.matching_method = 'OFFICIAL_IDENTIFIER' AND x.confidence = 1
                        THEN 'RESOLVED_OFFICIAL'
                        WHEN x.crosswalk_id IS NOT NULL THEN 'UNRESOLVED'
                        ELSE 'NOT_APPLICABLE' END AS identity_status,
                   CASE WHEN x.matching_method = 'OFFICIAL_IDENTIFIER' AND x.confidence = 1
                        THEN TRUE ELSE FALSE END AS longitudinally_compatible
            FROM dim_geo g
            LEFT JOIN bridge_geo_official_identifier x USING (geo_id)
        """,
        "bridge_party_identity": """
            SELECT result_id AS analytical_result_id, party_id, source_id,
                   CASE WHEN identity_review_status = 'manual_review_required'
                        THEN 'REVIEW_REQUIRED' ELSE 'SOURCE_IDENTIFIER' END AS matching_method,
                   CASE WHEN identity_review_status = 'manual_review_required'
                        THEN 'UNRESOLVED' ELSE 'RESOLVED' END AS identity_status,
                   identity_review_status <> 'manual_review_required' AS longitudinally_compatible
            FROM fact_election_result
            UNION ALL
            SELECT concat('COMMUNAL:', contest_id, ':', party_id), party_id, source_id,
                   'SOURCE_IDENTIFIER', 'RESOLVED', TRUE
            FROM fact_communal_election_result
        """,
        "analytics_elections": """
            SELECT e.*, count(DISTINCT c.contest_id) AS contest_count,
                   s.source_name, s.publisher, s.license AS source_license
            FROM dim_election e
            LEFT JOIN dim_electoral_contest c USING (election_id)
            LEFT JOIN sources s ON s.source_id = e.source_id
            GROUP BY ALL
        """,
        "analytics_contests": """
            SELECT c.contest_id, c.election_id, e.election_name, e.election_date,
                   c.geo_id, g.geo_name, g.geo_type, c.region_geo_id, c.list_type,
                   c.identity_review_status, c.source_id, c.evidence_id,
                   b.legal_regime_id, r.legal_basis, r.allocation_formula,
                   r.electoral_quotient_denominator, r.threshold_rule,
                   CASE WHEN b.legal_regime_id IS NULL THEN 'UNRESOLVED' ELSE 'VERIFIED' END AS legal_regime_status
            FROM dim_electoral_contest c
            JOIN dim_election e USING (election_id)
            JOIN dim_geo g USING (geo_id)
            LEFT JOIN bridge_contest_legal_regime b USING (contest_id, election_id)
            LEFT JOIN dim_legal_regime r USING (legal_regime_id)
        """,
        "analytics_party_results": """
            SELECT result_id AS analytical_result_id, 'GENERAL' AS result_family,
                   CASE c.list_type WHEN 'locale' THEN 'LOCAL' WHEN 'nationale' THEN 'NATIONAL'
                        WHEN 'regionale' THEN 'REGIONAL' WHEN 'regional_council' THEN 'REGIONAL' END AS ballot_type,
                   r.contest_id, r.election_id, r.geo_id, r.party_id, r.votes, r.seats,
                   NULL::DOUBLE AS vote_share_ratio, NULL::BIGINT AS rank, NULL::BOOLEAN AS winner_flag,
                   NULL::DOUBLE AS seat_share_ratio, NULL::DOUBLE AS previous_vote_share_ratio,
                   NULL::DOUBLE AS swing_ratio, NULL::BIGINT AS vote_change, NULL::BIGINT AS seat_change,
                   'count' AS unit, NULL::DOUBLE AS denominator_value,
                   'UNIDENTIFIED' AS denominator_status,
                   r.source_id, r.evidence_id, r.quality_status,
                   'UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR' AS coverage_status,
                   r.identity_review_status AS validation_status,
                   'NOT_ESTABLISHED_WITHOUT_VERIFIED_UNIVERSE' AS comparability_status,
                   'OBSERVED' AS analytical_readiness_level,
                   'No identified result-universe denominator; the sourced row is observable only.' AS analytical_readiness_reason,
                   'one party/list result per contest' AS grain,
                   'Observed result; completeness is not inferred.' AS limitations,
                   r.notes
            FROM fact_election_result r JOIN dim_electoral_contest c USING (contest_id, election_id, geo_id)
            UNION ALL
            SELECT concat('COMMUNAL:', contest_id, ':', party_id), 'COMMUNAL',
                   'COMMUNAL', contest_id, election_id, geo_id, party_id, votes, seats,
                   vote_share / 100.0, rank, winner_flag, seat_share / 100.0,
                   previous_vote_share / 100.0, swing_pp / 100.0, vote_change, seat_change,
                   'count', 1.0, 'SOURCE_DISTRIBUTION_TOTAL', source_id, NULL, quality_status,
                   'UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR', fact_status,
                   'NOT_ESTABLISHED_WITHOUT_VERIFIED_UNIVERSE',
                   CASE WHEN abs(sum(vote_share) OVER (PARTITION BY contest_id) - 100.0) <= 0.000001
                        THEN 'SOURCE_INTERNAL_COMPLETE' ELSE 'OBSERVED' END,
                   CASE WHEN abs(sum(vote_share) OVER (PARTITION BY contest_id) - 100.0) <= 0.000001
                        THEN 'Party shares sum to the identified source-distribution denominator (1.0).'
                        ELSE 'The source distribution does not sum to its identified denominator (1.0).' END,
                   'one party/list result per contest',
                   'Observed result; completeness is not inferred.', notes
            FROM fact_communal_election_result
        """,
        "analytics_seats": """
            SELECT analytical_result_id, result_family, contest_id, election_id,
                   geo_id, party_id, seats, 'seats' AS unit, source_id,
                   quality_status, coverage_status,
                   validation_status, comparability_status, grain, limitations,
                   CASE WHEN seats IS NULL THEN 'NOT_AVAILABLE' ELSE 'AVAILABLE' END AS availability_status,
                   'NOT_APPLICABLE_TO_ADDITIVE_COUNT' AS denominator_status
            FROM analytics_party_results
        """,
        "analytics_mobilization": """
            SELECT m.*, e.election_name, g.geo_name, g.geo_type,
                   CASE WHEN registered_voters > 0 AND voters IS NOT NULL
                        THEN 100.0 * voters / registered_voters END AS recomputed_turnout_rate,
                   registered_voters AS turnout_denominator,
                   CASE WHEN registered_voters > 0 AND voters IS NOT NULL
                        THEN 'COMPUTABLE' ELSE 'NOT_COMPUTABLE' END AS denominator_status,
                   'percent of registered voters' AS turnout_unit,
                   'one mobilization record per contest' AS grain,
                   'UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR' AS coverage_status,
                   CASE WHEN registered_voters > 0 AND voters IS NOT NULL
                        THEN 'QUALIFIED' ELSE 'NOT_COMPUTABLE' END AS validation_status,
                   'CONTEST_GRAIN_ONLY' AS comparability_status,
                   'Turnout is recomputed only with nonzero registered voters and an observed voter count.' AS limitations
            FROM fact_electoral_mobilization m
            JOIN dim_election e USING (election_id)
            JOIN dim_geo g USING (geo_id)
        """,
        "analytics_geographies": """
            SELECT g.*, x.official_geo_code, x.matching_method, x.confidence,
                   p.population, p.census_date, p.source_id AS population_source_id,
                   parent.verified_parent_geo_ids,
                   CASE
                     WHEN g.geo_type NOT IN ('commune', 'arrondissement') THEN 'NOT_APPLICABLE'
                     WHEN g.geo_id = concat(
                         'MA-', split_part(x.official_geo_code, '.', 1), '-',
                         split_part(x.official_geo_code, '.', 2), '-',
                         split_part(x.official_geo_code, '.', 3),
                         split_part(x.official_geo_code, '.', 4)
                     ) THEN 'VERIFIED'
                     ELSE 'UNRESOLVED'
                   END AS hcp_link_status,
                   'one internal geography' AS grain,
                   'HCP-dependent comparisons require hcp_link_status = VERIFIED.' AS limitations
            FROM dim_geo g
            LEFT JOIN bridge_geo_official_identifier x USING (geo_id)
            LEFT JOIN fact_geo_population p USING (official_geo_code)
            LEFT JOIN (
                SELECT child_geo_id,
                       string_agg(DISTINCT parent_geo_id, ',' ORDER BY parent_geo_id)
                           AS verified_parent_geo_ids
                FROM bridge_geo_parent
                GROUP BY child_geo_id
            ) parent ON parent.child_geo_id = g.geo_id
        """,
        "analytics_quality_controls": """
            SELECT r.*, c.election_id, c.geo_id, c.list_type,
                   g.geo_name, g.geo_type
            FROM fact_result_reconciliation r
            JOIN dim_electoral_contest c USING (contest_id)
            JOIN dim_geo g USING (geo_id)
        """,
        "analytics_coverage": "SELECT * FROM release_coverage_matrix",
        "analytics_provenance": """
            SELECT source_id, source_name, publisher, source_type, domain, url,
                   coverage_start, coverage_end, geo_granularity,
                   temporal_frequency, format, access_method, license,
                   reliability_score, last_checked, status, notes
            FROM sources
        """,
        "analytics_national_summary": """
            SELECT e.election_id, r.ballot_type, e.election_name, e.election_date,
                   count(DISTINCT r.contest_id) AS observed_contests,
                   count(DISTINCT r.geo_id) AS observed_territories,
                   count(DISTINCT r.party_id) AS observed_parties,
                   count(r.analytical_result_id) AS observed_result_rows,
                   sum(r.votes) AS observed_votes,
                   sum(r.seats) AS observed_seats,
                   'count' AS unit,
                   NULL::BIGINT AS official_denominator,
                   'NOT_COMPUTABLE' AS denominator_status,
                   'UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR' AS coverage_status,
                   'QUALIFIED_DESCRIPTIVE_ONLY' AS validation_status,
                   'NOT_COMPARABLE_AS_EXHAUSTIVE_TOTAL' AS comparability_status,
                   'one election and ballot type' AS grain,
                   string_agg(DISTINCT r.source_id, ',' ORDER BY r.source_id) AS source_ids,
                   'Observed sums are descriptive and are not presented as official exhaustive totals.' AS limitations
            FROM dim_election e
            LEFT JOIN analytics_party_results r USING (election_id)
            GROUP BY e.election_id, r.ballot_type, e.election_name, e.election_date
        """,
        "analytics_contest_metrics": """
            WITH distributions AS (
              SELECT contest_id, election_id, ballot_type, count(*) AS party_count,
                     sum(vote_share_ratio) AS share_sum,
                     sum(vote_share_ratio * vote_share_ratio) AS raw_hhi,
                     max(vote_share_ratio) AS first_share,
                     max(vote_share_ratio) FILTER (WHERE share_rank = 2) AS second_share,
                     bool_and(validation_status <> 'manual_review_required') AS party_identities_compatible,
                     bool_and(g.longitudinally_compatible) AS geography_compatible
              FROM (
                SELECT r.*, dense_rank() OVER (PARTITION BY contest_id ORDER BY vote_share_ratio DESC) AS share_rank
                FROM analytics_party_results r
              ) r
              JOIN bridge_geo_identity g USING (geo_id)
              GROUP BY contest_id, election_id, ballot_type
            )
            SELECT contest_id, election_id, ballot_type,
                   CASE WHEN share_sum IS NOT NULL AND abs(share_sum - 1.0) <= 0.000001 AND party_count >= 2
                        THEN raw_hhi END AS hhi,
                   CASE WHEN share_sum IS NOT NULL AND abs(share_sum - 1.0) <= 0.000001 AND raw_hhi > 0 AND party_count >= 2
                        THEN 1.0 / raw_hhi END AS effective_number_of_parties,
                   CASE WHEN share_sum IS NOT NULL AND abs(share_sum - 1.0) <= 0.000001 AND second_share IS NOT NULL
                        THEN first_share - second_share END AS victory_margin_ratio,
                   CASE WHEN share_sum IS NOT NULL AND abs(share_sum - 1.0) <= 0.000001 AND party_count >= 2
                        THEN first_share END AS concentration_ratio,
                   CASE WHEN share_sum IS NOT NULL AND abs(share_sum - 1.0) <= 0.000001 AND party_count >= 2
                        THEN 'COMPUTED' ELSE 'NOT_COMPUTED' END AS metric_status,
                   CASE WHEN share_sum IS NULL THEN 'VOTE_SHARE_RATIO_MISSING'
                        WHEN abs(share_sum - 1.0) > 0.000001 THEN 'SOURCE_DISTRIBUTION_DENOMINATOR_FAILED'
                        WHEN party_count < 2 THEN 'AT_LEAST_TWO_PARTIES_REQUIRED'
                        WHEN second_share IS NULL THEN 'RUNNER_UP_REQUIRED_FOR_MARGIN'
                        ELSE NULL END AS missing_preconditions,
                   party_identities_compatible, geography_compatible,
                   party_identities_compatible AND geography_compatible AS longitudinally_comparable
            FROM distributions
        """,
    }
    for name, query in statements.items():
        connection.execute(f'CREATE OR REPLACE VIEW "{name}" AS {query}')
