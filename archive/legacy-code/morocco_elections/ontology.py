from __future__ import annotations

import json
from pathlib import Path

from morocco_elections.config import PROJECT_ROOT


ONTOLOGY_PATH = PROJECT_ROOT / "metadata" / "ontology_v1.json"
MATURITY_LEVELS = {"CURRENT", "PARTIAL", "PLANNED"}


def load_ontology(path: str | Path | None = None) -> dict:
    ontology_path = Path(path) if path else ONTOLOGY_PATH
    return json.loads(ontology_path.read_text(encoding="utf-8"))


def validate_ontology(ontology: dict) -> list[str]:
    errors: list[str] = []
    if ontology.get("schema_version") != 1 or ontology.get("ontology_version") != "1.3.0":
        errors.append("version de l'ontologie invalide")
    if ontology.get("baseline_release") != "V14.1":
        errors.append("la baseline de l'ontologie doit être V14.1")
    if not ontology.get("principles") or set(ontology.get("maturity_levels", {})) != MATURITY_LEVELS:
        errors.append("principes ou niveaux de maturité incomplets")

    dimensions = ontology.get("dimensions", [])
    dimension_ids = _unique_ids(dimensions, "dimension_id", "dimension", errors)
    canonical_ids = [item.get("canonical_id") for item in dimensions if isinstance(item, dict)]
    if len(canonical_ids) != len(set(canonical_ids)) or any(not item for item in canonical_ids):
        errors.append("canonical_id vide ou dupliqué")
    for item in dimensions:
        if not isinstance(item, dict):
            continue
        _require(item, {"dimension_id", "canonical_id", "definition", "maturity", "v12_tables", "identity_rule", "temporal_fields"}, "dimension", errors)
        if item.get("maturity") not in MATURITY_LEVELS:
            errors.append(f"dimension {item.get('dimension_id')}: maturité invalide")
        if not isinstance(item.get("v12_tables"), list) or not isinstance(item.get("temporal_fields"), list):
            errors.append(f"dimension {item.get('dimension_id')}: listes invalides")

    facts = ontology.get("facts", [])
    fact_ids = _unique_ids(facts, "fact_id", "fait", errors)
    target_tables = [item.get("target_table") for item in facts if isinstance(item, dict)]
    if len(target_tables) != len(set(target_tables)) or any(not item for item in target_tables):
        errors.append("target_table vide ou dupliquée")
    for item in facts:
        if not isinstance(item, dict):
            continue
        _require(
            item,
            {"fact_id", "target_table", "grain", "dimensions", "maturity", "v12_tables", "observed_measures", "derived_measures", "rules"},
            "fait",
            errors,
        )
        if item.get("maturity") not in MATURITY_LEVELS:
            errors.append(f"fait {item.get('fact_id')}: maturité invalide")
        if not item.get("grain"):
            errors.append(f"fait {item.get('fact_id')}: grain vide")
        unknown = set(item.get("dimensions", [])) - dimension_ids
        if unknown:
            errors.append(f"fait {item.get('fact_id')}: dimensions inconnues {sorted(unknown)}")
        overlap = set(item.get("observed_measures", [])) & set(item.get("derived_measures", []))
        if overlap:
            errors.append(f"fait {item.get('fact_id')}: mesures observées/dérivées confondues {sorted(overlap)}")

    crosswalk = ontology.get("crosswalk_contract", {})
    required_crosswalk = {"entity_type", "source_system", "source_record_id", "canonical_id", "evidence_id", "review_status"}
    if not required_crosswalk <= set(crosswalk.get("required_fields", [])) or not crosswalk.get("primary_key") or not crosswalk.get("rules"):
        errors.append("contrat de crosswalk incomplet")

    relation_nodes = dimension_ids | fact_ids | {"any_fact"}
    _unique_ids(ontology.get("relations", []), "relation_id", "relation", errors)
    for relation in ontology.get("relations", []):
        if not isinstance(relation, dict):
            continue
        _require(relation, {"relation_id", "from", "to", "cardinality", "join_key", "temporal"}, "relation", errors)
        unknown = {relation.get("from"), relation.get("to")} - relation_nodes
        if unknown:
            errors.append(f"relation {relation.get('relation_id')}: nœuds inconnus {sorted(unknown)}")
        if not isinstance(relation.get("temporal"), bool):
            errors.append(f"relation {relation.get('relation_id')}: temporal doit être booléen")

    _unique_ids(ontology.get("cubes", []), "cube_id", "cube", errors)
    for cube in ontology.get("cubes", []):
        if not isinstance(cube, dict):
            continue
        _require(cube, {"cube_id", "grain", "facts", "measures"}, "cube", errors)
        if not cube.get("grain") or not cube.get("measures"):
            errors.append(f"cube {cube.get('cube_id')}: grain ou mesures vides")
        unknown = set(cube.get("facts", [])) - fact_ids
        if unknown:
            errors.append(f"cube {cube.get('cube_id')}: faits inconnus {sorted(unknown)}")

    if not ontology.get("forbidden_joins"):
        errors.append("les jointures interdites doivent être explicites")
    return errors


def _unique_ids(records: object, key: str, label: str, errors: list[str]) -> set[str]:
    if not isinstance(records, list) or not records:
        errors.append(f"liste {label} vide ou invalide")
        return set()
    values = [item.get(key) for item in records if isinstance(item, dict)]
    if len(values) != len(records) or any(not isinstance(value, str) or not value for value in values):
        errors.append(f"{label}: identifiant vide ou enregistrement invalide")
    if len(values) != len(set(values)):
        errors.append(f"{label}: identifiant dupliqué")
    return {value for value in values if isinstance(value, str) and value}


def _require(record: dict, required: set[str], label: str, errors: list[str]) -> None:
    missing = required - record.keys()
    if missing:
        errors.append(f"{label} {record}: champs absents {sorted(missing)}")
