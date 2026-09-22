"""Single public command line for the canonical electoral warehouse."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from morocco_elections.warehouse.auditor import main as audit_main
from morocco_elections.warehouse.package import build_package, validate_package
from morocco_elections.warehouse.sources import materialize_declared_sources, materialize_seed_database
from morocco_elections.warehouse.validator import main as validate_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = PROJECT_ROOT / "data" / "exports" / "open" / "warehouse"
DEFAULT_SEED = PROJECT_ROOT / "data" / "exports" / "open" / "v15" / "morocco_elections_v15.duckdb"


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
    package = commands.add_parser("package", help="créer une archive du paquet validé")
    package.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    package.add_argument(
        "--output", type=Path,
        default=PROJECT_ROOT / "data" / "exports" / "open" / "releases" / "morocco-electoral-warehouse.zip",
    )
    status = commands.add_parser("status", help="afficher un état compact du produit")
    status.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    return parser


def _build(args: argparse.Namespace) -> int:
    source_report = materialize_declared_sources(PROJECT_ROOT)
    if not args.seed.is_file():
        materialize_seed_database(PROJECT_ROOT, args.seed)
    report, validation = build_package(args.seed, args.output, PROJECT_ROOT, replace_existing=args.replace)
    _print({
        "status": validation["status"], "snapshot_id": "development-2026-09-21",
        "package": str(args.output.resolve()), "tables": validation["present_tables"],
        "files": validation["files_included"], "manifest_sha256": validation["manifest_sha256"],
        "proof_index_sha256": validation["bundle_sha256"],
        "materialized_publication_rows": report.get("materialized_publication_rows", {}),
        "source_materialization": source_report,
    })
    return 0 if validation["status"] == "PASS" else 1


def _validate(args: argparse.Namespace) -> int:
    if args.repository:
        return validate_repository([])
    report = validate_package(args.package)
    _print(report)
    return 0 if report["status"] == "PASS" else 1


def _audit(args: argparse.Namespace) -> int:
    argv = ["--database", str(args.package / "morocco_elections.duckdb")]
    if args.summary:
        argv.append("--summary")
    if args.require_ready:
        argv.append("--require-ready")
    return audit_main(argv)


def _package(args: argparse.Namespace) -> int:
    report = validate_package(args.package)
    if report["status"] != "PASS":
        _print(report)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in args.package.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(args.package).as_posix())
    _print({"status": "PASS", "archive": str(args.output.resolve()), "bytes": args.output.stat().st_size})
    return 0


def _status(args: argparse.Namespace) -> int:
    if not args.package.is_dir():
        _print({"status": "MISSING", "package": str(args.package.resolve())})
        return 1
    report = validate_package(args.package)
    _print({
        "status": report["status"], "package": str(args.package.resolve()),
        "tables": report.get("present_tables", 0), "files": report.get("files_included", 0),
        "failures": len(report.get("failures", [])),
    })
    return 0 if report["status"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {"build": _build, "validate": _validate, "audit": _audit, "package": _package, "status": _status}[args.command](args)
