from __future__ import annotations

import json
from pathlib import Path

import duckdb

from morocco_elections.v15.coverage import coverage_matrix
from morocco_elections.v15.queries import ANALYSES, CUBES, available_cubes, render_reference_queries
from morocco_elections.v15.schema import PARTIAL_DATE_POLICIES


def planned_observation_violations(connection: duckdb.DuckDBPyConnection) -> int:
    return connection.execute(
        "SELECT count(*) FROM fact_observation o JOIN dim_indicator i USING (indicator_id) "
        "WHERE upper(coalesce(i.collection_status, '')) LIKE '%PLANNED%' "
        "OR lower(coalesce(i.collection_status, '')) = 'not_started'"
    ).fetchone()[0]


def validate_accuracy(root: Path, manifest: dict) -> list[str]:
    errors: list[str] = []
    connection = duckdb.connect(str(root / "morocco_elections_v15.duckdb"), read_only=True)
    try:
        expected_cubes = [
            {key: value for key, value in cube.items() if key != "view_sql"}
            for cube in CUBES
        ]
        if manifest.get("cubes") != expected_cubes:
            errors.append("exactitude: contrats de cubes différents du registre canonique")
        expected_analyses = [{key: value for key, value in row.items() if key != "sql"} for row in ANALYSES]
        if manifest.get("analyses") != expected_analyses:
            errors.append("exactitude: contrats d'analyses différents du registre canonique")
        try:
            packaged_queries = (root / "queries.sql").read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"exactitude: requêtes SQL illisibles: {exc}")
        else:
            if packaged_queries != render_reference_queries():
                errors.append("exactitude: requêtes SQL différentes du registre canonique")
        bad_shares = connection.execute(
            "SELECT count(*) FROM fact_communal_election_result "
            "WHERE vote_share NOT BETWEEN 0 AND 100 OR seat_share NOT BETWEEN 0 AND 100"
        ).fetchone()[0]
        if bad_shares:
            errors.append(f"exactitude: {bad_shares} part(s) hors [0,100]")
        bad_hhi = connection.execute(
            "SELECT count(*) FROM fact_commune_election_summary WHERE hhi IS NOT NULL AND hhi NOT BETWEEN 0 AND 10000"
        ).fetchone()[0]
        if bad_hhi:
            errors.append(f"exactitude: {bad_hhi} HHI hors [0,10000]")
        bad_mobilization = connection.execute(
            "SELECT count(*) FROM fact_electoral_mobilization "
            "WHERE (voters IS NOT NULL AND registered_voters IS NOT NULL AND voters > registered_voters) "
            "OR (valid_votes IS NOT NULL AND voters IS NOT NULL AND valid_votes > voters)"
        ).fetchone()[0]
        if bad_mobilization:
            errors.append(f"exactitude: {bad_mobilization} identité(s) de mobilisation incohérente(s)")
        planned_with_facts = planned_observation_violations(connection)
        if planned_with_facts:
            errors.append(f"exactitude: {planned_with_facts} valeur(s) planifiée(s) présentée(s) comme observée(s)")
        if manifest.get("coverage_interpretation") != "UNKNOWN_WITHOUT_OFFICIAL_DENOMINATOR":
            errors.append("exactitude: couverture parlementaire non déclarée UNKNOWN")

        for cube in available_cubes():
            actual_output = [
                [row[0], row[1], row[2] == "YES"]
                for row in connection.execute(f'DESCRIBE SELECT * FROM "{cube["name"]}"').fetchall()
            ]
            if actual_output != cube["output_columns"]:
                errors.append(f"exactitude: schéma de sortie du cube invalide: {cube['name']}")
            count = connection.execute(f'SELECT count(*) FROM "{cube["name"]}"').fetchone()[0]
            if count == 0:
                errors.append(f"exactitude: cube AVAILABLE vide: {cube['name']}")
            violations = connection.execute(cube["reconciliation_sql"]).fetchone()[0]
            if violations:
                errors.append(f"exactitude: cube non réconcilié: {cube['name']}")

        for policy in PARTIAL_DATE_POLICIES:
            table = policy["table_name"]
            precision = policy["precision_column"]
            date_column = policy["column"]
            invalid = connection.execute(
                f'SELECT count(*) FROM "{table}" WHERE '
                f'("{date_column}" IS NULL) <> ("{precision}" IS NULL OR "{precision}" = \'UNRESOLVED\') '
                f'OR "{precision}" NOT IN (\'YEAR\', \'MONTH\', \'DAY\', \'LABEL_YEAR\', \'UNRESOLVED\')'
            ).fetchone()[0]
            if invalid:
                errors.append(f"exactitude: précision temporelle incohérente: {table}.{date_column}")
            boundary_rule = (
                f"(\"{precision}\" IN ('YEAR','LABEL_YEAR') AND "
                f"(month(\"{date_column}\")<>1 OR day(\"{date_column}\")<>1)) OR "
                f"(\"{precision}\"='MONTH' AND day(\"{date_column}\")<>1)"
                if policy["start_or_end"] == "START"
                else f"(\"{precision}\" IN ('YEAR','LABEL_YEAR') AND "
                f"(month(\"{date_column}\")<>12 OR day(\"{date_column}\")<>31)) OR "
                f"(\"{precision}\"='MONTH' AND \"{date_column}\"<>last_day(\"{date_column}\"))"
            )
            bad_boundaries = connection.execute(f'SELECT count(*) FROM "{table}" WHERE {boundary_rule}').fetchone()[0]
            if bad_boundaries:
                errors.append(f"exactitude: borne temporelle incohérente: {table}.{date_column}")

        expected_coverage = coverage_matrix(connection)
        try:
            published_coverage = json.loads((root / "coverage_matrix.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"exactitude: matrice de couverture illisible: {exc}")
        else:
            if published_coverage != expected_coverage or manifest.get("coverage_matrix") != expected_coverage:
                errors.append("exactitude: matrice de couverture différente des données")
    finally:
        connection.close()
    return errors
