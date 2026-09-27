# Analytical guide

Build and validate a database with:

```powershell
morocco-elections build --source canonical.duckdb --output analytics.duckdb --replace
morocco-elections validate --database analytics.duckdb
```

Use `mart_contest_results` for row-level electoral results, always retaining both `election_id` and `ballot_type`. Use `mart_contest_competitiveness` for HHI, effective party count, concentration, and victory margins. Use `mart_party_performance` for party summaries, `mart_geography_profile` for territorial summaries, and `mart_parliamentary_activity` for descriptive counts derived from published parliamentary documents.

The six examples cover an election profile, party territorial ranking, victory-margin mapping input, communal concentration, ballot comparison, and parliamentary activity. They are in `examples/analytics/01_election_profile.sql` through `06_parliamentary_activity.sql` and execute directly against the output DuckDB.

Interpretation rules:

- `AVAILABLE` means the required inputs for that metric are present, not that the official universe is exhaustive.
- `LIMITED` and `NOT_AVAILABLE` always carry `metric_status_reason`.
- `NULL` is missing or non-calculable and is not zero.
- Ballot types are not pooled implicitly.
- Parliamentary coverage is descriptive because no exhaustive official denominator is claimed.
- Longitudinal fields remain `UNKNOWN` unless separately evidenced.

Every example includes source identifiers or an explicit source scope plus a limitation statement. Consult the in-database catalogs before adding joins or interpreting a derived measure.
