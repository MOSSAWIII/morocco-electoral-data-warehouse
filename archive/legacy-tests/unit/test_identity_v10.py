from __future__ import annotations

import unicodedata

import pytest

from morocco_elections.domains.identity import local_person_id, normalize_person_name, person_name_match_key


def test_arabic_is_not_destroyed_by_normalization() -> None:
    assert normalize_person_name("مُحَمَّد الـحمامي") == "محمد الحمامي"
    assert person_name_match_key("مُحَمَّد الـحمامي") == "محمد الحمامي"


def test_french_composed_and_decomposed_forms_match() -> None:
    composed = "Élodie D’Arc"
    decomposed = unicodedata.normalize("NFD", composed)
    assert person_name_match_key(composed) == person_name_match_key(decomposed) == "elodie d arc"


def test_format_controls_and_typographic_punctuation_do_not_change_key() -> None:
    assert person_name_match_key("\u200fBen–M’sik") == person_name_match_key("Ben-M'sik")


def test_person_id_is_stable_but_scoped() -> None:
    args = ("SRC", 10, 20, "PI", "محمد الحمامي")
    assert local_person_id(*args) == local_person_id(*args)
    assert local_person_id(*args) != local_person_id("SRC", 10, 21, "PI", "محمد الحمامي")
    assert local_person_id(*args) != local_person_id("SRC", 10, 20, "PAM", "محمد الحمامي")


def test_empty_normalized_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        local_person_id("SRC", 10, 20, "PI", " ــ ")
