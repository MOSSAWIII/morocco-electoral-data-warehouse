from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def derive_comm2015_council_candidates(
    official_arrondissements: Iterable[Mapping[str, str]],
    observed_arrondissement_ids: Iterable[str],
    seed: Mapping[str, Any],
) -> dict[str, Any]:
    """Create review candidates, never official council identities or coverage."""
    if seed.get("election_id") != "COMM2015" or seed.get("status") != "PENDING_HUMAN_REVIEW_AND_BOUNDARY_ORDER":
        raise ValueError("candidate council seed must remain scoped and explicitly unverified")
    groups = list(seed.get("groups", []))
    codes = [str(row.get("prefecture_code")) for row in groups]
    council_ids = [str(row.get("candidate_council_id")) for row in groups]
    if (
        len(groups) != 6 or len(set(codes)) != 6 or len(set(council_ids)) != 6
        or not all(row.get("commune_name") and row.get("annex_arrondissement_count") for row in groups)
    ):
        raise ValueError("six distinct, explicit candidate council groups are required")
    for group in groups:
        order_source = group.get("urban_commune_order_source_id")
        if order_source is None:
            if group.get("urban_commune_order_number") or group.get("urban_commune_order_status"):
                raise ValueError("urban boundary order number or status cannot exist without its source")
        elif not group.get("urban_commune_order_number") or group.get("urban_commune_order_status") != "SOURCE_VERIFIED_MAP_AND_ARRONDISSEMENTS_PENDING":
            raise ValueError("urban boundary order must remain a sourced commune-perimeter candidate with maps pending")
    by_code = {str(row["prefecture_code"]): row for row in groups}
    official = list(official_arrondissements)
    official_ids = [str(row.get("geo_id")) for row in official]
    observed_ids = list(observed_arrondissement_ids)
    if (
        len(official_ids) != len(set(official_ids))
        or len(observed_ids) != len(set(observed_ids))
        or set(official_ids) != set(observed_ids)
    ):
        raise ValueError("HCP arrondissement identifiers do not exactly match observed COMM2015 identifiers")
    counts = Counter(str(row.get("prefecture_code")) for row in official)
    if set(counts) != set(by_code):
        raise ValueError("candidate council groups omit or add an HCP prefecture code")
    for code, count in counts.items():
        if count != by_code[code]["annex_arrondissement_count"]:
            raise ValueError(f"DGCL annex count differs from official HCP codes for {code}")
    if sum(counts.values()) != 41:
        raise ValueError("candidate grouping does not account for all 41 arrondissements")
    rows = [
        {
            "election_id": "COMM2015",
            "arrondissement_geo_id": row["geo_id"],
            "official_geo_code": row["official_geo_code"],
            "prefecture_code": row["prefecture_code"],
            "candidate_council_id": by_code[row["prefecture_code"]]["candidate_council_id"],
            "candidate_commune_name": by_code[row["prefecture_code"]]["commune_name"],
            "matching_method": "DOCUMENTED_CROSSWALK",
            "confidence": 0.9,
            "review_status": "PENDING_HUMAN_REVIEW_AND_BOUNDARY_ORDER",
            "legal_source_id": seed["legal_source_id"],
            "annex_source_id": seed["annex_source_id"],
            "code_source_id": seed["code_source_id"],
            "annex_pdf_page": seed["annex_pdf_page"],
            "urban_commune_order_source_id": by_code[row["prefecture_code"]].get("urban_commune_order_source_id"),
            "urban_commune_order_number": by_code[row["prefecture_code"]].get("urban_commune_order_number"),
            "urban_commune_order_status": by_code[row["prefecture_code"]].get("urban_commune_order_status"),
        }
        for row in official
    ]
    return {
        "status": "CANDIDATE_ONLY",
        "election_id": "COMM2015",
        "candidate_council_count": len(groups),
        "arrondissement_count": len(rows),
        "group_counts": dict(sorted(counts.items())),
        "urban_commune_order_source_group_count": sum(group.get("urban_commune_order_source_id") is not None for group in groups),
        "arrondissement_boundary_source_group_count": 0,
        "rows": sorted(rows, key=lambda row: row["arrondissement_geo_id"]),
        "publication_claim_allowed": False,
    }
