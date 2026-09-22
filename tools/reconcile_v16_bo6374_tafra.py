from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morocco_elections.v16.bo6374_reconciliation import (  # noqa: E402
    DEFAULT_ARTIFACT_PATH,
    DEFAULT_REPORT_PATH,
    write_reconciliation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile BO 6374 candidates with TAFRA 2015 results and elected members")
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_ARTIFACT_PATH)
    parser.add_argument("--report", type=Path, default=ROOT / DEFAULT_REPORT_PATH)
    args = parser.parse_args(argv)
    payload = write_reconciliation(ROOT, args.output, args.report)
    print(json.dumps(payload["report"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
