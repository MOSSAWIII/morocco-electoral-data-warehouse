from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morocco_elections.warehouse.package import build_package, package_context  # noqa: E402
from morocco_elections.warehouse.publication import sha256_file, validate_publication  # noqa: E402
from morocco_elections.warehouse.readiness import build_readiness_context  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the closed, package-rooted warehouse development package")
    parser.add_argument("--seed", type=Path, default=ROOT / "data/exports/open/v15/morocco_elections_v15.duckdb")
    parser.add_argument("--package-root", type=Path, default=ROOT / "data/exports/open/warehouse")
    parser.add_argument("--replace", action="store_true", help="atomically replace an existing package after staging validation")
    parser.add_argument(
        "--build-report", type=Path,
        default=ROOT / "data/exports/open/warehouse-build-report.json",
        help="internal, explicitly non-packaged build report",
    )
    parser.add_argument(
        "--gate-report", type=Path,
        default=ROOT / "data/exports/open/warehouse-gate-report.json",
        help="internal, explicitly non-packaged gate-scope report",
    )
    parser.add_argument(
        "--portability-report", type=Path,
        default=ROOT / "data/exports/open/warehouse-portability-report.json",
        help="internal, explicitly non-packaged source-portability and file-review report",
    )
    args = parser.parse_args(argv)
    build_report, validation = build_package(
        args.seed, args.package_root, ROOT, replace_existing=args.replace,
    )
    args.build_report.parent.mkdir(parents=True, exist_ok=True)
    args.build_report.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    package_root = args.package_root.resolve()
    manifest_path = package_root / "package-manifest.json"
    bundle_path = package_root / "evidence-bundle.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    autonomous_context = package_context(package_root)
    context, _ = build_readiness_context(
        package_root / "morocco_elections.duckdb", ROOT, files=manifest["files"],
        package_manifest_path=manifest_path.name, package_manifest_sha256=sha256_file(manifest_path),
        evidence_bundle_path=bundle_path.name, evidence_bundle_sha256=sha256_file(bundle_path),
        v15_manifest_path=ROOT / "metadata/warehouse/v15_immutable_checksums.json",
    )
    context = replace(context, checks=autonomous_context.checks)
    publication = validate_publication(context)
    autonomous_publication = validate_publication(autonomous_context)
    blocked = [
        {
            "gate_id": row["gate_id"], "reason": row["justification"],
            "affected_record_count": len(json.loads(row["affected_records"])),
        }
        for row in publication["gate_results"] if row["gate_status"] == "FAIL"
    ]
    gate_report = {
        "release_id": "development-2026-09-21",
        "publication_status": "NOT_PUBLICATION_READY",
        "scope": "PACKAGE_INTEGRITY_ONLY",
        "evidence_bundle_verified": validation["evidence_bundle_gate"],
        "gate_statuses": [
            {"gate_id": row["gate_id"], "gate_status": row["gate_status"], "justification": row["justification"]}
            for row in publication["gate_results"]
        ],
        "remaining_blocked_gates": blocked,
        "explicitly_excluded_from_public_package": [
            args.build_report.name,
            args.gate_report.name,
            args.portability_report.name,
            *validation["excluded_files"],
        ],
    }
    args.gate_report.write_text(json.dumps(gate_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    license_by_path = {row["relative_path"]: row for row in autonomous_context.checks["license_reviews"]}
    privacy_by_path = {row["relative_path"]: row for row in autonomous_context.checks["privacy_reviews"]}
    claim_by_path = {row["relative_path"]: row for row in autonomous_context.checks["claim_reviews"]}
    repo_gates = {row["gate_id"]: row["gate_status"] for row in publication["gate_results"]}
    autonomous_gates = {row["gate_id"]: row["gate_status"] for row in autonomous_publication["gate_results"]}
    sources = list(autonomous_context.checks["source_portability"])
    portability_report = {
        "release_id": autonomous_context.release_id,
        "as_of_date": str(autonomous_context.as_of_date),
        "public_file_count": len(autonomous_context.files),
        "package_control_file_count": 2,
        "package_control_files": ["package-manifest.json", "evidence-bundle.json"],
        "source_count": len(sources),
        "source_category_counts": validation["source_portability_counts"],
        "license_reviews_present": len(license_by_path),
        "license_reviews_missing": len(autonomous_context.files) - len(license_by_path),
        "privacy_reviews_present": len(privacy_by_path),
        "privacy_reviews_missing": len(autonomous_context.files) - len(privacy_by_path),
        "claim_reviews_present": len(claim_by_path),
        "claim_reviews_missing": len(autonomous_context.files) - len(claim_by_path),
        "repository_dependent_evidence": [],
        "sources": sources,
        "public_file_matrix": [
            {
                **file,
                "license_review": license_by_path[file["relative_path"]],
                "privacy_review": privacy_by_path[file["relative_path"]],
                "claim_and_uncertainty_review": claim_by_path[file["relative_path"]],
                "gate_consumers": [
                    "UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE", "PRIVACY_REVIEW_PASSED",
                    "CLAIM_CLASS_DECLARED", "REDISTRIBUTION_PERMITTED",
                ],
                "portability": "PACKAGE_RELATIVE_PAYLOAD",
            }
            for file in autonomous_context.files
        ],
        "repository_gate_statuses": repo_gates,
        "autonomous_gate_statuses": autonomous_gates,
        "gate_differences": [
            {"gate_id": gate_id, "repository": repo_gates[gate_id], "autonomous": autonomous_gates[gate_id]}
            for gate_id in repo_gates if repo_gates[gate_id] != autonomous_gates[gate_id]
        ],
        "conserved_autonomous_gates": sorted(
            gate_id for gate_id, status in autonomous_gates.items()
            if status == "PASS" and repo_gates.get(gate_id) == status
        ),
    }
    args.portability_report.write_text(
        json.dumps(portability_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "package_root": str(args.package_root.resolve()),
        "package_validation": validation,
        "build_report": str(args.build_report.resolve()),
        "gate_report": str(args.gate_report.resolve()),
        "portability_report": str(args.portability_report.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
