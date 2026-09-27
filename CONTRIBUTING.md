# Contributing

Contributions must preserve the analytics-only boundary: no source acquisition, canonical warehouse construction, publication gate, or import from `morocco_elections.warehouse` or the removed canonical CLI.

Before submitting a change, run:

```powershell
python -m compileall -q src
ruff check .
pytest
```

Business transformations belong in one ordered file under `src/morocco_elections/analytics/sql/`. Update the corresponding mart and column contracts, structural tests, and documentation in the same change. Never turn missing data into zero, broaden a join without a declared cardinality, or mark longitudinal compatibility as proven without dedicated evidence.

Factual corrections discovered here must be proposed to the canonical `main` product with the affected source, row/key, evidence, expected correction, and analytical impact. Until incorporated into a new canonical snapshot, analytics code must not patch canonical facts locally; see [docs/FACTUAL_CORRECTIONS.md](docs/FACTUAL_CORRECTIONS.md).
