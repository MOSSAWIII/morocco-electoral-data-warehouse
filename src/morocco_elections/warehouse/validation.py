from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence

from morocco_elections.warehouse.contracts import ALL_TABLE_CONTRACTS, FIELD_VOCABULARIES, VOCABULARIES


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    table: str
    record_id: str
    message: str


class WarehouseValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{i.code}[{i.table}:{i.record_id}] {i.message}" for i in issues))


def _identifier(row: Mapping[str, Any]) -> str:
    for name in ("result_id", "revision_id", "contest_id", "election_id", "geo_id", "universe_id", "id"):
        if row.get(name) is not None:
            return str(row[name])
    return "<unknown>"


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def validate_rows(table: str, rows: Iterable[Mapping[str, Any]]) -> list[ValidationIssue]:
    """Validate required fields, primary-key uniqueness and controlled values."""
    if table not in ALL_TABLE_CONTRACTS:
        return [ValidationIssue("UNKNOWN_TABLE", table, "<contract>", "table is absent from the canonical contract")]
    contract = ALL_TABLE_CONTRACTS[table]
    issues: list[ValidationIssue] = []
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        record_id = _identifier(row)
        missing = [name for name in contract["required"] if row.get(name) is None or row.get(name) == ""]
        if missing:
            issues.append(ValidationIssue("REQUIRED_FIELD_MISSING", table, record_id, ", ".join(missing)))
        key = tuple(row.get(name) for name in contract["primary_key"])
        if key in seen:
            issues.append(ValidationIssue("DUPLICATE_PRIMARY_KEY", table, record_id, repr(key)))
        seen.add(key)
        for field, vocabulary_name in FIELD_VOCABULARIES.items():
            value = row.get(field)
            if value is not None and value not in VOCABULARIES[vocabulary_name].values:
                issues.append(ValidationIssue("CONTROLLED_VOCABULARY_VIOLATION", table, record_id, f"{field}={value!r}"))
        valid_from, valid_to = _as_date(row.get("valid_from")), _as_date(row.get("valid_to"))
        if row.get("valid_from") is not None and valid_from is None:
            issues.append(ValidationIssue("INVALID_DATE", table, record_id, "valid_from is not an ISO date"))
        if row.get("valid_to") is not None and valid_to is None:
            issues.append(ValidationIssue("INVALID_DATE", table, record_id, "valid_to is not an ISO date"))
        if valid_from and valid_to and valid_from > valid_to:
            issues.append(ValidationIssue("INVALID_VALIDITY_INTERVAL", table, record_id, "valid_from is after valid_to"))
        method = row.get("identity_match_method") or row.get("matching_method")
        if table in {"fact_candidate", "bridge_person_party_affiliation"} and method == "NAME_ONLY":
            issues.append(ValidationIssue("NAME_ONLY_IDENTITY_FORBIDDEN", table, record_id, "person identity cannot rely only on name similarity"))
    return issues


def validate_semantic_consistency(
    facts: Iterable[Mapping[str, Any]],
    contests: Iterable[Mapping[str, Any]],
    elections: Iterable[Mapping[str, Any]],
    geographies: Iterable[Mapping[str, Any]],
    geo_parent_relations: Iterable[Mapping[str, Any]] = (),
) -> list[ValidationIssue]:
    """Enforce election, contest, geography, year and regional-parent invariants."""
    contest_by_id = {row["contest_id"]: row for row in contests}
    election_by_id = {row["election_id"]: row for row in elections}
    geo_by_id = {row["geo_id"]: row for row in geographies}
    relations_by_election_child: dict[tuple[Any, Any], list[Mapping[str, Any]]] = {}
    for relation in geo_parent_relations:
        relations_by_election_child.setdefault(
            (relation.get("election_id"), relation.get("child_geo_id")), []
        ).append(relation)

    def reaches_region(election_id: Any, election_date: date | None, child_id: Any, expected_region: Any) -> bool:
        current = child_id
        seen: set[Any] = set()
        while current is not None and current not in seen:
            if current == expected_region:
                return True
            seen.add(current)
            active = []
            for relation in relations_by_election_child.get((election_id, current), []):
                valid_from, valid_to = _as_date(relation.get("valid_from")), _as_date(relation.get("valid_to"))
                if election_date is not None and valid_from is not None and valid_from <= election_date and (
                    valid_to is None or election_date <= valid_to
                ):
                    active.append(relation)
            if active:
                # A materialized, election-scoped relation supersedes the immutable V15 parent.
                current = active[0].get("parent_geo_id")
            else:
                current = geo_by_id.get(current, {}).get("parent_geo_id")
        return False

    issues: list[ValidationIssue] = []
    for fact in facts:
        record_id = _identifier(fact)
        contest = contest_by_id.get(fact.get("contest_id"))
        if contest is None:
            issues.append(ValidationIssue("UNKNOWN_CONTEST", "fact", record_id, str(fact.get("contest_id"))))
            continue
        if fact.get("election_id") != contest.get("election_id"):
            issues.append(ValidationIssue("FACT_CONTEST_ELECTION_MISMATCH", "fact", record_id, "fact.election_id != contest.election_id"))
        if fact.get("geo_id") != contest.get("geo_id"):
            issues.append(ValidationIssue("FACT_CONTEST_GEO_MISMATCH", "fact", record_id, "fact.geo_id != contest.geo_id"))
        election = election_by_id.get(fact.get("election_id"))
        if election is None:
            issues.append(ValidationIssue("UNKNOWN_ELECTION", "fact", record_id, str(fact.get("election_id"))))
        election_date = None
        if election is not None:
            election_date = _as_date(election.get("election_date"))
            election_year = election.get("year") or (election_date.year if election_date else None)
            fact_year = fact.get("year")
            if fact_year is not None and election_year is not None and int(fact_year) != int(election_year):
                issues.append(ValidationIssue("FACT_ELECTION_YEAR_MISMATCH", "fact", record_id, f"{fact_year} != {election_year}"))
        geo = geo_by_id.get(fact.get("geo_id"))
        expected_region = contest.get("region_geo_id")
        if expected_region is not None:
            if geo is None:
                issues.append(ValidationIssue("UNKNOWN_GEOGRAPHY", "fact", record_id, str(fact.get("geo_id"))))
            elif geo.get("region_geo_id") != expected_region and not reaches_region(
                fact.get("election_id"), election_date, fact.get("geo_id"), expected_region
            ):
                issues.append(ValidationIssue("REGIONAL_PARENT_MISMATCH", "fact", record_id, f"expected {expected_region!r}"))
    return issues


def validate_legal_regimes(
    elections: Iterable[Mapping[str, Any]],
    regimes: Iterable[Mapping[str, Any]],
    links: Iterable[Mapping[str, Any]],
    contests: Iterable[Mapping[str, Any]] = (),
    contest_links: Iterable[Mapping[str, Any]] = (),
) -> list[ValidationIssue]:
    elections, regimes, links, contests, contest_links = list(elections), list(regimes), list(links), list(contests), list(contest_links)
    regimes_by_id = {r.get("legal_regime_id"): r for r in regimes if r.get("legal_regime_id") is not None}
    elections_by_id = {str(row.get("election_id")): row for row in elections}
    links_by_election: dict[str, list[Mapping[str, Any]]] = {}
    for link in links:
        links_by_election.setdefault(str(link.get("election_id")), []).append(link)
    issues = validate_rows("dim_legal_regime", regimes) + validate_rows("bridge_election_legal_regime", links)
    issues += validate_rows("bridge_contest_legal_regime", contest_links)
    for link in links:
        rid = f"{link.get('election_id')}:{link.get('legal_regime_id')}"
        if str(link.get("election_id")) not in elections_by_id:
            issues.append(ValidationIssue("UNKNOWN_LEGAL_LINK_ELECTION", "bridge_election_legal_regime", rid, "legal link references an unknown election"))
        if link.get("legal_regime_id") not in regimes_by_id:
            issues.append(ValidationIssue("UNKNOWN_LEGAL_LINK_REGIME", "bridge_election_legal_regime", rid, "legal link references an unknown regime"))
    for election in elections:
        if not election.get("covered", True):
            continue
        election_id = str(election["election_id"])
        election_date = _as_date(election.get("election_date"))
        applicable = []
        for link in links_by_election.get(election_id, []):
            regime = regimes_by_id.get(link.get("legal_regime_id"))
            if not regime or not election_date:
                continue
            start, end = _as_date(regime.get("valid_from")), _as_date(regime.get("valid_to"))
            if start and start <= election_date and (end is None or election_date <= end):
                applicable.append(regime)
        if not applicable:
            issues.append(ValidationIssue("NO_APPLICABLE_LEGAL_REGIME", "dim_election", election_id, "covered election has no verifiable regime valid on election date"))
    if contests:
        contest_by_id = {row.get("contest_id"): row for row in contests}
        links_by_contest: dict[Any, list[Mapping[str, Any]]] = {}
        for link in contest_links:
            links_by_contest.setdefault(link.get("contest_id"), []).append(link)
            rid = f"{link.get('contest_id')}:{link.get('legal_regime_id')}"
            contest = contest_by_id.get(link.get("contest_id"))
            if contest is None:
                issues.append(ValidationIssue("UNKNOWN_LEGAL_LINK_CONTEST", "bridge_contest_legal_regime", rid, "legal link references an unknown contest"))
            elif contest.get("election_id") != link.get("election_id"):
                issues.append(ValidationIssue("LEGAL_LINK_ELECTION_MISMATCH", "bridge_contest_legal_regime", rid, "contest and legal link have different election_id values"))
        for contest in contests:
            contest_id = contest.get("contest_id")
            election = elections_by_id.get(str(contest.get("election_id")))
            election_date = _as_date(election.get("election_date")) if election else None
            applicable = []
            for link in links_by_contest.get(contest_id, []):
                regime = regimes_by_id.get(link.get("legal_regime_id"))
                if regime is None or election_date is None:
                    continue
                start, end = _as_date(regime.get("valid_from")), _as_date(regime.get("valid_to"))
                list_compatible = (
                    bool(link.get("classification_rule"))
                    or not contest.get("list_type")
                    or not regime.get("list_type")
                    or str(contest.get("list_type")).upper() == str(regime.get("list_type")).upper()
                )
                if start and start <= election_date and (end is None or election_date <= end) and list_compatible:
                    applicable.append(regime)
            if len(applicable) != 1:
                code = "NO_APPLICABLE_CONTEST_LEGAL_REGIME" if not applicable else "AMBIGUOUS_CONTEST_LEGAL_REGIME"
                issues.append(ValidationIssue(code, "dim_electoral_contest", str(contest_id), "covered contest must have exactly one applicable, list-compatible legal regime"))
    return issues


def validate_or_raise(issues: Sequence[ValidationIssue]) -> None:
    if issues:
        raise WarehouseValidationError(issues)
