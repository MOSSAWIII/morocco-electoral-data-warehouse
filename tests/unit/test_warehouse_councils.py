from __future__ import annotations

import json
from pathlib import Path

import pytest

from morocco_elections.warehouse.councils import derive_comm2015_council_candidates


SEED = json.loads(
    (Path(__file__).resolve().parents[2] / "metadata/warehouse/comm2015_council_candidates.seed.json").read_text(encoding="utf-8")
)


def _official_rows() -> list[dict[str, str]]:
    return [
        {
            "geo_id": f"MA-{group['prefecture_code'][0:2]}-{group['prefecture_code'][3:6]}-01{index:02d}",
            "official_geo_code": f"{group['prefecture_code']}01.{index:02d}.",
            "prefecture_code": group["prefecture_code"],
        }
        for group in SEED["groups"]
        for index in range(1, group["annex_arrondissement_count"] + 1)
    ]


def test_council_crosswalk_is_exhaustive_but_only_a_candidate() -> None:
    rows = _official_rows()
    result = derive_comm2015_council_candidates(rows, [row["geo_id"] for row in rows], SEED)
    assert result["status"] == "CANDIDATE_ONLY"
    assert result["publication_claim_allowed"] is False
    assert (result["candidate_council_count"], result["arrondissement_count"]) == (6, 41)
    assert result["urban_commune_order_source_group_count"] == 3
    assert result["arrondissement_boundary_source_group_count"] == 0
    assert all(row["confidence"] == 0.9 and row["review_status"] == "PENDING_HUMAN_REVIEW_AND_BOUNDARY_ORDER" for row in result["rows"])


def test_council_candidate_mutations_fail_closed() -> None:
    rows = _official_rows()
    observed = [row["geo_id"] for row in rows]
    with pytest.raises(ValueError, match="do not exactly match"):
        derive_comm2015_council_candidates(rows, [*observed[:-1], "NOT_IN_HCP"], SEED)
    bad_count = {**SEED, "groups": [{**SEED["groups"][0], "annex_arrondissement_count": 5}, *SEED["groups"][1:]]}
    with pytest.raises(ValueError, match="annex count differs"):
        derive_comm2015_council_candidates(rows, observed, bad_count)
    with pytest.raises(ValueError, match="explicitly unverified"):
        derive_comm2015_council_candidates(rows, observed, {**SEED, "status": "VERIFIED"})
    overclaimed = {**SEED, "groups": [{**SEED["groups"][0], "urban_commune_order_status": "ARRONDISSEMENTS_VERIFIED"}, *SEED["groups"][1:]]}
    with pytest.raises(ValueError, match="maps pending"):
        derive_comm2015_council_candidates(rows, observed, overclaimed)
