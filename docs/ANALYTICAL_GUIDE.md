# Analytical guide

Build and validate a database with:

```powershell
morocco-elections build --source canonical.duckdb --output analytics.duckdb --replace
morocco-elections validate --database analytics.duckdb
```

Use `mart_contest_results` for row-level electoral results, always retaining both `election_id` and `ballot_type`. Use `mart_contest_competitiveness` for HHI, effective party count, concentration, and victory margins. Use `mart_party_performance` for party summaries, `mart_geography_profile` for territorial summaries, and `mart_parliamentary_activity` for descriptive counts derived from published parliamentary documents.

The six examples cover an election profile, party territorial ranking, victory-margin mapping input, communal concentration, ballot comparison, and parliamentary activity. They are in `examples/analytics/01_election_profile.sql` through `06_parliamentary_activity.sql` and execute directly against the output DuckDB.

Interpretation rules:

- `AVAILABLE` means the required inputs for the associated metric are present, not that every measure on the row is available or that the official universe is exhaustive. Use `seat_metric_status` before interpreting seat totals.
- `LIMITED` and `NOT_AVAILABLE` always carry the matching reason column.
- `NULL` is missing or non-calculable and is not zero.
- Ballot types are not pooled implicitly.
- Parliamentary coverage is descriptive because no exhaustive official denominator is claimed.
- Geographic and party identity are separate in `mart_geography_profile`; unresolved geographic crosswalks must not be treated as official matches.
- Territorial comparisons should retain `boundary_version` and validity dates; a shared label alone does not prove longitudinal comparability.
- Parliamentary `identity_status` states resolution; `identity_method` states how the party was assigned.
- Generic longitudinal fields remain `UNKNOWN` unless separately evidenced.

Every example includes source identifiers or an explicit source scope plus a limitation statement. Consult the in-database catalogs before adding joins or interpreting a derived measure.

## Adversarial development loop

Development starts with a concrete electoral question, not a new permanent artifact. Probe the real marts with a temporary query, then try to invalidate the answer through grain, denominator, coverage, identity, geography, time, and join-cardinality checks. Classify the result as answerable, answerable with a limitation, or blocked by a product gap.

Persist only what survives that attack: a mart or contract correction, a validator rule, an upstream requirement, or a regression test. Delete the temporary query unless it represents a genuinely reusable analytical pattern. This keeps the question workload broad while the permanent product stays small.
