from __future__ import annotations

from pathlib import Path

import duckdb


def validate_relationships(root: Path, manifest: dict) -> list[str]:
    errors: list[str] = []
    connection = duckdb.connect(str(root / "morocco_elections_v15.duckdb"), read_only=True)
    try:
        table_names = {table["table_name"] for table in manifest["tables"]}
        for table in manifest["tables"]:
            name = table["table_name"]
            columns = ", ".join(f'"{item}"' for item in table["natural_key"])
            duplicate = connection.execute(
                f'SELECT count(*) FROM (SELECT {columns}, count(*) n FROM "{name}" '
                f'GROUP BY {columns} HAVING n > 1)'
            ).fetchone()[0]
            if duplicate:
                errors.append(f"relations: {name} contient {duplicate} doublon(s) au grain naturel")
            for column in table["columns"]:
                if not column["nullable"]:
                    nulls = connection.execute(
                        f'SELECT count(*) FROM "{name}" WHERE "{column["name"]}" IS NULL'
                    ).fetchone()[0]
                    if nulls:
                        errors.append(f"relations: {name}.{column['name']} contient {nulls} NULL obligatoire(s)")
        for relation in manifest["relationships"]:
            child_table, child_column = relation["child_table"], relation["child_column"]
            parent_table, parent_column = relation["parent_table"], relation["parent_column"]
            orphan_count = connection.execute(
                f'SELECT count(*) FROM "{child_table}" c LEFT JOIN "{parent_table}" p '
                f'ON c."{child_column}" = p."{parent_column}" '
                f'WHERE c."{child_column}" IS NOT NULL AND p."{parent_column}" IS NULL'
            ).fetchone()[0]
            if orphan_count:
                errors.append(f"relations: {child_table}.{child_column} contient {orphan_count} orphelin(s)")
        if {"bridge_person_parliamentary_affiliation", "fact_mandate"} <= table_names:
            affiliation_outside_mandate = connection.execute(
                "SELECT count(*) FROM bridge_person_parliamentary_affiliation a "
                "JOIN fact_mandate m USING (mandate_id) "
                "WHERE a.valid_from < m.start_date "
                "OR (a.valid_to IS NOT NULL AND m.end_date IS NOT NULL AND a.valid_to > m.end_date)"
            ).fetchone()[0]
            if affiliation_outside_mandate:
                errors.append(
                    f"relations: {affiliation_outside_mandate} affiliation(s) hors de l'intervalle du mandat"
                )

        provenance_tables = {
            "fact_election_result", "fact_electoral_mobilization", "fact_mandate", "fact_observation",
            "fact_communal_election_result", "fact_commune_election_summary", "fact_parliamentary_question",
            "bridge_question_source", "sources",
        }
        if provenance_tables <= table_names:
            facts_without_source = connection.execute(
                "SELECT "
                "(SELECT count(*) FROM fact_election_result WHERE source_id IS NULL) + "
                "(SELECT count(*) FROM fact_electoral_mobilization WHERE source_id IS NULL) + "
                "(SELECT count(*) FROM fact_mandate WHERE source_id IS NULL) + "
                "(SELECT count(*) FROM fact_observation WHERE source_id IS NULL) + "
                "(SELECT count(*) FROM fact_communal_election_result WHERE source_id IS NULL) + "
                "(SELECT count(*) FROM fact_commune_election_summary WHERE source_id IS NULL) + "
                "(SELECT count(*) FROM fact_parliamentary_question q WHERE NOT EXISTS "
                " (SELECT 1 FROM bridge_question_source b WHERE b.question_id=q.question_id))"
            ).fetchone()[0]
            if facts_without_source:
                errors.append(f"relations: {facts_without_source} fait(s) CORE sans source")
            source_ids = {row[0] for row in connection.execute("SELECT source_id FROM sources").fetchall()}
            for correction in manifest.get("corrections", []):
                required = {"source_value", "published_value", "rule", "proof", "evidence_id", "source_id"}
                if not required <= correction.keys():
                    errors.append(f"relations: correction incomplète: {correction.get('correction_id')}")
                elif correction["source_id"] not in source_ids:
                    errors.append(f"relations: correction liée à une source absente: {correction.get('correction_id')}")
    finally:
        connection.close()
    return errors
