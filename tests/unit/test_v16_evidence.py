from __future__ import annotations

import hashlib
from pathlib import Path

from morocco_elections.v16.evidence import (
    derive_contest_legal_regime_links,
    normalize_list_type,
    validate_legal_regime_seed,
    validate_official_source_registry,
)


def _source(raw_path: str, content: bytes) -> dict:
    return {
        "source_id": "S",
        "title": "Official source",
        "authority": "Official authority",
        "source_url": "https://official.example/source.pdf",
        "verification_status": "VERIFIED_AUTHORITY_AND_BYTES",
        "license_status": "UNKNOWN",
        "public_package_disposition": "METADATA_ONLY",
        "raw_path": raw_path,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _regime() -> dict:
    return {
        "legal_regime_id": "R", "valid_from": "2021-01-01", "legal_article": "84", "legal_basis": "law",
        "official_source_id": "S", "official_source_url": "https://official.example/source.pdf",
        "allocation_formula": "LARGEST_REMAINDER", "electoral_quotient_denominator": "REGISTERED_VOTERS",
        "threshold_rule": "NONE", "district_magnitude_rule": "BY_DECREE", "remainder_rule": "LARGEST_REMAINDER",
        "tie_break_rule": "YOUNGEST_THEN_LOT", "list_type": "LOCAL",
    }


def test_official_source_bytes_and_distribution_are_verified(tmp_path: Path) -> None:
    content = b"official"
    path = tmp_path / "raw/source.pdf"
    path.parent.mkdir()
    path.write_bytes(content)
    payload = {"sources": [_source("raw/source.pdf", content)]}
    assert validate_official_source_registry(tmp_path, payload) == []
    path.write_bytes(b"mutation")
    assert "SOURCE_CHECKSUM_MISMATCH" in {issue.code for issue in validate_official_source_registry(tmp_path, payload)}
    unsafe = {"sources": [{**_source("raw/source.pdf", b"mutation"), "public_package_disposition": "INCLUDE"}]}
    assert "UNLICENSED_SOURCE_INCLUDED" in {issue.code for issue in validate_official_source_registry(tmp_path, unsafe)}


def test_legal_seed_requires_structured_rules_known_sources_and_disclosed_partial_coverage() -> None:
    source_registry = {"sources": [{"source_id": "S", "verification_status": "VERIFIED_AUTHORITY_AND_BYTES"}]}
    payload = {
        "coverage_status": "PARTIAL",
        "coverage_limitation": "Only one election is encoded.",
        "legal_regimes": [_regime()],
        "election_links": [{"election_id": "E", "legal_regime_id": "R", "valid_from": "2021-01-01", "source_id": "S"}],
    }
    assert validate_legal_regime_seed(payload, source_registry) == []
    bad = {**payload, "coverage_status": "COMPLETE", "legal_regimes": [{**_regime(), "tie_break_rule": ""}]}
    codes = {issue.code for issue in validate_legal_regime_seed(bad, source_registry)}
    assert {"REQUIRED_FIELD_MISSING", "LEGAL_SEED_COVERAGE_NOT_DISCLOSED"} <= codes


def test_contest_legal_links_are_derived_only_from_explicit_source_type_rules() -> None:
    payload = {
        "legal_regimes": [_regime()],
        "contest_link_rules": [
            {"election_id": "E", "source_list_type": "locale", "legal_regime_id": "R", "source_id": "S"}
        ],
    }
    contests = [
        {"contest_id": "C1", "election_id": "E", "source_list_type": "locale"},
        {"contest_id": "C2", "election_id": "E", "source_list_type": "communal"},
    ]
    assert normalize_list_type("regional_council") == "REGIONAL"
    assert derive_contest_legal_regime_links(contests, payload) == [
        {"contest_id": "C1", "election_id": "E", "legal_regime_id": "R", "valid_from": "2021-01-01", "source_id": "S"}
    ]


def test_contest_legal_rule_rejects_ambiguous_or_incompatible_mutations() -> None:
    source_registry = {"sources": [{"source_id": "S", "verification_status": "VERIFIED_AUTHORITY_AND_BYTES"}]}
    rule = {"election_id": "E", "source_list_type": "regionale", "legal_regime_id": "R", "source_id": "S"}
    payload = {
        "coverage_status": "PARTIAL",
        "coverage_limitation": "Partial.",
        "legal_regimes": [_regime()],
        "election_links": [{"election_id": "E", "legal_regime_id": "R", "valid_from": "2021-01-01", "source_id": "S"}],
        "contest_link_rules": [rule, rule],
    }
    codes = {issue.code for issue in validate_legal_regime_seed(payload, source_registry)}
    assert {"DUPLICATE_CONTEST_LEGAL_RULE", "CONTEST_LEGAL_RULE_LIST_TYPE_MISMATCH"} <= codes


def test_legal_seed_rejects_unknown_supporting_source() -> None:
    source_registry = {"sources": [{"source_id": "S", "verification_status": "VERIFIED_AUTHORITY_AND_BYTES"}]}
    payload = {
        "coverage_status": "PARTIAL",
        "coverage_limitation": "Partial.",
        "legal_regimes": [{**_regime(), "supporting_source_ids": ["MISSING"]}],
        "election_links": [{"election_id": "E", "legal_regime_id": "R", "valid_from": "2021-01-01", "source_id": "S"}],
    }
    assert "UNKNOWN_SUPPORTING_LEGAL_SOURCE" in {
        issue.code for issue in validate_legal_regime_seed(payload, source_registry)
    }


def test_legal_seed_rejects_sources_without_locally_verified_bytes() -> None:
    source_registry = {"sources": [{"source_id": "S", "verification_status": "VERIFIED_PORTAL_NOT_ACQUIRED"}]}
    payload = {
        "coverage_status": "PARTIAL",
        "coverage_limitation": "Partial.",
        "legal_regimes": [{**_regime(), "supporting_source_ids": ["S"]}],
        "election_links": [{"election_id": "E", "legal_regime_id": "R", "valid_from": "2021-01-01", "source_id": "S"}],
        "contest_link_rules": [
            {"election_id": "E", "source_list_type": "locale", "legal_regime_id": "R", "source_id": "S"}
        ],
    }
    issues = validate_legal_regime_seed(payload, source_registry)
    assert {issue.code for issue in issues} == {"LEGAL_SOURCE_BYTES_NOT_VERIFIED"}
    assert len(issues) == 4
