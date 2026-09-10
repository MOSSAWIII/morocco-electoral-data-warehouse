from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from morocco_elections.domains.identity.registry import (
    normalize_label,
    stable_contest_id,
    validate_registry,
)


def test_normalize_label_is_unicode_and_punctuation_safe() -> None:
    assert normalize_label("  Béni-Mellal – Khénifra ") == "beni mellal khenifra"
    assert normalize_label("Aïn-Sebaâ / Hay Mohammadi") == "ain sebaa hay mohammadi"


def test_contest_id_is_deterministic_and_scoped() -> None:
    first = stable_contest_id("LEG2021", "locale", "547")
    assert first == stable_contest_id("LEG2021", "locale", "547")
    assert first != stable_contest_id("LEG2021", "regionale", "547")
    assert first.startswith("CONTEST_LEG2021_LOCALE_")


def test_repository_registry_is_valid() -> None:
    registry = _repository_registry()
    assert validate_registry(registry) == []
    assert registry["counts"]["contests"] == 639
    assert registry["counts"]["crosswalks"] == 741
    assert registry["counts"]["crosswalks_by_entity_type"] == {
        "election": 6,
        "party_or_alliance": 176,
        "territory": 559,
    }
    assert registry["integration_authorized"] is False


def test_duplicate_contest_id_is_rejected() -> None:
    registry = _repository_registry()
    broken = deepcopy(registry)
    broken["contests"][1]["contest_id"] = broken["contests"][0]["contest_id"]
    assert any("contest_id uniques" in error for error in validate_registry(broken))


def _repository_registry() -> dict:
    path = Path(__file__).resolve().parents[2] / "metadata" / "v13_identity_registry.json"
    return json.loads(path.read_text(encoding="utf-8"))
