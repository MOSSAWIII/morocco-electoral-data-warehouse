from __future__ import annotations

import argparse
import json
from pathlib import Path

from morocco_elections.analytics.build import build_analytics_database
from morocco_elections.analytics.validate import validate_analytics_database
from morocco_elections.cli import DEFAULT_PACKAGE, PROJECT_ROOT


DEFAULT_SOURCE = DEFAULT_PACKAGE / "morocco_elections.duckdb"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "exports" / "analytics" / "morocco_elections_analytics.duckdb"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="morocco-elections-analytics")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build all analytical marts from the canonical warehouse")
    build.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument("--replace", action="store_true")
    validate = commands.add_parser("validate", help="validate analytical keys, ratios and status contracts")
    validate.add_argument("--database", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        report = (
            build_analytics_database(args.source, args.output, replace=args.replace)
            if args.command == "build" else validate_analytics_database(args.database)
        )
    except (FileExistsError, FileNotFoundError) as error:
        report = {"status": "FAIL", "error": str(error)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"BUILT", "PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
