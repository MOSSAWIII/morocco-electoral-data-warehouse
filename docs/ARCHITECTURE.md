# Architecture

The package is a one-way consumer of an external canonical DuckDB.

```text
canonical DuckDB (READ_ONLY)
  -> upstream contract validation
  -> ordered SQL materialization in a unique temporary DuckDB
  -> explicit table, column, and join catalogs
  -> structural validation
  -> detach source and atomic destination replacement
```

`paths.py` resolves the input, `upstream_contract.py` checks it, `provenance.py` computes stable identities, `contracts.py` orders marts, `builder.py` orchestrates the transaction, and `validator.py` enforces product invariants. `acceptance.py` deliberately keeps snapshot counts outside generic validation.

Each build uses a unique `.building` file next to the destination. The source is attached with DuckDB `READ_ONLY`, detached before replacement, and hashed before and after. Failure removes the temporary file and leaves any valid destination untouched.
