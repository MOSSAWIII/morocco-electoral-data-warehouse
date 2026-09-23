"""Single public command line for the canonical electoral warehouse."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from morocco_elections.warehouse.auditor import main as audit_main
from morocco_elections.warehouse.package import build_package, validate_package
from morocco_elections.warehouse.sources import materialize_declared_sources
from morocco_elections.warehouse.validator import main as validate_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = PROJECT_ROOT / "data" / "exports" / "open" / "warehouse"
DEFAULT_SEED = PROJECT_ROOT / "data" / "seeds" / "historical" / "morocco_elections.duckdb"


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="morocco-elections", description="Morocco Electoral Data Warehouse")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="construire et vérifier le warehouse canonique")
    build.add_argument("--seed", type=Path, default=DEFAULT_SEED, help=argparse.SUPPRESS)
    build.add_argument("--output", type=Path, default=DEFAULT_PACKAGE)
    build.add_argument("--replace", action="store_true")
    validate = commands.add_parser("validate", help="valider le dépôt et le paquet canonique")
    validate.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    validate.add_argument("--repository", action="store_true", help="inclure les sources et preuves locales")
    audit = commands.add_parser("audit", help="auditer les lacunes et gates depuis DuckDB")
    audit.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    audit.add_argument("--summary", action="store_true")
    audit.add_argument("--require-ready", action="store_true")
    audit.add_argument(
        "--historical-seed-diagnostic", action="store_true",
        help="ajouter le diagnostic du seed historique, séparé de l'état courant",
    )
    package = commands.add_parser("package", help="créer une archive du paquet validé")
    package.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    package.add_argument(
        "--output", type=Path,
        default=PROJECT_ROOT / "data" / "exports" / "open" / "releases" / "morocco-electoral-warehouse.zip",
    )
    package.add_argument(
        "--require-ready", action="store_true",
        help="refuser l'archive tant que les gates de publication ne passent pas",
    )
    status = commands.add_parser("status", help="afficher un état compact du produit")
    status.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    return parser


def _build(args: argparse.Namespace) -> int:
    source_report = materialize_declared_sources(PROJECT_ROOT)
    report, validation = build_package(args.seed, args.output, PROJECT_ROOT, replace_existing=args.replace)
    _print({
        "integrity_status": validation["integrity_status"],
        "publication_status": validation["publication_status"],
        "snapshot_id": "development-2026-09-21",
        "package": str(args.output.resolve()), "tables": validation["present_tables"],
        "files": validation["files_included"], "manifest_sha256": validation["manifest_sha256"],
        "proof_index_sha256": validation["bundle_sha256"],
        "materialized_publication_rows": report.get("materialized_publication_rows", {}),
        "source_materialization": source_report,
    })
    return 0 if validation["integrity_status"] == "PASS" else 1


def _validate(args: argparse.Namespace) -> int:
    if args.repository:
        return validate_repository([])
    report = validate_package(args.package)
    _print(report)
    return 0 if report["integrity_status"] == "PASS" else 1


def _audit(args: argparse.Namespace) -> int:
    argv = ["--database", str(args.package / "morocco_elections.duckdb")]
    if args.summary:
        argv.append("--summary")
    if args.require_ready:
        argv.append("--require-ready")
    if args.historical_seed_diagnostic:
        argv.append("--historical-seed-diagnostic")
    return audit_main(argv)


def _package(args: argparse.Namespace) -> int:
    report = validate_package(args.package)
    if report["status"] != "PASS":
        _print(report)
        return 1
    official_release_name = "v1.0.0" in args.output.name.lower()
    if (
        (args.require_ready or official_release_name)
        and report["publication_status"] != "PUBLICATION_READY"
    ):
        _print({
            "integrity_status": report["integrity_status"],
            "publication_status": report["publication_status"],
            "archive": str(args.output.resolve()),
            "created": False,
            "reason": "publication gates are not ready",
        })
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in args.package.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(args.package).as_posix())
    _print({
        "integrity_status": report["integrity_status"],
        "publication_status": report["publication_status"],
        "archive": str(args.output.resolve()), "bytes": args.output.stat().st_size,
    })
    return 0


def _status(args: argparse.Namespace) -> int:
    if not args.package.is_dir():
        _print({
            "integrity_status": "FAIL", "publication_status": "NOT_PUBLICATION_READY",
            "package": str(args.package.resolve()), "reason": "package is missing",
        })
        return 1
    report = validate_package(args.package)
    _print({
        "integrity_status": report["integrity_status"],
        "publication_status": report["publication_status"],
        "package": str(args.package.resolve()),
        "tables": report.get("present_tables", 0), "files": report.get("files_included", 0),
        "failures": len(report.get("failures", [])),
    })
    return 0 if report["integrity_status"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {"build": _build, "validate": _validate, "audit": _audit, "package": _package, "status": _status}[args.command](args)
