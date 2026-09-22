from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morocco_elections.v16.package import package_context, validate_package  # noqa: E402
from morocco_elections.v16.publication import validate_publication  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a V16 package only from its package root")
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--bundle-sha256", help="optional externally pinned evidence-bundle digest")
    parser.add_argument("--require-ready", action="store_true", help="also require all publication gates to pass")
    args = parser.parse_args(argv)
    report = validate_package(args.package_root, expected_bundle_sha256=args.bundle_sha256)
    if report["status"] == "PASS":
        publication = validate_publication(package_context(args.package_root))
        report["publication_evaluation"] = {
            "release_id": publication["release_id"],
            "publication_status": publication["publication_status"],
            "gate_results": publication["gate_results"],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    package_failed = report["status"] != "PASS"
    readiness_failed = args.require_ready and report.get("publication_evaluation", {}).get(
        "publication_status"
    ) != "PUBLICATION_READY"
    return 1 if package_failed or readiness_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
