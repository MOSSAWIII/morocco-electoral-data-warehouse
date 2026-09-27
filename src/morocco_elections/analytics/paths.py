from __future__ import annotations

import os
from pathlib import Path


SOURCE_ENVIRONMENT_VARIABLE = "MOROCCO_ELECTIONS_CANONICAL_DB"
DEFAULT_OUTPUT = Path("data/analytics/morocco_elections_analytics.duckdb")


def resolve_source(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    configured = os.environ.get(SOURCE_ENVIRONMENT_VARIABLE)
    if configured:
        return Path(configured)
    return Path("data/exports/open/warehouse/morocco_elections.duckdb")
