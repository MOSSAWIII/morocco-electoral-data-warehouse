# Upstream contract

The source must be a DuckDB exposing these relations:

| Relation | Logical key | Purpose |
|---|---|---|
| `analytics_party_results` | `analytical_result_id` | Result facts and ratios |
| `analytics_contest_metrics` | `contest_id, election_id, ballot_type` | Competition metrics |
| `bridge_party_identity` | `analytical_result_id, party_id, source_id` | Party identity status |
| `bridge_geo_identity` | `geo_id` | Official geographic crosswalk and longitudinal compatibility |
| `analytics_geographies` | `geo_id` | Geographic labels, hierarchy, boundaries, and validity |
| `analytical_parliamentary_trajectory` | `trajectory_id` | Published parliamentary activity |

Required columns, DuckDB types, minimal non-null columns, vocabularies, and cardinalities are declared in `upstream_contract.py` and checked before a destination is created. Ballots are `LOCAL`, `NATIONAL`, `REGIONAL`, or `COMMUNAL`; upstream competition states are `COMPUTED` or `NOT_COMPUTED`. Every result must match exactly one party identity and one geographic identity. Geographic source states are normalized by the analytical mart instead of being confused with party identity.

Errors identify the relation, column/key, failed rule, and observed value. The contract intentionally permits nullable measures when the canonical source lacks a denominator or observation.
