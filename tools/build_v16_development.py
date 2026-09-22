from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morocco_elections.v16.build import build_development_database  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build additive V16 development database from immutable V15")
    parser.add_argument("--seed", type=Path, default=ROOT / "data/exports/open/v15/morocco_elections_v15.duckdb")
    parser.add_argument("--output", type=Path, required=True, help="V16 development database path")
    parser.add_argument("--replace", action="store_true", help="atomically replace an existing V16 output")
    parser.add_argument("--report", type=Path, help="optional compact geographic-parent JSON report")
    parser.add_argument("--reconciliation-report", type=Path, help="optional exhaustive reconciliation JSON report")
    args = parser.parse_args(argv)
    report = build_development_database(
        args.seed,
        args.output,
        legal_seed_path=ROOT / "metadata/v16/legal_regimes.seed.json",
        source_registry_path=ROOT / "metadata/v16/official_source_registry.json",
        evidence_root=ROOT,
        replace_existing=args.replace,
    )
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report["geo_parent_report"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.reconciliation_report is not None:
        args.reconciliation_report.parent.mkdir(parents=True, exist_ok=True)
        args.reconciliation_report.write_text(
            json.dumps(report["reconciliation_report"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
