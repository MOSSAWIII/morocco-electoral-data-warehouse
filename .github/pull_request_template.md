## Purpose

Describe the analytical change, affected mart, grain, and key.

## Contract

- [ ] No canonical warehouse code, source acquisition, or publication gate is introduced.
- [ ] SQL, table/column contracts, join cardinalities, nullability, and limitations agree.
- [ ] Missing observations remain `NULL`, not zero.
- [ ] Any factual correction is routed to canonical `main` with evidence.

## Validation

- [ ] `python -m compileall -q src`
- [ ] `ruff check .`
- [ ] `pytest`
- [ ] A synthetic double build is logically identical.
