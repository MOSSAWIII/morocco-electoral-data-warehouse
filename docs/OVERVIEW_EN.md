# English project overview

[**Morocco Electoral Data Warehouse — full README (French)**](../README.md)

This repository develops reproducible infrastructure for Morocco's electoral and parliamentary data. The output is a locally queryable DuckDB warehouse backed by provenance, validation rules, source checksums, and documented limits on coverage.

## What the current development snapshot contains

The [main README](../README.md) reports nine elections, 3,715 electoral contests, 10,883 election results, 22,054 communal results, 1,825 territories, 65,748 parliamentary questions and 30,257 answers. These are **observed dataset counts, not a claim of complete official coverage**.

## Why the project matters

Public electoral data can span different formats, territorial boundaries, periods and publication practices. Without traceable source identifiers, explicit definitions and careful missing-data treatment, combining such information risks producing misleading historical comparisons.

The project separates raw evidence, normalization, quality checks, warehouse facts and analytical views. Missing values are not silently recoded as zero; unsupported completeness claims are explicitly avoided.

## Engineering and reproducibility

- Python 3.11 / 3.12 and DuckDB.
- Canonical CLI commands for building, validating, auditing, packaging and checking status.
- Source registry and content checksums.
- CI validation and rebuild checks.
- Documentation of licensing and publication-readiness gates.

For exact commands, use the [main README](../README.md). For domain coverage and limitations consult [product scope](PRODUCT_SCOPE.md) and [analytical guide](ANALYTICAL_GUIDE.md).

**Status:** active project; reproduction and verification must follow the repository's source-access and release-readiness requirements.
