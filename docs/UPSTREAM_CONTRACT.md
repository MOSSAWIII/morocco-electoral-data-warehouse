# Upstream contract

The source must be a DuckDB exposing these relations:

| Relation | Logical key | Purpose |
|---|---|---|
| `analytics_party_results` | `analytical_result_id` | Result facts and ratios |
| `analytics_contest_metrics` | `contest_id, election_id, ballot_type` | Competition metrics |
| `bridge_party_identity` | `analytical_result_id, party_id, source_id` | Party identity status |
| `analytical_parliamentary_trajectory` | `trajectory_id` | Published parliamentary activity |

Required columns, DuckDB types, minimal non-null columns, vocabularies, and cardinalities are declared in `upstream_contract.py` and checked before a destination is created. Ballots are `LOCAL`, `NATIONAL`, `REGIONAL`, or `COMMUNAL`; upstream competition states are `COMPUTED` or `NOT_COMPUTED`; identity states are `RESOLVED` or `UNRESOLVED`.

Errors identify the relation, column/key, failed rule, and observed value. The contract intentionally permits nullable measures when the canonical source lacks a denominator or observation.
