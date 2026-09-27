# Analytical data contract

## Marts and keys

| Mart | Grain | Key |
|---|---|---|
| `mart_contest_results` | result × contest × ballot | `analytical_result_id` |
| `mart_contest_competitiveness` | contest × election × ballot | `contest_id, election_id, ballot_type` |
| `mart_party_performance` | party × election × ballot | `party_performance_id` |
| `mart_geography_profile` | geography × election × ballot | `geography_profile_id` |
| `mart_parliamentary_activity` | person × party × legislature × period × type | `parliamentary_activity_id` |

Every column is materialized in `analytics_column_catalog` with its DuckDB type, unit, definition, nullability, calculation method, associated status, source, and limitation. `analytics_table_catalog` records dependencies and grains. `analytics_join_contracts` declares the cross-mart demonstration join as many-to-one on `contest_id, election_id, ballot_type`.

Ratios tagged `ratio_0_1` must be null or within 0–1. Metric status is always `AVAILABLE`, `LIMITED`, or `NOT_AVAILABLE`; the latter two require a reason. A status qualifies only the measures associated with it in `analytics_column_catalog`: for example, `metric_status` in `mart_contest_results` qualifies vote share, while `seat_metric_status` qualifies seats and seat share. Availability, identity, fact provenance, quality, and longitudinal compatibility remain separate columns.

`mart_geography_profile` exposes geographic labels, hierarchy, boundary version and validity. It distinguishes `party_identity_status` from `geography_identity_status` and exposes the official code, matching method, supporting source, and dedicated geographic longitudinal evidence. Nullable hierarchy fields are not inferred when the canonical crosswalk does not identify them. `mart_parliamentary_activity.identity_status` is normalized to `RESOLVED` or `UNRESOLVED`; `identity_method` preserves how the assignment was made. Generic longitudinal fields remain `UNKNOWN` unless dedicated evidence exists.

The reference acceptance profile expects 32,937 contest results, 3,073 available competition rows, four ballot types, 241 unresolved party identities, and 177 distinct unresolved geographies. Every declared profile field is checked; unknown or missing fields fail acceptance. These historical counts are not structural rules.
