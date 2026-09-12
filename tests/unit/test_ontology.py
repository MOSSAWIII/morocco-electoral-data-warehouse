from __future__ import annotations

from copy import deepcopy

from morocco_elections.ontology import load_ontology, validate_ontology


def test_repository_ontology_is_valid() -> None:
    ontology = load_ontology()
    assert validate_ontology(ontology) == []
    assert len(ontology["dimensions"]) == 14
    assert len(ontology["facts"]) == 9
    assert len(ontology["cubes"]) == 7


def test_unknown_fact_dimension_is_rejected() -> None:
    ontology = deepcopy(load_ontology())
    ontology["facts"][0]["dimensions"].append("unknown_dimension")
    assert any("dimensions inconnues" in error for error in validate_ontology(ontology))


def test_observed_and_derived_measure_overlap_is_rejected() -> None:
    ontology = deepcopy(load_ontology())
    ontology["facts"][0]["derived_measures"].append("votes")
    assert any("observées/dérivées" in error for error in validate_ontology(ontology))


def test_unknown_cube_fact_is_rejected() -> None:
    ontology = deepcopy(load_ontology())
    ontology["cubes"][0]["facts"].append("unknown_fact")
    assert any("faits inconnus" in error for error in validate_ontology(ontology))
