from __future__ import annotations

import json
import csv as csv_module
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from morocco_elections.quality.v15.logical import csv_digest, duckdb_digest, parquet_digest
from morocco_elections.v15.schema import TABLE_SPECS, all_table_contracts


def _arrow_type(name: str) -> pa.DataType:
    return {
        "VARCHAR": pa.string(), "BIGINT": pa.int64(), "DOUBLE": pa.float64(),
        "BOOLEAN": pa.bool_(), "DATE": pa.date32(),
    }[name]


def validate_schema(root: Path, manifest: dict) -> list[str]:
    errors: list[str] = []
    tables = manifest.get("tables", [])
    by_name = {row.get("table_name"): row for row in tables}
    expected = [item.name for item in TABLE_SPECS]
    if list(by_name) != expected:
        errors.append("schema: ordre ou ensemble des tables différent du registre canonique")
    if manifest.get("core_tables") != [item.name for item in TABLE_SPECS if item.category == "CORE"]:
        errors.append("schema: noyau CORE invalide")
    if tables != all_table_contracts():
        errors.append("schema: manifeste différent du contrat V15 versionné")
    database = root / "morocco_elections_v15.duckdb"
    if not database.is_file():
        return errors + ["schema: base DuckDB absente"]
    connection = duckdb.connect(str(database), read_only=True)
    try:
        duck_tables = {
            row[0] for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'"
            ).fetchall()
        }
        if set(expected) | {"warehouse_metadata"} != duck_tables:
            errors.append("schema: tables DuckDB différentes du manifeste")
        for name, table in by_name.items():
            parquet = root / "parquet" / f"{name}.parquet"
            csv = root / "csv" / f"{name}.csv"
            if not parquet.is_file() or not csv.is_file():
                errors.append(f"schema: formats manquants pour {name}")
                continue
            parquet_rows = pq.ParquetFile(parquet).metadata.num_rows
            csv_rows = connection.execute("SELECT count(*) FROM read_csv_auto(?, header=true)", [str(csv)]).fetchone()[0]
            duck_rows = connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            if not (parquet_rows == csv_rows == duck_rows == table["rows"]):
                errors.append(f"schema: volumes incohérents pour {name}")
            duck_columns = connection.execute(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema='main' AND table_name=? ORDER BY ordinal_position",
                [name],
            ).fetchall()
            expected_columns = [(row["name"], row["type"], "YES" if row["nullable"] else "NO") for row in table["columns"]]
            if duck_columns != expected_columns:
                errors.append(f"schema: colonnes DuckDB différentes du manifeste pour {name}")
            constraints = connection.execute(
                "SELECT constraint_type, constraint_column_names, referenced_table, referenced_column_names "
                "FROM duckdb_constraints() WHERE table_name=?",
                [name],
            ).fetchall()
            primary_keys = [tuple(row[1]) for row in constraints if row[0] == "PRIMARY KEY"]
            if primary_keys != [tuple(table["primary_key"])]:
                errors.append(f"schema: clé primaire physique différente du contrat pour {name}")
            expected_unique = [] if table["natural_key"] == table["primary_key"] else [tuple(table["natural_key"])]
            actual_unique = [tuple(row[1]) for row in constraints if row[0] == "UNIQUE"]
            if actual_unique != expected_unique:
                errors.append(f"schema: clé naturelle physique différente du contrat pour {name}")
            expected_checks = sum(len(row["checks"]) + bool(row.get("domain")) for row in table["columns"])
            expected_checks += len(table["table_checks"])
            if sum(row[0] == "CHECK" for row in constraints) != expected_checks:
                errors.append(f"schema: contraintes CHECK physiques différentes du contrat pour {name}")
            expected_foreign = {
                ((row["child_column"],), row["parent_table"], (row["parent_column"],))
                for row in manifest["relationships"] if row["child_table"] == name
            }
            actual_foreign = {
                (tuple(row[1]), row[2], tuple(row[3])) for row in constraints if row[0] == "FOREIGN KEY"
            }
            if actual_foreign != expected_foreign:
                errors.append(f"schema: clés étrangères physiques différentes du contrat pour {name}")
            with csv.open(encoding="utf-8", newline="") as stream:
                header = next(csv_module.reader(stream), [])
            expected_header = [row["name"] for row in table["columns"]]
            if header != expected_header:
                errors.append(f"schema: en-tête CSV différent du contrat pour {name}")
            parquet_schema = pq.read_schema(parquet)
            expected_parquet = pa.schema(
                [pa.field(row["name"], _arrow_type(row["type"]), nullable=row["nullable"]) for row in table["columns"]]
            )
            if not parquet_schema.equals(expected_parquet, check_metadata=False):
                errors.append(f"schema: schéma ou nullabilité Parquet différent du contrat pour {name}")
            expected_digest = manifest.get("logical_digests", {}).get(name)
            if not expected_digest:
                errors.append(f"schema: empreinte logique absente pour {name}")
            else:
                digests = {
                    "DuckDB": duckdb_digest(connection, table)[0],
                    "Parquet": parquet_digest(connection, parquet, table)[0],
                    "CSV": csv_digest(connection, csv, table)[0],
                }
                mismatches = [kind for kind, digest in digests.items() if digest != expected_digest]
                if mismatches:
                    errors.append(f"schema: contenu logique divergent pour {name}: {', '.join(mismatches)}")
    finally:
        connection.close()
    return errors
