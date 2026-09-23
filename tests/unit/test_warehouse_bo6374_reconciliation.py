from __future__ import annotations

import copy
from pathlib import Path

from morocco_elections.warehouse.bo6374_reconciliation import build_reconciliation, validate_reconciliation


ROOT = Path(__file__).resolve().parents[2]


def test_bo_tafra_reconciliation_is_complete_bijective_and_fail_closed() -> None:
    payload = build_reconciliation(ROOT)
    report = payload["report"]
    assert report["candidate_rows"] == 758
    assert report["identity_matches"] == 753
    assert report["unmatched"] == 5
    assert report["unmatched_with_verified_parent"] == 5
    assert report["ambiguous"] == 7
    assert report["exact_count_matches"] == 1
    assert report["explained_differences"] == 745
    assert report["exact_name_matches"] == 644
    assert report["fuzzy_unique_name_matches"] == 109
    matched_ids = [row["tafra_commune_id"] for row in payload["rows"] if row["tafra_commune_id"] is not None]
    assert len(matched_ids) == len(set(matched_ids)) == 753
    unmatched = [row for row in payload["rows"] if row["status"] == "UNMATCHED"]
    assert {row["warehouse_communal_parent_id"] for row in unmatched} == {
        "COMM2015-CITY:TANGER", "COMM2015-CITY:FES", "COMM2015-CITY:RABAT", "COMM2015-CITY:SALE",
        "COMM2015-CITY:CASABLANCA",
    }
    assert {row["remaining_blocker"] for row in unmatched} == {
        "TAFRA_HAS_ARRONDISSEMENT_RESULTS_BUT_NO_EQUIVALENT_CITY_COUNCIL_RESULT_ROW"
    }
    assert validate_reconciliation(payload, ROOT) == []


def test_bo_tafra_reconciliation_rejects_identifier_seat_and_source_mutations() -> None:
    payload = build_reconciliation(ROOT)
    matched_index = next(index for index, row in enumerate(payload["rows"]) if row["status"] == "EXPLAINED_DIFFERENCE")
    mutations = []
    identifier = copy.deepcopy(payload)
    identifier["rows"][matched_index]["tafra_commune_id"] += 1
    mutations.append(identifier)
    seats = copy.deepcopy(payload)
    seats["rows"][matched_index]["tafra_nSieges"] += 1
    mutations.append(seats)
    source = copy.deepcopy(payload)
    source["rows"][matched_index]["source_ids"][0] = "MUTATED"
    mutations.append(source)
    for mutation in mutations:
        codes = {issue.code for issue in validate_reconciliation(mutation, ROOT)}
        assert "BO_TAFRA_RECONCILIATION_PROTECTED_VALUE_MUTATION" in codes
    source_fingerprint = copy.deepcopy(payload)
    source_fingerprint["sources"][0]["source_id"] = "MUTATED"
    assert "BO_TAFRA_RECONCILIATION_SOURCE_MUTATION" in {
        issue.code for issue in validate_reconciliation(source_fingerprint, ROOT)
    }
