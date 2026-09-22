from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import duckdb

from morocco_elections.warehouse.coverage import DIMENSIONS, coverage_report, validate_universes
from morocco_elections.warehouse.contracts import ALL_TABLE_CONTRACTS, TABLE_CONTRACTS
from morocco_elections.warehouse.demography import load_hcp_rgph2014_individuals, validate_population_crosswalks
from morocco_elections.warehouse.history import (
    geographies_comparable,
    validate_geo_history,
    validate_party_history,
    validate_result_geographies,
)
from morocco_elections.warehouse.gates.base import GateResult
from morocco_elections.warehouse.gates.registry import SPECS, build_registry
from morocco_elections.warehouse.institutional import validate_candidacies_and_seats
from morocco_elections.warehouse.immutability import (
    CANONICAL_MANIFEST_BYTES,
    CANONICAL_MANIFEST_SHA256,
    MANIFEST_PATH,
    verify_v15_immutability,
)
from morocco_elections.warehouse.reconciliation import compare
from morocco_elections.warehouse.schema import OPTIONAL_FIELDS
from morocco_elections.warehouse.validation import (
    ValidationIssue,
    _as_date,
    validate_legal_regimes,
    validate_rows,
    validate_semantic_consistency,
)
from morocco_elections.warehouse.versions import validate_revisions


REQUIRED_GATES = tuple(spec.gate_id for spec in SPECS)


@dataclass(frozen=True)
class PublicationContext:
    """Inputs inspected by publication gates; callers cannot provide gate outcomes."""

    release_id: str
    as_of_date: date | str
    files: Sequence[Mapping[str, Any]]
    coverage_matrix: Sequence[Mapping[str, Any]]
    datasets: Mapping[str, Sequence[Mapping[str, Any]]]
    checks: Mapping[str, Sequence[Mapping[str, Any]]]
    package_root: Path | None = None
    evidence_bundle_path: str | None = None
    evidence_bundle_sha256: str | None = None
    evidence_root: Path | None = None
    package_database_path: str | None = None
    package_manifest_path: str | None = None
    package_manifest_sha256: str | None = None
    v15_root: Path | None = None
    v15_manifest_path: Path = MANIFEST_PATH


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_checksums(root: Path, relative_paths: Iterable[str]) -> list[dict[str, str]]:
    output = []
    resolved_root = root.resolve()
    for relative in sorted(relative_paths):
        path = (root / relative).resolve()
        if resolved_root not in path.parents or not path.is_file():
            raise ValueError(f"unsafe or missing publication file: {relative}")
        output.append({"relative_path": relative.replace("\\", "/"), "sha256": sha256_file(path)})
    return output


def evidence_bundle_payload(context: PublicationContext) -> dict[str, Any]:
    manifest_sha256: str | None = None
    try:
        manifest_bytes = context.v15_manifest_path.read_bytes()
    except OSError:
        pass
    else:
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    table_index: list[dict[str, Any]] = []
    source_references: list[str] = []
    if context.package_root is not None and context.package_database_path:
        root = context.package_root.resolve()
        catalog_path = root / "table-catalog.json"
        database_path = (root / context.package_database_path).resolve()
        if catalog_path.is_file():
            try:
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                table_index = [
                    {
                        "table_name": row.get("table_name"),
                        "row_count": row.get("row_count"),
                        "logical_sha256": row.get("logical_sha256"),
                    }
                    for row in catalog.get("tables", [])
                ]
            except (OSError, ValueError, TypeError):
                table_index = []
        if root in database_path.parents and database_path.is_file():
            try:
                connection = duckdb.connect(str(database_path), read_only=True)
                try:
                    names = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
                    if "sources" in names:
                        source_references = [
                            str(row[0]) for row in connection.execute(
                                "SELECT DISTINCT source_id FROM sources WHERE source_id IS NOT NULL ORDER BY source_id"
                            ).fetchall()
                        ]
                finally:
                    connection.close()
            except (duckdb.Error, OSError):
                source_references = []
    if not table_index:
        for name, rows in sorted(context.datasets.items()):
            encoded = json.dumps(_canonical(rows), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
            table_index.append({"table_name": name, "row_count": len(rows), "logical_sha256": hashlib.sha256(encoded).hexdigest()})
    return {
        "release_id": context.release_id,
        "as_of_date": _canonical(context.as_of_date),
        "files": _canonical(context.files),
        "checks": _canonical(context.checks),
        "tables": table_index,
        "source_references": source_references,
        "package_database_path": context.package_database_path,
        "package_manifest": {
            "relative_path": context.package_manifest_path,
            "sha256": context.package_manifest_sha256,
        },
        "v15_immutability_manifest": {
            "sha256": manifest_sha256,
        },
    }


def write_evidence_bundle(
    context: PublicationContext,
    relative_path: str = "validation-evidence.json",
) -> PublicationContext:
    """Atomically freeze every gate input under the package root; never overwrite evidence."""
    if context.package_root is None:
        raise ValueError("package_root is required to write an evidence bundle")
    root = context.package_root.resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents:
        raise ValueError(f"unsafe evidence bundle path: {relative_path}")
    if target.exists():
        raise FileExistsError(f"refusing to overwrite evidence bundle: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        evidence_bundle_payload(context), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return replace(
        context,
        evidence_bundle_path=relative_path.replace("\\", "/"),
        evidence_bundle_sha256=hashlib.sha256(encoded).hexdigest(),
    )


def validate_coverage_matrix(rows: Iterable[Mapping[str, Any]]) -> list[ValidationIssue]:
    rows = list(rows)
    issues = validate_rows("release_coverage_matrix", rows)
    for row in rows:
        rid = str(row.get("scope_id", "<unknown>"))
        values = [row.get(name) for name in ("acquired", "expected", "covered", "missing", "non_comparable", "redistribution_forbidden")]
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            issues.append(ValidationIssue("INVALID_COVERAGE_MATRIX_COUNT", "release_coverage_matrix", rid, "all counts must be non-negative integers"))
            continue
        if row["expected"] != row["covered"] + row["missing"] + row["non_comparable"] + row["redistribution_forbidden"]:
            issues.append(ValidationIssue("COVERAGE_MATRIX_NOT_RECONCILED", "release_coverage_matrix", rid, "expected must equal covered + missing + non_comparable + redistribution_forbidden"))
        status = row.get("status")
        if status not in {"COMPLETE", "PARTIAL", "EMPTY", "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR"}:
            issues.append(ValidationIssue("INVALID_COVERAGE_STATUS", "release_coverage_matrix", rid, str(status)))
        try:
            universe_ids = json.loads(str(row.get("universe_ids_json")))
        except (TypeError, ValueError):
            universe_ids = None
        if (
            not isinstance(universe_ids, list)
            or any(not isinstance(value, str) or not value for value in universe_ids)
            or len(universe_ids) != len(set(universe_ids))
            or universe_ids != sorted(universe_ids)
        ):
            issues.append(ValidationIssue("INVALID_COVERAGE_UNIVERSE_IDS", "release_coverage_matrix", rid, "universe_ids_json must be a sorted unique JSON string array"))
        elif status == "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR" and universe_ids:
            issues.append(ValidationIssue("UNKNOWN_COVERAGE_HAS_UNIVERSE", "release_coverage_matrix", rid, "unknown coverage cannot claim a verified universe"))
        elif status != "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR" and not universe_ids:
            issues.append(ValidationIssue("COVERAGE_UNIVERSE_REFERENCE_REQUIRED", "release_coverage_matrix", rid, "known coverage status must reference its verified universes"))
    return issues


def _canonical(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value.resolve())
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _gate(gate_id: str, evidence: Any, failures: Iterable[tuple[str, str]], success: str) -> GateResult:
    failures = tuple((str(record), message) for record, message in failures)
    proof = {"evidence": evidence, "failures": failures}
    encoded = json.dumps(_canonical(proof), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    evidence_id = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if failures:
        messages = sorted({message for _, message in failures})
        return GateResult(gate_id, "FAIL", "; ".join(messages), evidence_id, tuple(sorted({record for record, _ in failures})))
    return GateResult(gate_id, "PASS", success, evidence_id, ())


def _issue_failures(issues: Iterable[ValidationIssue]) -> list[tuple[str, str]]:
    return [(issue.record_id, f"{issue.code}: {issue.message}") for issue in issues]


def _rows(context: PublicationContext, name: str) -> list[Mapping[str, Any]]:
    return list(context.datasets.get(name, ()))


def _checks(context: PublicationContext, name: str) -> list[Mapping[str, Any]]:
    return list(context.checks.get(name, ()))


def _require_rows(name: str, rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    return [] if rows else [(name, f"{name} has no inspectable evidence")]


def _bind_contract_tables(
    context: PublicationContext,
    datasets: Mapping[str, tuple[str, Sequence[Mapping[str, Any]]]],
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Compare every contract field against every materialized package row."""
    failures: list[tuple[str, str]] = []
    observed: dict[str, Any] = {}
    root, relative = context.package_root, context.package_database_path
    if root is None or not relative:
        return observed, [(context.release_id, "package-rooted DuckDB database is required for contract-table binding")]
    root = root.resolve()
    path = (root / relative).resolve()
    declared = {str(row.get("relative_path")): row for row in context.files}
    if root not in path.parents or not path.is_file():
        return observed, [(relative, "package contract database is unsafe or missing")]
    if relative not in declared or sha256_file(path) != declared[relative].get("sha256"):
        return observed, [(relative, "package contract database lacks its observed publication SHA-256")]
    try:
        connection = duckdb.connect(str(path), read_only=True)
        try:
            for name, (table, evaluated_rows) in datasets.items():
                if table in ALL_TABLE_CONTRACTS:
                    fields = [*ALL_TABLE_CONTRACTS[table]["required"], *OPTIONAL_FIELDS.get(table, ())]
                    identity = ALL_TABLE_CONTRACTS[table]["primary_key"][0]
                else:
                    fields = sorted({str(field) for row in evaluated_rows for field in row})
                    identity = fields[0] if fields else "<unknown>"
                selected = ", ".join(f'"{field}"' for field in fields)
                cursor = connection.execute(f'SELECT {selected} FROM "{table}"')
                package_rows = [dict(zip(fields, values, strict=True)) for values in cursor.fetchall()]
                observed[name] = {"table": table, "row_count": len(package_rows), "rows": package_rows}
                def row_key(row: Mapping[str, Any]) -> str:
                    projected = {}
                    for field in fields:
                        value = row.get(field)
                        if field == "supporting_source_ids" and isinstance(value, str):
                            try:
                                value = json.loads(value)
                            except ValueError:
                                pass  # An invalid stored value remains unequal to the evaluated list.
                        if field in {"threshold", "official_value", "recomputed_value", "difference", "tolerance"} and value is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
                            value = float(value)
                        projected[field] = value
                    return json.dumps(_canonical(projected), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

                package_multiset = Counter(row_key(row) for row in package_rows)
                evaluated_multiset = Counter(row_key(row) for row in evaluated_rows)
                for encoded, count in (package_multiset - evaluated_multiset).items():
                    rid = str(json.loads(encoded).get(identity) or "<unknown>")
                    failures.append((rid, f"{count} materialized {table} row(s) were omitted or changed in {name}"))
                for encoded, count in (evaluated_multiset - package_multiset).items():
                    rid = str(json.loads(encoded).get(identity) or "<unknown>")
                    failures.append((rid, f"{count} evaluated {name} row(s) are absent or changed in materialized {table}"))
        finally:
            connection.close()
    except (duckdb.Error, OSError) as error:
        failures.append((relative, f"cannot inspect all materialized contract tables: {type(error).__name__}"))
    return observed, failures


def _verify_demographic_source_rows(
    context: PublicationContext,
    populations: Sequence[Mapping[str, Any]],
    crosswalks: Sequence[Mapping[str, Any]],
    sources: Mapping[Any, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Re-extract every claimed demographic row from pinned source bytes."""
    failures: list[tuple[str, str]] = []
    observed: dict[str, Any] = {}
    source_ids = {row.get("source_id") for row in [*populations, *crosswalks]}
    if not source_ids:
        return observed, failures
    if context.evidence_root is None:
        return observed, [(context.release_id, "evidence_root is required to reproduce demographic rows")]
    root = context.evidence_root.resolve()
    package_root, relative = context.package_root, context.package_database_path
    if package_root is None or not relative:
        return observed, [(context.release_id, "package database is required to reproduce demographic crosswalks")]
    package_root = package_root.resolve()
    database = (package_root / relative).resolve()
    declared = {str(row.get("relative_path")): row for row in context.files}
    if package_root not in database.parents or not database.is_file() or sha256_file(database) != declared.get(relative, {}).get("sha256"):
        return observed, [(relative, "demographic extraction lacks its pinned package geography database")]
    try:
        connection = duckdb.connect(str(database), read_only=True)
        try:
            fields = ("geo_id", "geo_type", "geo_name", "parent_geo_id")
            geographies = [
                dict(zip(fields, values, strict=True))
                for values in connection.execute(
                    "SELECT geo_id, geo_type, geo_name, parent_geo_id FROM dim_geo"
                ).fetchall()
            ]
        finally:
            connection.close()
    except (duckdb.Error, OSError) as error:
        return observed, [(relative, f"cannot inspect package geographies for demographic extraction: {type(error).__name__}")]
    for source_id in sorted(source_ids, key=str):
        source = sources.get(source_id)
        if source is None or source.get("extraction_method") != "HCP_RGPH2014_INDIVIDUS":
            failures.append((str(source_id), "demographic source lacks a supported, declared extraction method"))
            continue
        relative = source.get("raw_path")
        path = (root / str(relative)).resolve() if relative else root
        if root not in path.parents or not path.is_file():
            failures.append((str(source_id), "demographic source path is unsafe or missing"))
            continue
        if path.stat().st_size != source.get("bytes") or sha256_file(path) != source.get("sha256"):
            failures.append((str(source_id), "demographic source bytes differ from pinned size or SHA-256"))
            continue
        try:
            derived_populations, derived_crosswalks = load_hcp_rgph2014_individuals(
                path, geographies, source_id=str(source_id), source_url=str(source.get("source_url")),
            )
        except (OSError, ValueError, TypeError, KeyError, IndexError, zipfile.BadZipFile) as error:
            failures.append((str(source_id), f"demographic extraction failed: {type(error).__name__}"))
            continue
        for dataset, table, derived, evaluated in (
            ("geo_populations", "fact_geo_population", derived_populations, populations),
            ("geo_official_identifier_crosswalks", "bridge_geo_official_identifier", derived_crosswalks, crosswalks),
        ):
            fields = [*TABLE_CONTRACTS[table]["required"], *OPTIONAL_FIELDS.get(table, ())]
            identity = TABLE_CONTRACTS[table]["primary_key"][0]

            def encoded(row: Mapping[str, Any]) -> str:
                return json.dumps(
                    _canonical({field: row.get(field) for field in fields}),
                    ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                )

            expected_rows = [row for row in evaluated if row.get("source_id") == source_id]
            observed[f"{source_id}:{dataset}"] = {"source_sha256": source.get("sha256"), "derived_count": len(derived)}
            derived_multiset = Counter(encoded(row) for row in derived)
            evaluated_multiset = Counter(encoded(row) for row in expected_rows)
            for key, count in (derived_multiset - evaluated_multiset).items():
                rid = str(json.loads(key).get(identity) or "<unknown>")
                failures.append((rid, f"{count} source-derived {table} row(s) are absent or changed in evaluated {dataset}"))
            for key, count in (evaluated_multiset - derived_multiset).items():
                rid = str(json.loads(key).get(identity) or "<unknown>")
                failures.append((rid, f"{count} evaluated {dataset} row(s) are absent or changed in source-derived {table}"))
    return observed, failures


def _package_inventory(context: PublicationContext) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Inventory every package byte and reject paths not derived from release evidence."""
    if context.package_root is None:
        return [], [(context.release_id, "package_root is required to inventory package files")]
    root = context.package_root.resolve()
    allowed: dict[str, str] = {
        str(row.get("relative_path", "")).replace("\\", "/"): "PUBLICATION_FILE"
        for row in context.files
        if row.get("relative_path")
    }
    if context.evidence_bundle_path:
        allowed[context.evidence_bundle_path.replace("\\", "/")] = "EVIDENCE_BUNDLE"
    if context.package_manifest_path:
        allowed[context.package_manifest_path.replace("\\", "/")] = "PACKAGE_MANIFEST"
    failures: list[tuple[str, str]] = []
    for build in _checks(context, "clean_builds"):
        report_relative = build.get("report_path")
        if not isinstance(report_relative, str) or not report_relative:
            continue
        normalized_report = report_relative.replace("\\", "/")
        allowed[normalized_report] = "CLEAN_BUILD_REPORT"
        report_path = (root / report_relative).resolve()
        if root not in report_path.parents or not report_path.is_file():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        manifest_relative = report.get("manifest_path") if isinstance(report, dict) else None
        if isinstance(manifest_relative, str) and manifest_relative:
            allowed[manifest_relative.replace("\\", "/")] = "PACKAGE_MANIFEST"

    inventory: list[dict[str, Any]] = []
    if not root.is_dir():
        return inventory, [(context.release_id, "package_root is not an inspectable directory")]
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() and not path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        resolved = path.resolve()
        if path.is_symlink() or root not in resolved.parents:
            failures.append((relative, "package entries must be regular files physically contained under package_root"))
            inventory.append({"relative_path": relative, "role": "UNSAFE", "sha256": None})
            continue
        role = allowed.get(relative)
        if role is None:
            failures.append((relative, "unmanaged file is present in the public package"))
            role = "UNMANAGED"
        inventory.append({"relative_path": relative, "role": role, "sha256": sha256_file(path)})
    actual = {row["relative_path"] for row in inventory}
    for relative, role in allowed.items():
        target = (root / relative).resolve()
        if not relative or root not in target.parents:
            failures.append((relative or "<empty>", f"unsafe {role.lower()} path"))
        elif relative not in actual:
            failures.append((relative, f"declared {role.lower()} is absent from the package inventory"))
    return inventory, failures


def _evidence_bundle(context: PublicationContext) -> GateResult:
    failures: list[tuple[str, str]] = []
    expected = evidence_bundle_payload(context)
    observed: Any = None
    observed_sha256: str | None = None
    root = context.package_root.resolve() if context.package_root is not None else None
    if root is None or not context.evidence_bundle_path or not context.evidence_bundle_sha256:
        failures.append((context.release_id, "package-rooted evidence bundle path and SHA-256 are required"))
    else:
        path = (root / context.evidence_bundle_path).resolve()
        if root not in path.parents or not path.is_file():
            failures.append((context.release_id, "evidence bundle is unsafe or missing"))
        else:
            observed_sha256 = sha256_file(path)
            if observed_sha256 != context.evidence_bundle_sha256:
                failures.append((context.release_id, f"evidence bundle checksum mismatch: observed {observed_sha256}"))
            try:
                observed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                failures.append((context.release_id, "evidence bundle is not valid UTF-8 JSON"))
            else:
                if _canonical(observed) != _canonical(expected):
                    failures.append((context.release_id, "evidence bundle content differs from the evaluated publication context"))
    inventory, inventory_failures = _package_inventory(context)
    failures += inventory_failures
    evidence = {
        "path": context.evidence_bundle_path,
        "declared_sha256": context.evidence_bundle_sha256,
        "observed_sha256": observed_sha256,
        "bundle": observed,
        "package_inventory": inventory,
    }
    return _gate(
        "EVIDENCE_BUNDLE_VERIFIED",
        evidence,
        failures,
        "The complete gate context matches its SHA-256 bundle and every package file has a derived role.",
    )


def _semantic_facts(context: PublicationContext) -> GateResult:
    # Local import avoids the evidence -> publication -> geography-evidence cycle.
    from morocco_elections.warehouse.geo_parents import validate_geo_parent_relations

    facts = _rows(context, "semantic_facts")
    contests, elections, geographies = _rows(context, "contests"), _rows(context, "elections"), _rows(context, "geographies")
    geo_parent_relations = _rows(context, "geo_parent_relations")
    failures = _require_rows("semantic_facts", facts)
    failures += _require_rows("contests", contests) + _require_rows("elections", elections) + _require_rows("geographies", geographies)
    source_facts: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    source_dimensions: dict[str, list[dict[str, Any]]] = {}
    dimension_fields = {
        "elections": ("dim_election", ("election_id", "election_date"), "election_id"),
        "contests": ("dim_electoral_contest", ("contest_id", "election_id", "geo_id"), "contest_id"),
        "geographies": ("dim_geo", ("geo_id", "parent_geo_id"), "geo_id"),
        "geo_parent_relations": (
            "bridge_geo_parent",
            tuple(TABLE_CONTRACTS["bridge_geo_parent"]["required"]) + OPTIONAL_FIELDS["bridge_geo_parent"],
            "relation_id",
        ),
    }
    relative = context.package_database_path
    root = context.package_root.resolve() if context.package_root is not None else None
    declared = {str(row.get("relative_path")): row for row in context.files}
    if root is None or not relative:
        failures.append((context.release_id, "package-rooted DuckDB fact database is required for exhaustive semantic validation"))
    else:
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            failures.append((relative, "package fact database is unsafe or missing"))
        elif relative not in declared or sha256_file(path) != declared[relative].get("sha256"):
            failures.append((relative, "package fact database is not declared with its observed SHA-256"))
        else:
            try:
                connection = duckdb.connect(str(path), read_only=True)
                try:
                    for table in ("fact_election_result", "fact_electoral_mobilization", "fact_communal_election_result"):
                        cursor = connection.execute(f'SELECT * FROM "{table}"')
                        columns = [item[0] for item in cursor.description]
                        rows = [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]
                        source_counts[table] = len(rows)
                        source_facts.extend(rows)
                    for name, (table, fields, _) in dimension_fields.items():
                        selected = ", ".join(f'"{field}"' for field in fields)
                        cursor = connection.execute(f'SELECT {selected} FROM "{table}"')
                        source_dimensions[name] = [
                            dict(zip(fields, values, strict=True)) for values in cursor.fetchall()
                        ]
                finally:
                    connection.close()
            except (duckdb.Error, OSError) as error:
                failures.append((relative, f"cannot inspect all package fact and dimension tables: {type(error).__name__}"))
    def row_key(row: Mapping[str, Any]) -> str:
        return json.dumps(_canonical(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    if len(source_counts) == 3:
        source_multiset = Counter(row_key(row) for row in source_facts)
        evaluated_multiset = Counter(row_key(row) for row in facts)
        for encoded, count in (source_multiset - evaluated_multiset).items():
            row = json.loads(encoded)
            rid = str(row.get("result_id") or row.get("mobilization_id") or row.get("communal_result_id") or "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest())
            failures.append((rid, f"{count} package fact row(s) were omitted from semantic evaluation"))
        for encoded, count in (evaluated_multiset - source_multiset).items():
            row = json.loads(encoded)
            rid = str(row.get("result_id") or row.get("mobilization_id") or row.get("communal_result_id") or "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest())
            failures.append((rid, f"{count} semantic fact row(s) are absent from the package database"))
    if len(source_dimensions) == len(dimension_fields):
        evaluated_dimensions = {
            "elections": elections,
            "contests": contests,
            "geographies": geographies,
            "geo_parent_relations": geo_parent_relations,
        }
        for name, (_, fields, key_field) in dimension_fields.items():
            source_multiset = Counter(row_key(row) for row in source_dimensions[name])
            evaluated_multiset = Counter(
                row_key({field: row.get(field) for field in fields})
                for row in evaluated_dimensions[name]
            )
            for encoded, count in (source_multiset - evaluated_multiset).items():
                rid = str(json.loads(encoded).get(key_field) or "<unknown>")
                failures.append((rid, f"{count} package {name} row(s) were omitted or changed in semantic evaluation"))
            for encoded, count in (evaluated_multiset - source_multiset).items():
                rid = str(json.loads(encoded).get(key_field) or "<unknown>")
                failures.append((rid, f"{count} evaluated {name} row(s) are absent or changed in the package database"))
    failures += _issue_failures(validate_geo_parent_relations(geo_parent_relations, geographies, elections))
    failures += _issue_failures(validate_semantic_consistency(facts, contests, elections, geographies, geo_parent_relations))
    evidence = {"evaluated_facts": facts, "package_fact_counts": source_counts, "package_facts": source_facts, "package_dimensions": source_dimensions, "contests": contests, "elections": elections, "geographies": geographies, "geo_parent_relations": geo_parent_relations}
    return _gate("SEMANTIC_FACTS_VALIDATED", evidence, failures, "Every package fact, dimension row, and materialized geographic-parent relation is exhaustively evaluated.")


def _legal_regime(context: PublicationContext) -> GateResult:
    elections, regimes, links = _rows(context, "elections"), _rows(context, "legal_regimes"), _rows(context, "election_legal_regimes")
    failures = _require_rows("elections", elections) + _require_rows("legal_regimes", regimes) + _require_rows("election_legal_regimes", links)
    contests, contest_links = _rows(context, "contests"), _rows(context, "contest_legal_regimes")
    failures += _require_rows("contests", contests) + _require_rows("contest_legal_regimes", contest_links)
    failures += _issue_failures(validate_legal_regimes(elections, regimes, links, contests, contest_links))
    official_sources = _rows(context, "official_sources")
    failures += _require_rows("official_sources", official_sources)
    sources_by_id = {row.get("source_id"): row for row in official_sources}
    references = [
        ("dim_legal_regime", row.get("legal_regime_id"), row.get("official_source_id"))
        for row in regimes
    ]
    references += [
        ("dim_legal_regime", row.get("legal_regime_id"), source_id)
        for row in regimes
        for source_id in row.get("supporting_source_ids", [])
    ]
    classified_links = [row for row in contest_links if row.get("classification_basis") == "POPULATION_THRESHOLD"]
    geo_classified_links = [row for row in contest_links if row.get("classification_basis") == "GEO_TYPE"]
    population_rules = _rows(context, "population_legal_rules")
    geo_type_rules = _rows(context, "geo_type_legal_rules")
    populations = _rows(context, "geo_populations")
    crosswalks = _rows(context, "geo_official_identifier_crosswalks")
    failures += _issue_failures(validate_population_crosswalks(populations, crosswalks, _rows(context, "geographies")))
    if classified_links:
        failures += _require_rows("population_legal_rules", population_rules)
        failures += _require_rows("geo_populations", populations)
        failures += _require_rows("geo_official_identifier_crosswalks", crosswalks)
    population_by_code = {row.get("official_geo_code"): row for row in populations}
    crosswalk_by_geo = {row.get("geo_id"): row for row in crosswalks}
    population_rule_by_election = {row.get("election_id"): row for row in population_rules}
    for link in classified_links:
        contest_id = str(link.get("contest_id"))
        rule = population_rule_by_election.get(link.get("election_id"))
        crosswalk = crosswalk_by_geo.get(next((row.get("geo_id") for row in contests if row.get("contest_id") == link.get("contest_id")), None))
        population = population_by_code.get(crosswalk.get("official_geo_code")) if crosswalk else None
        if rule is None or crosswalk is None or population is None:
            failures.append((contest_id, "population classification lacks its rule, exact-code crosswalk, or population row"))
            continue
        value, threshold = population.get("population"), rule.get("threshold")
        if not isinstance(value, int) or not isinstance(threshold, int):
            failures.append((contest_id, "population classification operands are not integers"))
            continue
        expected_regime = rule.get("at_or_below_regime_id") if value <= threshold else rule.get("above_regime_id")
        if (
            crosswalk.get("geo_type") != rule.get("geo_type")
            or crosswalk.get("confidence") != 1.0
            or link.get("legal_regime_id") != expected_regime
            or link.get("classification_value") != value
            or link.get("classification_source_id") != rule.get("population_source_id")
        ):
            failures.append((contest_id, "materialized legal regime does not match the official population classification"))
    if geo_classified_links:
        failures += _require_rows("geo_type_legal_rules", geo_type_rules)
        failures += _require_rows("geo_official_identifier_crosswalks", crosswalks)
    geo_rule_by_key = {(row.get("election_id"), row.get("geo_type")): row for row in geo_type_rules}
    contest_by_id = {row.get("contest_id"): row for row in contests}
    for link in geo_classified_links:
        contest_id = str(link.get("contest_id"))
        contest = contest_by_id.get(link.get("contest_id"))
        crosswalk = crosswalk_by_geo.get(contest.get("geo_id")) if contest else None
        geo_type = crosswalk.get("geo_type") if crosswalk else None
        rule = geo_rule_by_key.get((link.get("election_id"), geo_type))
        if (
            crosswalk is None
            or crosswalk.get("confidence") != 1.0
            or rule is None
            or link.get("legal_regime_id") != rule.get("legal_regime_id")
            or link.get("source_id") != rule.get("source_id")
        ):
            failures.append((contest_id, "materialized legal regime does not match the exact official geography type"))
    references += [
        ("bridge_election_legal_regime", row.get("election_id"), row.get("source_id"))
        for row in links
    ]
    references += [
        ("bridge_contest_legal_regime", row.get("contest_id"), row.get("source_id"))
        for row in contest_links
    ]
    references += [
        ("bridge_contest_legal_regime", row.get("contest_id"), row.get("classification_source_id"))
        for row in contest_links
        if row.get("classification_source_id")
    ]
    references += [
        ("fact_geo_population", row.get("geo_population_id"), row.get("source_id"))
        for row in populations
    ]
    references += [
        ("bridge_geo_official_identifier", row.get("crosswalk_id"), row.get("source_id"))
        for row in crosswalks
    ]
    for table, record_id, source_id in references:
        source = sources_by_id.get(source_id)
        if source is None:
            failures.append((str(record_id), f"{table} references unknown official source {source_id}"))
        elif source.get("verification_status") != "VERIFIED_AUTHORITY_AND_BYTES":
            failures.append((str(record_id), f"{table} source {source_id} has no verified local bytes"))
    for population in populations:
        source = sources_by_id.get(population.get("source_id"))
        if source is not None and population.get("source_url") != source.get("source_url"):
            failures.append((str(population.get("geo_population_id")), "population source URL differs from its verified registry URL"))
    if context.evidence_root is None:
        failures.append((context.release_id, "evidence_root is required to verify legal source bytes"))
    else:
        # Local import avoids a module cycle: evidence reuses sha256_file from this module.
        from morocco_elections.warehouse.evidence import validate_official_source_registry

        failures += _issue_failures(
            validate_official_source_registry(context.evidence_root, {"sources": official_sources})
        )
    derived_demography, source_failures = _verify_demographic_source_rows(
        context, populations, crosswalks, sources_by_id,
    )
    failures += source_failures
    materialized, binding_failures = _bind_contract_tables(context, {
        "legal_regimes": ("dim_legal_regime", regimes),
        "election_legal_regimes": ("bridge_election_legal_regime", links),
        "contest_legal_regimes": ("bridge_contest_legal_regime", contest_links),
        "geo_populations": ("fact_geo_population", populations),
        "geo_official_identifier_crosswalks": ("bridge_geo_official_identifier", crosswalks),
    })
    failures += binding_failures
    evidence = [elections, contests, regimes, links, contest_links, official_sources, population_rules, geo_type_rules, populations, crosswalks, materialized, derived_demography]
    return _gate("LEGAL_REGIME_PINNED", evidence, failures, "Every covered contest has one sourced applicable regime, and all five legal and demographic tables match the package and demographic source bytes.")


def _result_status(context: PublicationContext) -> GateResult:
    revisions = _rows(context, "result_revisions")
    decisions = _rows(context, "legal_decisions")
    gaps = _rows(context, "result_history_gaps")
    failures = _issue_failures(validate_revisions(revisions))
    failures += _issue_failures(validate_rows("fact_legal_decision", decisions))
    materialized, binding_failures = _bind_contract_tables(context, {
        "result_revisions": ("fact_result_revision", revisions),
        "legal_decisions": ("fact_legal_decision", decisions),
    })
    failures += binding_failures
    if not revisions:
        if gaps:
            for gap in gaps:
                scope_id = str(gap.get("scope_id", "<unknown>"))
                required = (
                    "scope_type", "scope_id", "required_source", "availability_status",
                    "publication_consequence", "blocking_code",
                )
                missing = [field for field in required if not gap.get(field)]
                if missing:
                    failures.append((scope_id, "result-history gap lacks " + ", ".join(missing)))
                else:
                    failures.append((scope_id, f"{gap['blocking_code']}: {gap['publication_consequence']}"))
        else:
            failures += _require_rows("result_revisions", revisions)
    decisions_by_id = {row.get("decision_id"): row for row in decisions}
    referenced_decisions: set[Any] = set()
    expected_decision_types = {"RECTIFIED": "RECTIFICATION", "ANNULLED": "ANNULMENT"}
    for revision in revisions:
        rid, decision_id = str(revision.get("revision_id", "<unknown>")), revision.get("decision_id")
        if revision.get("result_status") in expected_decision_types and decision_id is None:
            failures.append((rid, "rectified or annulled revision must reference its legal decision"))
        if decision_id is None:
            continue
        referenced_decisions.add(decision_id)
        decision = decisions_by_id.get(decision_id)
        if decision is None:
            failures.append((rid, "revision references an absent legal decision"))
            continue
        if decision.get("affected_revision_id") != revision.get("revision_id"):
            failures.append((rid, "legal decision does not identify the affected revision"))
        expected_type = expected_decision_types.get(str(revision.get("result_status")))
        if expected_type is not None and decision.get("decision_type") != expected_type:
            failures.append((rid, f"legal decision type must be {expected_type}"))
        decision_date, published_at = _as_date(decision.get("decision_date")), _as_date(revision.get("published_at"))
        if decision_date is not None and published_at is not None and decision_date > published_at:
            failures.append((rid, "legal decision postdates the publication of the affected revision"))
    for decision in decisions:
        if decision.get("decision_id") not in referenced_decisions:
            failures.append((str(decision.get("decision_id", "<unknown>")), "legal decision is not linked from a retained revision"))

    official_sources = _rows(context, "official_sources")
    sources_by_id = {row.get("source_id"): row for row in official_sources}
    referenced_source_ids = {
        row.get("source_id") for row in [*revisions, *decisions] if row.get("source_id") is not None
    }
    referenced_sources = [row for row in official_sources if row.get("source_id") in referenced_source_ids]
    if referenced_sources and context.evidence_root is None:
        failures.append((context.release_id, "evidence_root is required to verify result-history source bytes"))
    elif referenced_sources:
        from morocco_elections.warehouse.evidence import validate_official_source_registry

        failures += _issue_failures(
            validate_official_source_registry(context.evidence_root, {"sources": referenced_sources})
        )
    for table, rows in (("revision", revisions), ("legal decision", decisions)):
        for row in rows:
            rid = str(row.get("revision_id") or row.get("decision_id") or "<unknown>")
            source = sources_by_id.get(row.get("source_id"))
            if source is None or source.get("verification_status") != "VERIFIED_AUTHORITY_AND_BYTES":
                failures.append((rid, f"{table} lacks a registry source with verified local bytes"))
            elif table == "legal decision" and row.get("source_url") != source.get("source_url"):
                failures.append((rid, "legal-decision URL differs from its registered source URL"))
    claims_by_source: dict[Any, list[dict[str, Any]]] = {}
    if context.evidence_root is not None:
        for source in referenced_sources:
            source_id, raw_path = source.get("source_id"), source.get("raw_path")
            claims: list[dict[str, Any]] = []
            try:
                payload = json.loads((context.evidence_root / str(raw_path)).read_text(encoding="utf-8"))
                candidate = payload.get("result_history_claims", [])
                if isinstance(candidate, list) and all(isinstance(row, dict) for row in candidate):
                    claims = candidate
            except (OSError, UnicodeDecodeError, ValueError, AttributeError):
                pass
            claims_by_source[source_id] = claims
    for revision in revisions:
        rid = str(revision.get("revision_id", "<unknown>"))
        if revision.get("verification_method") != "STRUCTURED_SOURCE_CLAIM":
            failures.append((rid, "revision verification_method must be STRUCTURED_SOURCE_CLAIM"))
        if revision.get("verification_status") != "VERIFIED":
            failures.append((rid, "revision verification_status must be VERIFIED"))
        source = sources_by_id.get(revision.get("source_id"), {})
        acquired_at, known_at = _as_date(source.get("acquired_at")), _as_date(revision.get("known_at"))
        if acquired_at is None:
            failures.append((rid, "revision source lacks an acquisition date"))
        elif known_at is not None and known_at < acquired_at:
            failures.append((rid, "known_at precedes source acquisition"))
        claim_fields = ("revision_id", "result_id", "contest_id", "result_status", "valid_from", "published_at")
        matching_claim = any(
            all(_canonical(claim.get(field)) == _canonical(revision.get(field)) for field in claim_fields)
            for claim in claims_by_source.get(revision.get("source_id"), [])
        )
        if not matching_claim:
            failures.append((rid, "verified source bytes do not prove the declared status and dates"))
    evidence = {
        "revisions": revisions, "legal_decisions": decisions, "official_sources": referenced_sources,
        "result_history_gaps": gaps, "materialized": materialized, "source_claims": claims_by_source,
    }
    return _gate(
        "RESULT_STATUS_KNOWN",
        evidence,
        failures,
        "Every revision has a valid sourced chain and every legal decision is linked to its affected revision.",
    )


def _as_of(context: PublicationContext) -> GateResult:
    revisions, as_of = _rows(context, "result_revisions"), _as_date(context.as_of_date)
    metadata = _rows(context, "warehouse_metadata")
    failures: list[tuple[str, str]] = []
    if as_of is None:
        failures.append((context.release_id, "release as_of_date is not a valid ISO date"))
    for row in revisions:
        rid = str(row.get("revision_id", "<unknown>"))
        for field in ("valid_from", "known_at"):
            value = _as_date(row.get(field))
            if value is None:
                failures.append((rid, f"{field} is required and must be an ISO date"))
            elif as_of is not None and value > as_of:
                failures.append((rid, f"{field} is later than release as_of_date"))
        published = _as_date(row.get("published_at"))
        if row.get("published_at") is not None and published is None:
            failures.append((rid, "published_at must be an ISO date when known"))
        elif published is not None and as_of is not None and published > as_of:
            failures.append((rid, "published_at is later than release as_of_date"))
    if len(metadata) != 1:
        failures.append(("warehouse_metadata", "exactly one materialized release metadata row is required"))
    elif _as_date(metadata[0].get("as_of_date")) != as_of:
        failures.append(("warehouse_metadata", "materialized as_of_date differs from the release context"))
    binding_datasets: dict[str, tuple[str, Sequence[Mapping[str, Any]]]] = {
        "warehouse_metadata": ("warehouse_metadata", metadata),
    }
    if revisions:
        binding_datasets["result_revisions"] = ("fact_result_revision", revisions)
    materialized, binding_failures = _bind_contract_tables(context, binding_datasets)
    failures += binding_failures
    return _gate(
        "AS_OF_DATE_VALID",
        {"as_of_date": context.as_of_date, "revisions": revisions, "warehouse_metadata": metadata, "materialized": materialized},
        failures,
        "The materialized release date is explicit and no retained result was published, known, or effective after it.",
    )


def _official_universe(context: PublicationContext) -> GateResult:
    universes, members = _rows(context, "coverage_universes"), _rows(context, "coverage_universe_members")
    observations = _rows(context, "coverage_observations")
    failures = _require_rows("coverage_universes", universes) + _require_rows("coverage_universe_members", members)
    failures += _issue_failures(validate_universes(universes)) + _issue_failures(validate_rows("coverage_universe_member", members))
    official_sources = _rows(context, "official_sources")
    sources_by_id = {row.get("source_id"): row for row in official_sources}
    referenced_source_ids = {
        row.get("source_id") for row in [*universes, *members] if row.get("source_id") is not None
    }
    universe_sources = [row for row in official_sources if row.get("source_id") in referenced_source_ids]
    portability = _checks(context, "source_portability")
    source_root: Path | None = context.evidence_root
    portable_manager: Any = None
    if portability:
        from morocco_elections.warehouse.portability import SourceEvidenceError, portable_evidence_root

        try:
            portable_manager = portable_evidence_root(
                portability,
                {str(value) for value in referenced_source_ids},
                package_root=context.package_root,
                repository_root=context.evidence_root,
            )
            source_root = portable_manager.__enter__()
        except SourceEvidenceError as error:
            failures.append((context.release_id, str(error)))
            source_root = None
    elif source_root is None:
        failures.append((context.release_id, "official-universe source bytes lack a portable evidence strategy"))
    if source_root is not None:
        from morocco_elections.warehouse.evidence import validate_official_source_registry

        failures += _issue_failures(validate_official_source_registry(source_root, {"sources": universe_sources}))
    universe_by_id = {row.get("universe_id"): row for row in universes}
    derived_members: dict[str, list[str]] = {}
    declared_members: dict[Any, set[str]] = {}
    for member in members:
        declared_members.setdefault(member.get("universe_id"), set()).add(str(member.get("expected_id")))
    for row in universes:
        uid, source_id = str(row.get("universe_id")), row.get("source_id")
        source = sources_by_id.get(source_id)
        if source is None or source.get("verification_status") != "VERIFIED_AUTHORITY_AND_BYTES":
            failures.append((uid, "official universe lacks a registry source with verified local bytes"))
        elif row.get("source_url") != source.get("source_url"):
            failures.append((uid, "official-universe URL differs from its registered source URL"))
        if source is None or source_root is None or not source.get("raw_path"):
            continue
        root = source_root.resolve()
        source_path = (root / str(source["raw_path"])).resolve()
        if root not in source_path.parents or not source_path.is_file():
            failures.append((uid, "official-universe source path is unsafe or missing"))
            continue
        method = row.get("member_extraction_method")
        try:
            if method == "HCP_RGPH2014_COMMUNES" and source_id == "MA_HCP_RGPH2014_POPULATION_LEGALE_COMMUNES_12_REGIONS":
                from morocco_elections.warehouse.demography import load_hcp_rgph2014_territorial_universe

                extracted_universe, extracted = load_hcp_rgph2014_territorial_universe(
                    source_path, election_id=str(row.get("election_id")), source_id=str(source_id),
                    source_url=str(source.get("source_url")), acquired_at=str(source.get("acquired_at")),
                )
                if uid != extracted_universe["universe_id"] or row.get("coverage_dimension") != "TERRITORIAL":
                    failures.append((uid, "HCP territorial universe scope or identifier differs from its source-derived contract"))
                expected_ids = {member["expected_id"] for member in extracted}
            elif method == "JSON_UNIVERSES_OBJECT" and source_path.suffix.lower() == ".json":
                payload = json.loads(source_path.read_text(encoding="utf-8"))
                values = payload.get("universes", {}).get(uid) if isinstance(payload, dict) else None
                if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                    raise ValueError("JSON universes object lacks an explicit string identifier array")
                expected_ids = set(values)
                if len(expected_ids) != len(values):
                    failures.append((uid, "official source contains duplicate expected identifiers"))
            else:
                failures.append((uid, "member extraction method is unsupported for the registered official source"))
                continue
        except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError) as error:
            failures.append((uid, f"cannot extract expected identifiers from official source: {type(error).__name__}"))
            continue
        derived_members[uid] = sorted(expected_ids)
        for missing in expected_ids - declared_members.get(row.get("universe_id"), set()):
            failures.append((missing, "source-derived expected identifier is absent from the universe members"))
        for unexpected in declared_members.get(row.get("universe_id"), set()) - expected_ids:
            failures.append((unexpected, "declared universe member is absent from the official source"))
        if row.get("denominator") != len(expected_ids):
            failures.append((uid, "official universe denominator differs from the source-derived identifier count"))
    for row in members:
        rid, universe = str(row.get("expected_id")), universe_by_id.get(row.get("universe_id"))
        source = sources_by_id.get(row.get("source_id"))
        if universe is None:
            continue
        if source is None or source.get("verification_status") != "VERIFIED_AUTHORITY_AND_BYTES":
            failures.append((rid, "expected identifier lacks a registry source with verified local bytes"))
        elif row.get("source_id") != universe.get("source_id"):
            failures.append((rid, "expected identifier source differs from its official universe source"))
    verified = {row.get("universe_id") for row in universes if row.get("verification_status") == "VERIFIED" and row.get("is_external") is True}
    verified_scopes = {
        (str(row.get("election_id")), row.get("coverage_dimension"))
        for row in universes if row.get("universe_id") in verified
    }
    for row in universes:
        if row.get("verification_status") != "VERIFIED":
            failures.append((str(row.get("universe_id")), "official universe is not verified"))
    for row in members:
        if row.get("universe_id") not in verified:
            failures.append((str(row.get("expected_id")), "expected identifier is not attached to a verified external universe"))
    for row in observations:
        dimension, election_id = row.get("coverage_dimension"), row.get("election_id")
        matching = {scope for scope in verified_scopes if scope[1] == dimension}
        if election_id is None and len(matching) == 1:
            continue
        if election_id is None:
            failures.append((str(dimension), "coverage observation needs election_id when a dimension has multiple universes"))
        elif (str(election_id), dimension) not in verified_scopes:
            failures.append((f"{election_id}:{dimension}", "observed coverage scope lacks a verified external universe"))
    evidence = [universes, members, observations, universe_sources, derived_members, portability]
    result = _gate("OFFICIAL_UNIVERSE_DECLARED", evidence, failures, "Every expected identifier is recomputed from verified official source bytes.")
    if portable_manager is not None:
        portable_manager.__exit__(None, None, None)
    return result


def _denominator(context: PublicationContext) -> GateResult:
    universes, members = _rows(context, "coverage_universes"), _rows(context, "coverage_universe_members")
    failures = _require_rows("coverage_universes", universes)
    member_counts: dict[Any, int] = {}
    for row in members:
        member_counts[row.get("universe_id")] = member_counts.get(row.get("universe_id"), 0) + 1
    for row in universes:
        uid, denominator = row.get("universe_id"), row.get("denominator")
        if not isinstance(denominator, int) or isinstance(denominator, bool) or denominator < 0:
            failures.append((str(uid), "denominator must be a non-negative integer"))
        elif denominator != member_counts.get(uid, 0):
            failures.append((str(uid), "denominator does not equal the number of expected identifiers"))
        if not row.get("universe_type"):
            failures.append((str(uid), "denominator type is missing"))
    return _gate("DENOMINATOR_TYPED", [universes, members], failures, "Every denominator is typed and reconciles to its expected-identifier set.")


def _grain(context: PublicationContext) -> GateResult:
    specs = _checks(context, "grain_checks")
    failures: list[tuple[str, str]] = []
    inspected: dict[str, Any] = {}
    if not specs:
        root, relative = context.package_root, context.package_database_path
        if root is None or not relative:
            failures.append((context.release_id, "package database is required for exhaustive row-grain inspection"))
        else:
            root, path = root.resolve(), (root / relative).resolve()
            try:
                if root not in path.parents or not path.is_file():
                    raise OSError("unsafe or missing package database")
                connection = duckdb.connect(str(path), read_only=True)
                try:
                    for (table,) in connection.execute("SHOW TABLES").fetchall():
                        escaped = str(table).replace('"', '""')
                        total = connection.execute(f'SELECT count(*) FROM "{escaped}"').fetchone()[0]
                        distinct = connection.execute(
                            f'SELECT count(*) FROM (SELECT DISTINCT * FROM "{escaped}")'
                        ).fetchone()[0]
                        inspected[str(table)] = {"rows": total, "distinct_rows": distinct}
                        if total != distinct:
                            failures.append((str(table), f"{total - distinct} exact duplicate row(s) violate the materialized grain"))
                finally:
                    connection.close()
            except (duckdb.Error, OSError) as error:
                failures.append((relative, f"cannot inspect materialized row grains: {type(error).__name__}"))
    for spec in specs:
        rid = str(spec.get("check_id", "<unknown>"))
        dataset_name, grain_keys = spec.get("dataset"), spec.get("grain_keys")
        if not isinstance(dataset_name, str) or not dataset_name:
            failures.append((rid, "grain check does not reference an output dataset"))
            continue
        if not isinstance(grain_keys, list) or not grain_keys or any(not isinstance(key, str) or not key for key in grain_keys):
            failures.append((rid, "grain_keys must be a non-empty list of field names"))
            continue
        output = _rows(context, dataset_name)
        inspected[dataset_name] = output
        seen: set[str] = set()
        for index, row in enumerate(output):
            missing = [key for key in grain_keys if row.get(key) is None]
            if missing:
                failures.append((f"{rid}:{index}", f"grain key fields are missing: {', '.join(missing)}"))
                continue
            grain = json.dumps(_canonical([row[key] for key in grain_keys]), ensure_ascii=False, separators=(",", ":"))
            if grain in seen:
                failures.append((f"{rid}:{grain}", "duplicate output row at declared grain"))
            seen.add(grain)
        expected_count = spec.get("expected_row_count")
        if expected_count is not None and (not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count != len(output)):
            failures.append((rid, f"expected_row_count does not match inspected row count {len(output)}"))
    evidence = {"specifications": specs, "inspected_outputs": inspected}
    return _gate("GRAIN_COMPATIBLE", evidence, failures, "Every inspected output is unique and complete at its declared grain.")


def _boundary(context: PublicationContext) -> GateResult:
    rows = _checks(context, "boundary_checks")
    failures = _require_rows("boundary_checks", rows)
    revisions = _rows(context, "result_revisions")
    versions = _rows(context, "geo_versions")
    lineages = _rows(context, "geo_lineages")
    failures += _issue_failures(validate_geo_history(versions, lineages))
    materialized, binding_failures = _bind_contract_tables(context, {
        "geo_versions": ("dim_geo_version", versions),
        "geo_lineages": ("bridge_geo_lineage", lineages),
    })
    failures += binding_failures
    official_sources = _rows(context, "official_sources")
    sources_by_id = {row.get("source_id"): row for row in official_sources}
    referenced_source_ids = {row.get("source_id") for row in [*versions, *lineages]}
    for source_id in referenced_source_ids:
        source = sources_by_id.get(source_id)
        if source is None or source.get("verification_status") != "VERIFIED_AUTHORITY_AND_BYTES":
            failures.append((str(source_id), "geography source lacks a verified official registry entry"))
    if referenced_source_ids:
        if context.evidence_root is None:
            failures.append((context.release_id, "evidence_root is required to verify geography source bytes"))
        else:
            from morocco_elections.warehouse.evidence import validate_official_source_registry

            failures += _issue_failures(validate_official_source_registry(
                context.evidence_root,
                {"sources": [source for source_id in referenced_source_ids if (source := sources_by_id.get(source_id)) is not None]},
            ))
    by_version = {row.get("geo_version_id"): row for row in versions}
    declared_files = {str(row.get("relative_path")): row for row in context.files}
    geometry_fingerprints: dict[Any, str | None] = {}

    def verified_geometry(version_id: Any) -> str | None:
        if version_id in geometry_fingerprints:
            return geometry_fingerprints[version_id]
        version = by_version.get(version_id)
        relative = version.get("geometry_path") if version else None
        root = context.package_root.resolve() if context.package_root is not None else None
        fingerprint: str | None = None
        if isinstance(relative, str) and relative.endswith(".geojson") and root is not None:
            path = (root / relative).resolve()
            file_row = declared_files.get(relative)
            if root in path.parents and path.is_file() and file_row and sha256_file(path) == file_row.get("sha256"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    geometry = payload.get("geometry") if payload.get("type") == "Feature" else payload
                    geometry_type = geometry.get("type")
                    polygons = [geometry.get("coordinates")] if geometry_type == "Polygon" else geometry.get("coordinates") if geometry_type == "MultiPolygon" else []
                    valid = payload.get("crs") is None and geometry.get("crs") is None and bool(polygons) and all(
                        isinstance(polygon, list) and polygon and all(
                            isinstance(ring, list) and len(ring) >= 4
                            and ring[0] == ring[-1]
                            and all(
                                isinstance(point, list) and len(point) == 2
                                and all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in point)
                                and -180 <= point[0] <= 180 and -90 <= point[1] <= 90
                                for point in ring
                            )
                            for ring in polygon
                        )
                        for polygon in polygons
                    )
                    if valid:
                        fingerprint = hashlib.sha256(
                            json.dumps(_canonical(geometry), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                        ).hexdigest()
                except (OSError, UnicodeError, ValueError, AttributeError, TypeError):
                    pass
        geometry_fingerprints[version_id] = fingerprint
        return fingerprint

    for lineage in lineages:
        if lineage.get("geo_lineage_type") != "SAME_BOUNDARY":
            continue
        from_id, to_id = lineage.get("from_geo_version_id"), lineage.get("to_geo_version_id")
        if from_id == to_id:
            continue
        from_fingerprint, to_fingerprint = verified_geometry(from_id), verified_geometry(to_id)
        if not from_fingerprint or from_fingerprint != to_fingerprint:
            failures.append((str(lineage.get("geo_lineage_id", "<unknown>")), "SAME_BOUNDARY requires identical verified package GeoJSON geometries"))
    if revisions:
        failures += _require_rows("geo_versions", versions)
        failures += _issue_failures(validate_result_geographies(revisions, versions, _rows(context, "elections")))
    for row in rows:
        rid = str(row.get("check_id", "<unknown>"))
        from_version, to_version = row.get("from_geo_version_id"), row.get("to_geo_version_id")
        if from_version is None or to_version is None:
            failures.append((rid, "boundary comparison lacks geography-version identifiers"))
            continue
        version_ids = {version.get("geo_version_id") for version in versions}
        if from_version not in version_ids or to_version not in version_ids:
            failures.append((rid, "boundary comparison references an unknown geography version"))
            continue
        direct = geographies_comparable(str(from_version), str(to_version), lineages, direct=True)
        if from_version != to_version:
            from_fingerprint, to_fingerprint = verified_geometry(from_version), verified_geometry(to_version)
            direct = direct and bool(from_fingerprint and from_fingerprint == to_fingerprint)
        harmonized = geographies_comparable(str(from_version), str(to_version), lineages, direct=False)
        computed_status = "DIRECTLY_COMPARABLE" if direct else "HARMONIZED" if harmonized else "NOT_COMPARABLE"
        status = row.get("comparison_status")
        if status != computed_status:
            failures.append((rid, f"declared comparison_status differs from computed {computed_status}"))
        if status not in {"DIRECTLY_COMPARABLE", "HARMONIZED", "PARTIAL"}:
            failures.append((rid, "boundary comparison is not admissible"))
        if status != "DIRECTLY_COMPARABLE" and not (row.get("method") and row.get("source_id")):
            failures.append((rid, "non-direct boundary comparison lacks method or source"))
    evidence = {"checks": rows, "revisions": revisions, "geo_versions": versions, "geo_lineages": lineages, "materialized_geography": materialized, "official_sources": official_sources, "verified_geometry_fingerprints": geometry_fingerprints}
    return _gate("BOUNDARY_COMPATIBLE", evidence, failures, "All results use election-day geography versions and all comparisons are admissible.")


def _lineage(context: PublicationContext) -> GateResult:
    rows = _checks(context, "party_lineage_reviews")
    versions = _rows(context, "party_versions")
    lineages = _rows(context, "party_lineages")
    affiliations = _rows(context, "party_affiliations")
    failures = _require_rows("party_versions", versions)
    failures += _issue_failures(validate_party_history(versions, lineages, affiliations))
    reviews_by_lineage: dict[Any, list[Mapping[str, Any]]] = {}
    for row in rows:
        reviews_by_lineage.setdefault(row.get("lineage_id"), []).append(row)
    for lineage in lineages:
        lineage_id = lineage.get("lineage_id")
        reviews = reviews_by_lineage.get(lineage_id, [])
        if len(reviews) != 1:
            failures.append((str(lineage_id), "used party lineage must have exactly one human review"))
    for row in rows:
        rid = str(row.get("lineage_id", "<unknown>"))
        if not row.get("reviewed_by") or _as_date(row.get("reviewed_at")) is None or not row.get("source_id"):
            failures.append((rid, "used party lineage lacks traceable human review"))
        if row.get("lineage_id") not in {lineage.get("lineage_id") for lineage in lineages}:
            failures.append((rid, "party lineage review does not reference an inspected lineage"))
    evidence = {"versions": versions, "lineages": lineages, "affiliations": affiliations, "reviews": rows}
    return _gate("PARTY_LINEAGE_REVIEWED", evidence, failures, "Party versions and affiliations are temporally valid, and every used lineage has one traceable human review.")


def _source_conflicts(context: PublicationContext) -> GateResult:
    observations = _rows(context, "source_observations")
    resolutions = _checks(context, "source_conflict_checks")
    failures: list[tuple[str, str]] = []
    grouped: dict[tuple[Any, Any], list[Mapping[str, Any]]] = {}
    for index, row in enumerate(observations):
        rid = str(row.get("observation_id", index))
        if not row.get("source_id") or row.get("subject_id") is None or not row.get("field") or "normalized_value" not in row:
            failures.append((rid, "source observation lacks subject, field, normalized value, or source"))
            continue
        grouped.setdefault((row.get("subject_id"), row.get("field")), []).append(row)
    resolution_by_key: dict[tuple[Any, Any], list[Mapping[str, Any]]] = {}
    for row in resolutions:
        resolution_by_key.setdefault((row.get("subject_id"), row.get("field")), []).append(row)
    conflicts: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        values = {json.dumps(_canonical(row.get("normalized_value")), ensure_ascii=False, sort_keys=True) for row in rows}
        if len(values) <= 1:
            continue
        subject_id, field = key
        conflicts.append({"subject_id": subject_id, "field": field, "observations": rows})
        matches = resolution_by_key.get(key, [])
        if len(matches) != 1:
            failures.append((f"{subject_id}:{field}", "detected source conflict must have exactly one resolution record"))
            continue
        resolution = matches[0]
        if resolution.get("resolution_status") not in {"RESOLVED", "EXPOSED"} or not resolution.get("source_id") or not resolution.get("justification"):
            failures.append((str(resolution.get("check_id", f"{subject_id}:{field}")), "source conflict is not resolved or exposed with sourced justification"))
    evidence = {"observations": observations, "detected_conflicts": conflicts, "resolutions": resolutions}
    return _gate("SOURCE_CONFLICTS_RESOLVED_OR_EXPOSED", evidence, failures, "Source values were compared and every detected conflict is resolved or explicitly exposed.")


def _metrics(context: PublicationContext) -> GateResult:
    rows = _rows(context, "reconciliations")
    failures = _require_rows("reconciliations", rows) + _issue_failures(validate_rows("fact_result_reconciliation", rows))
    package_rows, binding_failures = _bind_contract_tables(
        context, {"reconciliations": ("fact_result_reconciliation", rows)}
    )
    failures += binding_failures
    portability = _checks(context, "source_portability")
    metric_evidence_root = context.evidence_root
    portable_manager: Any = None
    if portability:
        from morocco_elections.warehouse.portability import SourceEvidenceError, portable_evidence_root

        required_source_ids = {
            str(row.get("source_id")) for row in rows if row.get("source_id") is not None
        }
        required_source_ids.add("TAFRA_COMMUNAL_ELECTED_2015")
        try:
            portable_manager = portable_evidence_root(
                portability,
                required_source_ids,
                package_root=context.package_root,
                repository_root=context.evidence_root,
            )
            metric_evidence_root = portable_manager.__enter__()
        except SourceEvidenceError as error:
            failures.append((context.release_id, str(error)))
            metric_evidence_root = None
    manifest = metric_evidence_root / "metadata/source_manifest.json" if metric_evidence_root else None
    if manifest is not None and manifest.is_file():
        from morocco_elections.warehouse.reconciliation import derive_reconciliation_matrix

        root, relative = context.package_root, context.package_database_path
        report: dict[str, Any] = {}
        expected: list[dict[str, Any]] = []
        if root is None or not relative:
            failures.append((context.release_id, "reconciliation matrix requires a package-rooted DuckDB database"))
        else:
            root = root.resolve()
            path = (root / relative).resolve()
            declared = {str(file.get("relative_path")): file for file in context.files}
            if root not in path.parents or not path.is_file() or sha256_file(path) != declared.get(relative, {}).get("sha256"):
                failures.append((relative, "reconciliation matrix lacks its pinned package database"))
            else:
                try:
                    connection = duckdb.connect(str(path), read_only=True)
                    try:
                        expected, report = derive_reconciliation_matrix(connection, metric_evidence_root)
                    finally:
                        connection.close()
                except (duckdb.Error, OSError, ValueError, KeyError, TypeError) as error:
                    failures.append((relative, f"cannot reproduce reconciliation matrix: {type(error).__name__}"))
        fields = [
            *TABLE_CONTRACTS["fact_result_reconciliation"]["required"],
            *OPTIONAL_FIELDS["fact_result_reconciliation"],
        ]

        def encoded(row: Mapping[str, Any]) -> str:
            projected = {field: row.get(field) for field in fields}
            for field in ("official_value", "recomputed_value", "difference", "tolerance"):
                value = projected.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    projected[field] = float(value)
            return json.dumps(
                _canonical(projected),
                ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            )

        evaluated = Counter(encoded(row) for row in rows)
        reproduced = Counter(encoded(row) for row in expected)
        for value, count in (reproduced - evaluated).items():
            row = json.loads(value)
            failures.append((str(row.get("reconciliation_id")), f"{count} source-derived reconciliation row(s) are absent or changed"))
        for value, count in (evaluated - reproduced).items():
            row = json.loads(value)
            failures.append((str(row.get("reconciliation_id")), f"{count} evaluated reconciliation row(s) are unsupported or changed"))
        evidence = {
            "reconciliations": rows,
            "materialized_reconciliations": package_rows,
            "reproduced_reconciliations": expected,
            "matrix_report": report,
        }
        result = _gate(
            "METRIC_RECONCILED", evidence, failures,
            "Every applicable contest check is materialized exactly once and reproduced from pinned package facts.",
        )
        if portable_manager is not None:
            portable_manager.__exit__(None, None, None)
        return result
    mobilization_by_contest: dict[str, dict[str, Any]] = {}
    root, relative = context.package_root, context.package_database_path
    if root is not None and relative:
        root = root.resolve()
        path = (root / relative).resolve()
        declared = {str(file.get("relative_path")): file for file in context.files}
        if root in path.parents and path.is_file() and sha256_file(path) == declared.get(relative, {}).get("sha256"):
            try:
                connection = duckdb.connect(str(path), read_only=True)
                try:
                    fields = ("contest_id", "contest_seats", "registered_voters", "voters", "valid_votes", "invalid_votes", "blank_votes", "turnout_rate", "source_id")
                    for values in connection.execute(
                        "SELECT contest_id, contest_seats, registered_voters, voters, valid_votes, invalid_votes, "
                        "blank_votes, turnout_rate, source_id "
                        "FROM fact_electoral_mobilization"
                    ).fetchall():
                        fact = dict(zip(fields, values, strict=True))
                        contest_id = str(fact["contest_id"])
                        if contest_id in mobilization_by_contest:
                            failures.append((contest_id, "duplicate materialized mobilization rows make metric recomputation ambiguous"))
                        mobilization_by_contest[contest_id] = fact
                finally:
                    connection.close()
            except (duckdb.Error, OSError) as error:
                failures.append((relative, f"cannot derive metrics from materialized mobilization facts: {type(error).__name__}"))
        else:
            failures.append((relative, "metric derivation lacks a pinned package fact database"))
    else:
        failures.append((context.release_id, "metric derivation requires a package fact database"))
    official_sources = _rows(context, "official_sources")
    sources_by_id = {row.get("source_id"): row for row in official_sources}
    referenced_ids = {row.get("source_id") for row in rows if row.get("source_id") is not None}
    referenced_sources = [row for row in official_sources if row.get("source_id") in referenced_ids]
    if context.evidence_root is None:
        failures.append((context.release_id, "evidence_root is required to verify reconciliation source bytes"))
    else:
        from morocco_elections.warehouse.evidence import validate_official_source_registry

        failures += _issue_failures(
            validate_official_source_registry(context.evidence_root, {"sources": referenced_sources})
        )
    for row in rows:
        status, rid = row.get("validation_status"), str(row.get("reconciliation_id", "<unknown>"))
        source = sources_by_id.get(row.get("source_id"))
        if source is None or source.get("verification_status") != "VERIFIED_AUTHORITY_AND_BYTES":
            failures.append((rid, "official reconciliation value lacks a registry source with verified local bytes"))
        tolerance = row.get("tolerance")
        if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or not 0 <= tolerance < float("inf"):
            failures.append((rid, "tolerance must be a finite non-negative number"))
            continue
        derived = compare(str(row.get("contest_id")), str(row.get("metric")), row.get("official_value"), row.get("recomputed_value"), float(tolerance))
        if status != derived.validation_status:
            failures.append((rid, f"declared validation_status differs from recomputed {derived.validation_status}"))
        if row.get("difference") != derived.difference:
            failures.append((rid, f"declared difference differs from recomputed {derived.difference!r}"))
        if derived.validation_status == "FAIL":
            failures.append((rid, "metric reconciliation failed"))
        if status == "NOT_COMPUTABLE" and not row.get("explanation"):
            failures.append((rid, "NOT_COMPUTABLE reconciliation lacks an explanation"))
        if status != "NOT_COMPUTABLE" and row.get("not_computable_reason") is not None:
            failures.append((rid, "computable reconciliation must not declare a not-computable reason"))
        metric = row.get("metric")
        if metric == "turnout_rate":
            fact = mobilization_by_contest.get(str(row.get("contest_id")))
            if fact is None:
                failures.append((rid, "turnout rate lacks its materialized mobilization fact"))
                continue
            registered, voters = fact["registered_voters"], fact["voters"]
            expected = None if registered in (None, 0) or voters is None else float(voters) / float(registered)
            if row.get("source_id") != fact["source_id"] or row.get("official_value") != fact["turnout_rate"]:
                failures.append((rid, "official turnout rate differs from the sourced materialized mobilization fact"))
            if row.get("recomputed_value") != expected:
                failures.append((rid, "declared recomputed turnout rate differs from the package fact derivation"))
            if status == "NOT_COMPUTABLE":
                reason = "MOBILIZATION_FIELDS_MISSING" if expected is None else "OFFICIAL_TURNOUT_MISSING"
                if row.get("not_computable_reason") != reason:
                    failures.append((rid, f"not-computable turnout reason differs from source-derived reason {reason}"))
        elif metric == "ballot_categories_vs_voters":
            fact = mobilization_by_contest.get(str(row.get("contest_id")))
            if fact is None:
                failures.append((rid, "ballot accounting lacks its materialized mobilization fact"))
                continue
            if row.get("source_id") != fact["source_id"] or row.get("official_value") != fact["voters"]:
                failures.append((rid, "official voter total differs from the sourced materialized mobilization fact"))
            components = ("voters", "valid_votes", "invalid_votes", "blank_votes")
            reason = "BALLOT_COMPONENTS_MISSING" if any(fact[name] is None for name in components) else "BALLOT_TAXONOMY_UNVERIFIED"
            if row.get("recomputed_value") is not None or status != "NOT_COMPUTABLE" or row.get("not_computable_reason") != reason:
                failures.append((rid, f"ballot accounting must remain NOT_COMPUTABLE with source-derived reason {reason}"))
        elif metric in {"party_votes_vs_valid_votes", "allocated_seats_vs_contest_seats"}:
            reason = "PARTY_UNIVERSE_UNVERIFIED" if metric == "party_votes_vs_valid_votes" else "SEAT_UNIVERSE_UNVERIFIED"
            fact = mobilization_by_contest.get(str(row.get("contest_id")))
            if fact is None:
                failures.append((rid, "party or seat accounting lacks its materialized mobilization fact"))
                continue
            official_field = "valid_votes" if metric == "party_votes_vs_valid_votes" else "contest_seats"
            if row.get("source_id") != fact["source_id"] or row.get("official_value") != fact[official_field]:
                failures.append((rid, f"official {official_field} differs from the sourced materialized mobilization fact"))
            if row.get("recomputed_value") is not None or status != "NOT_COMPUTABLE" or row.get("not_computable_reason") != reason:
                failures.append((rid, "party or seat detail cannot pass without a verified external expected-identifier universe"))
        elif status != "NOT_COMPUTABLE" or row.get("not_computable_reason") != "UNSUPPORTED_METRIC":
            failures.append((rid, "metric has no supported package-fact derivation and cannot pass"))
    required_metrics = {
        "turnout_rate", "ballot_categories_vs_voters",
        "party_votes_vs_valid_votes", "allocated_seats_vs_contest_seats",
    }
    declared_by_contest: dict[str, Counter[str]] = {}
    for row in rows:
        contest_id = str(row.get("contest_id"))
        declared_by_contest.setdefault(contest_id, Counter())[str(row.get("metric"))] += 1
    for contest in _rows(context, "contests"):
        contest_id = str(contest.get("contest_id"))
        declared = declared_by_contest.get(contest_id, Counter())
        for metric in sorted(required_metrics):
            if declared[metric] != 1:
                failures.append((f"{contest_id}:{metric}", "every contest requires exactly one applicable reconciliation status"))
    evidence = {"reconciliations": rows, "materialized_reconciliations": package_rows, "mobilization_facts": mobilization_by_contest, "official_sources": referenced_sources}
    return _gate("METRIC_RECONCILED", evidence, failures, "Every applicable metric is sourced and passed or is explicitly not computable.")


def _candidacy_seats(context: PublicationContext) -> GateResult:
    lists = _rows(context, "candidacy_lists")
    candidates = _rows(context, "candidates")
    allocations = _rows(context, "seat_allocations")
    categories = _rows(context, "seat_categories")
    failures = _require_rows("candidacy_lists", lists) + _require_rows("candidates", candidates)
    failures += _require_rows("seat_allocations", allocations) + _require_rows("seat_categories", categories)
    failures += _issue_failures(
        validate_candidacies_and_seats(
            lists, candidates, allocations, _rows(context, "contests"), _rows(context, "legal_regimes"), categories
        )
    )
    evidence = [lists, candidates, allocations, categories]
    return _gate("CANDIDACY_AND_SEATS_VALIDATED", evidence, failures, "Every candidacy and seat allocation is linked and its official/recomputed status is consistent.")


def _analytic_admissibility(context: PublicationContext) -> GateResult:
    rows = _rows(context, "metric_validations")
    failures = _require_rows("metric_validations", rows) + _issue_failures(validate_rows("fact_metric_validation", rows))
    for row in rows:
        rid = str(row.get("metric_validation_id", "<unknown>"))
        failed = row.get("failed_preconditions", [])
        if not isinstance(failed, list):
            failures.append((rid, "failed_preconditions must be an inspectable list"))
        elif row.get("metric_status") == "COMPUTED" and (failed or row.get("coverage_status") != "COMPLETE"):
            failures.append((rid, "a computed metric must have complete coverage and no failed precondition"))
        elif row.get("metric_status") == "NOT_COMPUTED" and not failed:
            failures.append((rid, "a non-computed metric must expose at least one failed precondition"))
        if not row.get("limitations"):
            failures.append((rid, "metric limitations must be disclosed"))
    return _gate("ANALYTIC_METRICS_ADMISSIBLE", rows, failures, "Every analytic metric is computed only after its declared preconditions pass.")


def _coverage(context: PublicationContext) -> GateResult:
    rows = list(context.coverage_matrix)
    failures = _require_rows("coverage_matrix", rows) + _issue_failures(validate_coverage_matrix(rows))
    by_scope = {str(row.get("scope_id", "")).upper(): row for row in rows}
    scopes = set(by_scope)
    for dimension in DIMENSIONS:
        if dimension not in scopes:
            failures.append((dimension, "coverage dimension is missing"))
    observations = _rows(context, "coverage_observations")
    computed = coverage_report(observations, _rows(context, "coverage_universes"), _rows(context, "coverage_universe_members"))
    for report in computed:
        dimension = report["coverage_dimension"]
        declared = by_scope.get(dimension)
        if declared is None:
            continue
        expected = {
            "universe_ids_json": json.dumps(
                sorted(
                    report["universe_id"]
                    if isinstance(report["universe_id"], list)
                    else [report["universe_id"]]
                    if report["universe_id"]
                    else []
                ),
                separators=(",", ":"),
            ),
            "acquired": len(report["covered_ids"]) + len(report["unexpected_ids"]) + len(report["non_comparable_ids"]) + len(report["redistribution_forbidden_ids"]) + report["unidentified_observations"],
            "expected": report["denominator"] or 0,
            "covered": len(report["covered_ids"]),
            "missing": len(report["missing_ids"]),
            "non_comparable": len(report["non_comparable_ids"]) + report["unidentified_observations"],
            "redistribution_forbidden": len(report["redistribution_forbidden_ids"]),
            "status": report["status"],
        }
        for field, value in expected.items():
            if declared.get(field) != value:
                failures.append((dimension, f"declared {field}={declared.get(field)!r} differs from recomputed {value!r}"))
    evidence = {"declared": rows, "computed": computed, "observations": observations}
    return _gate("COVERAGE_DISCLOSED", evidence, failures, "All six coverage dimensions match identifier-level recomputation.")


def _uncertainty(context: PublicationContext) -> GateResult:
    rows = _checks(context, "claim_reviews")
    failures = _require_rows("claim_reviews", rows)
    review_by_path: dict[str, Mapping[str, Any]] = {}
    files_by_path = {str(row.get("relative_path")): row for row in context.files}
    for row in rows:
        rid = str(row.get("relative_path", "<unknown>"))
        if rid in review_by_path:
            failures.append((rid, "claim review must be unique per publication file"))
        review_by_path[rid] = row
        applicable = row.get("uncertainty_applicable")
        if not isinstance(applicable, bool):
            failures.append((rid, "uncertainty_applicable must be explicitly true or false"))
        if applicable is True and not row.get("uncertainty_disclosure"):
            failures.append((rid, "applicable uncertainty is not disclosed"))
        file_row = files_by_path.get(rid)
        if file_row is not None and row.get("file_sha256") != file_row.get("sha256"):
            failures.append((rid, "claim review is linked to the wrong file SHA-256"))
        if not row.get("evidence_id") or not row.get("reviewed_at") or not (
            row.get("reviewed_by") or row.get("review_method")
        ):
            failures.append((rid, "claim and uncertainty review is not traceable"))
    for file_row in context.files:
        rid, claim_class = str(file_row.get("relative_path", "<unknown>")), file_row.get("claim_class")
        review = review_by_path.get(rid)
        if review is None:
            failures.append((rid, "publication file lacks a claim and uncertainty review"))
        elif claim_class in {"PREDICTION", "CAUSAL"} and review.get("uncertainty_applicable") is not True:
            failures.append((rid, f"{claim_class} output must disclose uncertainty"))
    return _gate("UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE", rows, failures, "Every applicable uncertainty has a disclosure.")


def _privacy(context: PublicationContext) -> GateResult:
    rows = _checks(context, "privacy_reviews")
    required = {str(row.get("relative_path")) for row in context.files}
    failures = _require_rows("privacy_reviews", rows)
    as_of = _as_date(context.as_of_date)
    reviews_by_path: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        rid = str(row.get("relative_path", "<unknown>"))
        reviews_by_path.setdefault(rid, []).append(row)
        reviewed_at = _as_date(row.get("reviewed_at"))
        if row.get("decision") != "PASS" or not row.get("reviewed_by") or reviewed_at is None:
            failures.append((rid, "privacy review is not a traceable PASS"))
        elif as_of is not None and reviewed_at > as_of:
            failures.append((rid, "privacy review occurred after release as_of_date"))
        if rid not in required:
            failures.append((rid, "privacy review does not reference a public-package file"))
        else:
            file_row = next(item for item in context.files if str(item.get("relative_path")) == rid)
            if row.get("file_sha256") != file_row.get("sha256"):
                failures.append((rid, "privacy review is linked to the wrong file SHA-256"))
            if not row.get("evidence_id"):
                failures.append((rid, "privacy review lacks an inspected evidence identifier"))
    for file_row in context.files:
        rid = str(file_row.get("relative_path"))
        if file_row.get("privacy_review_required") is not True:
            failures.append((rid, "caller-supplied privacy-review exemptions are forbidden"))
        count = len(reviews_by_path.get(rid, []))
        if count != 1:
            failures.append((rid, f"public-package file must have exactly one privacy review, observed {count}"))
    return _gate(
        "PRIVACY_REVIEW_PASSED",
        {"required": sorted(required), "reviews": rows},
        failures,
        "Every public-package file has exactly one traceable privacy PASS no later than as_of_date.",
    )


def _claims(context: PublicationContext) -> GateResult:
    rows = list(context.files)
    failures = _require_rows("publication_files", rows) + _issue_failures(validate_rows("publication_file", rows))
    reviews = {str(row.get("relative_path")): row for row in _checks(context, "claim_reviews")}
    for row in rows:
        rid = str(row.get("relative_path", "<unknown>"))
        review = reviews.get(rid)
        if row.get("claim_class") == "OBSERVED_FACT" and row.get("fact_status") not in {"OBSERVED", "OFFICIAL"}:
            failures.append((rid, "forecast, AI inference, or insufficiently sourced data cannot be an observed fact"))
        if review is None or review.get("claim_class") != row.get("claim_class"):
            failures.append((rid, "manifest claim_class lacks a matching file-level review"))
            continue
        if review.get("file_sha256") != row.get("sha256"):
            failures.append((rid, "claim review is linked to the wrong file SHA-256"))
        if row.get("claim_class") == "ASSOCIATION" and not review.get("ecological_inference_warning"):
            failures.append((rid, "territorial association lacks an ecological-inference warning"))
        if row.get("claim_class") == "CAUSAL" and not (
            review.get("identification_card_status") == "VALIDATED" and review.get("identification_card_id")
        ):
            failures.append((rid, "causal claim lacks a validated identification card"))
        if review.get("automatic_fraud_inference") is True:
            failures.append((rid, "statistical signals cannot automatically produce a fraud conclusion"))
    return _gate("CLAIM_CLASS_DECLARED", rows, failures, "Every published file has an admissible claim class.")


def _redistribution(context: PublicationContext) -> GateResult:
    rows = list(context.files)
    failures = _require_rows("publication_files", rows) + _issue_failures(validate_rows("publication_file", rows))
    reviews = _checks(context, "license_reviews")
    failures += _require_rows("license_reviews", reviews)
    as_of = _as_date(context.as_of_date)
    file_paths = {str(row.get("relative_path")) for row in rows}
    reviews_by_path: dict[str, list[Mapping[str, Any]]] = {}
    for review in reviews:
        rid = str(review.get("relative_path", "<unknown>"))
        reviews_by_path.setdefault(rid, []).append(review)
        reviewed_at = _as_date(review.get("reviewed_at"))
        if (
            review.get("decision") != "REDISTRIBUTABLE"
            or not review.get("legal_basis")
            or not str(review.get("evidence_url", "")).startswith(("https://", "http://"))
            or not review.get("reviewed_by")
            or reviewed_at is None
        ):
            failures.append((rid, "license review is not a traceable REDISTRIBUTABLE decision"))
        elif as_of is not None and reviewed_at > as_of:
            failures.append((rid, "license review occurred after release as_of_date"))
        if rid not in file_paths:
            failures.append((rid, "license review does not reference a public-package file"))
        else:
            file_row = next(item for item in rows if str(item.get("relative_path")) == rid)
            if review.get("file_sha256") != file_row.get("sha256"):
                failures.append((rid, "license review is linked to the wrong file SHA-256"))
            if not review.get("evidence_id") or not review.get("proof_sha256"):
                failures.append((rid, "license review lacks inspected proof linkage"))
    for row in rows:
        rid = str(row.get("relative_path", "<unknown>"))
        if row.get("license_status") != "REDISTRIBUTABLE":
            failures.append((rid, "only REDISTRIBUTABLE files may enter the public package"))
        matching = reviews_by_path.get(rid, [])
        if len(matching) != 1:
            failures.append((rid, f"public-package file must have exactly one license review, observed {len(matching)}"))
        elif matching[0].get("decision") != row.get("license_status"):
            failures.append((rid, "file license_status differs from its reviewed decision"))
    return _gate(
        "REDISTRIBUTION_PERMITTED",
        {"files": rows, "license_reviews": reviews},
        failures,
        "Every public-package file has one sourced REDISTRIBUTABLE license decision.",
    )


def _reproducible(context: PublicationContext) -> GateResult:
    rows = _checks(context, "clean_builds")
    failures = [] if len(rows) >= 2 else [("clean_builds", "at least two clean builds are required")]
    manifest_digests, build_ids, workspace_ids, source_revisions, lock_digests = set(), set(), set(), set(), set()
    root = context.package_root.resolve() if context.package_root is not None else None
    for row in rows:
        rid = str(row.get("build_id", "<unknown>"))
        if rid in build_ids:
            failures.append((rid, "clean build identifiers must be unique"))
        build_ids.add(rid)
        relative_path, expected_sha = row.get("report_path"), row.get("report_sha256")
        if root is None or not relative_path or not expected_sha:
            failures.append((rid, "a package-rooted clean-build report and its SHA-256 are required"))
            continue
        report_path = (root / str(relative_path)).resolve()
        if root not in report_path.parents or not report_path.is_file():
            failures.append((rid, "clean-build report is unsafe or missing"))
            continue
        if sha256_file(report_path) != expected_sha:
            failures.append((rid, "clean-build report SHA-256 does not match"))
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            failures.append((rid, "clean-build report is not valid UTF-8 JSON"))
            continue
        if report.get("build_id") != rid:
            failures.append((rid, "registry build_id does not match the attested build_id"))
        environment = report.get("environment")
        if not isinstance(environment, dict):
            failures.append((rid, "clean-build report lacks structured environment evidence"))
        else:
            workspace_id = environment.get("workspace_id")
            if not isinstance(workspace_id, str) or not workspace_id:
                failures.append((rid, "clean-build environment lacks a workspace identifier"))
            elif workspace_id in workspace_ids:
                failures.append((rid, "clean builds must use distinct workspace identifiers"))
            else:
                workspace_ids.add(workspace_id)
            if environment.get("source_materialization") not in {"CLEAN_CHECKOUT", "SOURCE_ARCHIVE_EXTRACTION"}:
                failures.append((rid, "source materialization does not prove an isolated clean workspace"))
            if environment.get("initial_entries") != []:
                failures.append((rid, "clean-build workspace was not empty before source materialization"))
        manifest_path = report.get("manifest_path")
        manifest_sha = report.get("manifest_sha256")
        if not isinstance(manifest_path, str) or not isinstance(manifest_sha, str):
            failures.append((rid, "clean-build report lacks a package manifest path and digest"))
        else:
            resolved_manifest = (root / manifest_path).resolve()
            if root not in resolved_manifest.parents or not resolved_manifest.is_file():
                failures.append((rid, "attested package manifest is unsafe or missing"))
            elif sha256_file(resolved_manifest) != manifest_sha:
                failures.append((rid, "attested manifest digest does not match package bytes"))
            else:
                manifest_digests.add(manifest_sha)
                try:
                    manifest_payload = json.loads(resolved_manifest.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    failures.append((rid, "attested package manifest is not valid UTF-8 JSON"))
                else:
                    manifest_files = manifest_payload.get("files") if isinstance(manifest_payload, dict) else None
                    expected_files = sorted(
                        (str(row.get("relative_path")), str(row.get("sha256"))) for row in context.files
                    )
                    actual_files = sorted(
                        (str(row.get("relative_path")), str(row.get("sha256")))
                        for row in manifest_files
                        if isinstance(row, dict)
                    ) if isinstance(manifest_files, list) else []
                    if actual_files != expected_files:
                        failures.append((rid, "attested manifest does not exactly match publication_file evidence"))
        source_revision, lock_digest = report.get("source_revision"), report.get("dependency_lock_sha256")
        if not isinstance(source_revision, str) or not source_revision:
            failures.append((rid, "source revision is missing"))
        else:
            source_revisions.add(source_revision)
        if not isinstance(lock_digest, str) or len(lock_digest) != 64 or any(char not in "0123456789abcdef" for char in lock_digest.lower()):
            failures.append((rid, "dependency lock digest is not a SHA-256"))
        else:
            lock_digests.add(lock_digest.lower())
        commands = report.get("commands")
        command_results = {row.get("name"): row for row in commands} if isinstance(commands, list) and all(isinstance(row, dict) for row in commands) else {}
        for required_command in ("tests", "validate_warehouse"):
            command = command_results.get(required_command)
            if command is None or command.get("exit_code") != 0 or not command.get("command"):
                failures.append((rid, f"clean build lacks a successful {required_command} command"))
    if len(manifest_digests) > 1:
        failures.append(("clean_builds", "clean builds produced different manifests"))
    if len(source_revisions) > 1:
        failures.append(("clean_builds", "clean builds used different source revisions"))
    if len(lock_digests) > 1:
        failures.append(("clean_builds", "clean builds used different dependency locks"))
    if len(rows) >= 2 and len(workspace_ids) != len(rows):
        failures.append(("clean_builds", "every clean build must provide a distinct structured workspace"))
    return _gate("REPRODUCIBLE_FROM_CLEAN_ENVIRONMENT", rows, failures, "Two clean builds passed and produced the same manifest.")


def _immutability(context: PublicationContext) -> GateResult:
    root = context.v15_root
    failures: list[tuple[str, str]] = []
    manifest: Any = None
    try:
        manifest_bytes = context.v15_manifest_path.read_bytes()
        observed_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        if len(manifest_bytes) != CANONICAL_MANIFEST_BYTES:
            failures.append((str(context.v15_manifest_path), "canonical V15 manifest byte length differs"))
        if observed_sha256 != CANONICAL_MANIFEST_SHA256:
            failures.append((str(context.v15_manifest_path), "canonical V15 manifest SHA-256 differs"))
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if manifest.get("release") != "V15" or manifest.get("release_version") != "15.0.0":
            failures.append((str(context.v15_manifest_path), "invalid canonical V15 manifest identity"))
        if root is not None:
            failures += _issue_failures(verify_v15_immutability(root, context.v15_manifest_path))
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError, RuntimeError) as error:
        failures.append((str(context.v15_manifest_path), f"V15 immutability manifest is unreadable or invalid: {type(error).__name__}"))
    evidence = {
        "manifest_sha256": sha256_file(context.v15_manifest_path) if context.v15_manifest_path.is_file() else None,
        "manifest": manifest,
        "root": root,
        "canonical_manifest_bytes": CANONICAL_MANIFEST_BYTES,
        "canonical_manifest_sha256": CANONICAL_MANIFEST_SHA256,
    }
    return _gate(
        "V15_IMMUTABILITY_VERIFIED",
        evidence,
        failures,
        "The embedded manifest has the canonical V15 byte identity; repository builds also verify every listed V15 artifact.",
    )


GATE_EVALUATORS: Mapping[str, Callable[[PublicationContext], GateResult]] = {
    "SEMANTIC_FACTS_VALIDATED": _semantic_facts,
    "LEGAL_REGIME_PINNED": _legal_regime,
    "AS_OF_DATE_VALID": _as_of,
    "OFFICIAL_UNIVERSE_DECLARED": _official_universe,
    "GRAIN_COMPATIBLE": _grain,
    "SOURCE_CONFLICTS_RESOLVED_OR_EXPOSED": _source_conflicts,
    "METRIC_RECONCILED": _metrics,
    "COVERAGE_DISCLOSED": _coverage,
    "UNCERTAINTY_DISCLOSED_WHEN_APPLICABLE": _uncertainty,
    "PRIVACY_REVIEW_PASSED": _privacy,
    "CLAIM_CLASS_DECLARED": _claims,
    "REDISTRIBUTION_PERMITTED": _redistribution,
}
GATE_REGISTRY = build_registry(GATE_EVALUATORS)


def evaluate_publication_gates(context: PublicationContext) -> list[GateResult]:
    """Evaluate every mandatory gate from inspectable inputs in fixed order."""
    if not isinstance(context, PublicationContext):
        raise TypeError("publication gates require PublicationContext evidence; caller-supplied gate booleans are forbidden")
    return [gate.evaluate(context) for gate in GATE_REGISTRY]


def validate_publication(context: PublicationContext) -> dict[str, Any]:
    """Fail closed: status is derived solely from artifact checks and gate evaluators."""
    if not isinstance(context, PublicationContext):
        raise TypeError("validate_publication accepts only a PublicationContext; boolean gate maps are forbidden")
    issues: list[ValidationIssue] = []
    if context.package_root is None:
        issues.append(ValidationIssue("PACKAGE_ROOT_REQUIRED", "release", context.release_id, "publication readiness requires an inspectable package root"))
    for row in context.files:
        rid = str(row.get("relative_path", "<unknown>"))
        if row.get("license_status") != "REDISTRIBUTABLE":
            issues.append(ValidationIssue("FILE_NOT_REDISTRIBUTABLE", "publication_file", rid, "file cannot be included in a public release"))
        if context.package_root is not None:
            root, path = context.package_root.resolve(), (context.package_root / rid).resolve()
            if root not in path.parents or not path.is_file():
                issues.append(ValidationIssue("PUBLICATION_FILE_MISSING", "publication_file", rid, "manifest file absent"))
            elif sha256_file(path) != row.get("sha256"):
                issues.append(ValidationIssue("PUBLICATION_CHECKSUM_MISMATCH", "publication_file", rid, "published bytes differ from manifest"))
    gates = evaluate_publication_gates(context)
    for gate in gates:
        if gate.status != "PASS":
            issues.append(ValidationIssue("PUBLICATION_GATE_FAILED", "release", gate.gate_id, gate.justification))
    return {
        "release_id": context.release_id,
        "publication_status": "PUBLICATION_READY" if not issues else "NOT_PUBLICATION_READY",
        "issues": [issue.__dict__ for issue in issues],
        "gates": [gate.as_dict() for gate in gates],
        "gate_results": [gate.as_contract_row(context.release_id) for gate in gates],
    }
