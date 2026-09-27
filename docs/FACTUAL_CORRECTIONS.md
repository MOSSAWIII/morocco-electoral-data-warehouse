# Factual corrections

This branch consumes canonical data read-only and must never repair source facts inside a mart transformation.

When an analytical result reveals a factual issue, open a correction against the canonical `main` product containing: the canonical relation and logical key, source identifier, observed value, proposed value, documentary evidence, reason, and downstream analytical impact. The correction belongs in `main`; this branch consumes it only after a new canonical snapshot is issued.

Changes limited to analytical formulas, status mapping, descriptions, or mart structure may be corrected here when they do not alter canonical facts. Add a regression fixture and document any compatibility effect.
