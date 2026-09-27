from __future__ import annotations

import argparse
import json
from pathlib import Path

from morocco_elections.analytics.acceptance import DEFAULT_PROFILE, validate_acceptance_profile
from morocco_elections.analytics.build import build_analytics_database
from morocco_elections.analytics.builder import AnalyticsBuildError
from morocco_elections.analytics.paths import DEFAULT_OUTPUT, resolve_source
from morocco_elections.analytics.upstream_contract import UpstreamContractError
from morocco_elections.analytics.validate import validate_analytics_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="morocco-elections")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build all analytical marts from the canonical warehouse")
    build.add_argument("--source", type=Path)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument("--replace", action="store_true")
    validate = commands.add_parser("validate", help="validate analytical keys, ratios and status contracts")
    validate.add_argument("--database", type=Path, default=DEFAULT_OUTPUT)
    acceptance = commands.add_parser("accept", help="validate a database against a pinned snapshot profile")
    acceptance.add_argument("--database", type=Path, default=DEFAULT_OUTPUT)
    acceptance.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build_analytics_database(resolve_source(args.source), args.output, replace=args.replace)
        elif args.command == "validate":
            report = validate_analytics_database(args.database)
        else:
            report = validate_acceptance_profile(args.database, args.profile)
    except (AnalyticsBuildError, FileExistsError, FileNotFoundError, UpstreamContractError) as error:
        report = {"status": "FAIL", "error": str(error)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"BUILT", "PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
