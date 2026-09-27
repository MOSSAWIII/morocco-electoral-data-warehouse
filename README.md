# Morocco Electoral Analytics

This branch is a standalone analytics product. It reads a compatible canonical Morocco elections DuckDB in `READ_ONLY` mode and creates a separate DuckDB containing five documented marts. It does not acquire sources, construct the canonical warehouse, decide publication readiness, or modify the source database.

## Install and build

Python 3.11 or 3.12 and DuckDB are the only runtime requirements.

```powershell
python -m pip install --requirement requirements-dev.txt
python -m pip install --no-deps --editable .
morocco-elections build --source path/to/morocco_elections.duckdb --output data/analytics.duckdb
morocco-elections validate --database data/analytics.duckdb
```

`--source` takes precedence over `MOROCCO_ELECTIONS_CANONICAL_DB`, followed by the optional conventional local path `data/exports/open/warehouse/morocco_elections.duckdb`. An existing output is protected unless `--replace` is supplied. Replacement occurs atomically only after the new database passes validation.

The product contains:

- `mart_contest_results` — result × contest × ballot;
- `mart_contest_competitiveness` — contest × election × ballot;
- `mart_party_performance` — party × election × ballot;
- `mart_geography_profile` — geography × election × ballot;
- `mart_parliamentary_activity` — person × party × legislature × period × question type.

Six executable examples are under `examples/analytics/`. Every example states its source scope and limitations. See [the analytical guide](docs/ANALYTICAL_GUIDE.md), [upstream contract](docs/UPSTREAM_CONTRACT.md), and [data contract](docs/DATA_CONTRACT.md).

## Quality and limitations

The build checks upstream schemas and keys before materialization, validates every mart key and ratio, restricts operational metric statuses to `AVAILABLE`, `LIMITED`, and `NOT_AVAILABLE`, requires reasons for limited/unavailable metrics, and verifies declared join cardinality. Missing values remain `NULL`; they are never silently converted to zero.

Structural validation works with any compatible snapshot. `morocco-elections accept` is a separate, pinned check for the current reference snapshot. The source SHA-256 is checked before and after every build and only the source file name—not a machine-specific absolute path—is stored in provenance.

## Development

```powershell
python -m compileall -q src
ruff check .
pytest
```

The code is MIT licensed. Documentation is CC BY 4.0. Derived database structure and transformations are offered under ODbL 1.0 subject to source-specific rights described in [ATTRIBUTIONS.md](ATTRIBUTIONS.md) and [LICENSES/DATA.md](LICENSES/DATA.md).
