from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from morocco_elections.config import PROJECT_ROOT, get_paths


EXPECTED_ROWS = 1_538
EXPECTED_TOTALS = {2015: 15_498_658, 2021: 17_983_490}
YEARS = (2015, 2021)
REQUIRED_CHECKS = {
    "file_readable",
    "provenance",
    "aggregate_only",
    "row_count",
    "unique_geo_key",
    "geographic_universe",
    "election_year",
    "registered_voters",
    "national_total",
    "optional_counts",
    "accounting_identity",
    "turnout_reconciliation",
}
DEFAULT_METADATA = PROJECT_ROOT / "metadata" / "v10qa1_electoral_denominators.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "research" / "V10QA1_ELECTORAL_DENOMINATORS.txt"
V10_REPORT = PROJECT_ROOT / "metadata" / "v10_release_report.json"
PERSONAL_FIELD_PATTERNS = (
    r"^cnie?$",
    r"^cin$",
    r"^prenom",
    r"^nom(?:_|$)",
    r"^name$",
    r"adresse",
    r"date.*naissance",
    r"birth.*date",
)
ALIASES = {
    "idCommune": ("idCommune", "id_commune", "source_geo_id", "commune_id"),
    "geo_id": ("geo_id", "canonical_geo_id"),
    "year": ("year", "annee", "année", "election_year"),
    "registered_voters": ("registered_voters", "nInscrits", "inscrits", "nombre_inscrits"),
    "voters": ("voters", "votants", "nombre_votants"),
    "valid_votes": ("valid_votes", "votes_valides", "suffrages_exprimes"),
    "invalid_votes": ("invalid_votes", "votes_invalides", "votes_nuls", "nuls"),
    "blank_votes": ("blank_votes", "votes_blancs", "blancs"),
    "turnout_rate": ("turnout_rate", "txParticipation", "taux_participation"),
}


RESEARCH_SOURCES = [
    {
        "source_id": "OFFICIAL_ELECTIONS_MA_RESULTS",
        "url": "https://www.elections.ma/elections/communales/resultats.aspx",
        "publisher": "Ministère de l'Intérieur",
        "role": "interface officielle des résultats communaux et des taux de participation",
        "finding": "Aucun export agrégé des inscrits 2015 et 2021 n'a été identifié.",
        "candidate_status": "not_found",
    },
    {
        "source_id": "OFFICIAL_ELECTORAL_LISTS_STATS",
        "url": "https://www.listeselectorales.ma/fr/statistiques.aspx",
        "publisher": "Ministère de l'Intérieur",
        "role": "statistiques officielles du corps électoral",
        "finding": "Le portail courant publie des statistiques nationales contemporaines, pas les 3 076 agrégats historiques requis.",
        "candidate_status": "not_found",
    },
    {
        "source_id": "WAYBACK_ELECTIONS_MA_2015",
        "url": "https://web.archive.org/web/20150916012118/http://www.elections.ma/elections/communales/resultats.aspx",
        "publisher": "Archive du site officiel elections.ma",
        "role": "vérification de l'interface historique 2015",
        "finding": "Interface et service de taux archivés; aucun CSV/XLS/XLSX communal d'inscrits retrouvé.",
        "candidate_status": "not_found",
    },
    {
        "source_id": "CNDH_2015_CONTROL",
        "url": "https://cndh.ma/sites/default/files/2024-01/rapportdeffr_7sept_compressed.pdf",
        "publisher": "Conseil national des droits de l'Homme",
        "role": "contrôle national 2015",
        "finding": "15 498 658 inscrits au niveau national; aucune table communale exploitable.",
        "candidate_status": "control_only",
    },
    {
        "source_id": "CNDH_2021_CONTROL",
        "url": "https://cndh.ma/en/2021-elections-thematic-observation-new-approach-highlighting-details-relationship-between-0",
        "publisher": "Conseil national des droits de l'Homme",
        "role": "contrôle national 2021",
        "finding": "17 983 490 inscrits au niveau national; aucune table communale exploitable.",
        "candidate_status": "control_only",
    },
    {
        "source_id": "TAFRA_COMMUNAL_RESULTS_2015_2021",
        "url": "https://open.africa/organization/tafra",
        "publisher": "TAFRA, copie de elections.ma",
        "role": "sources RAW déjà conservées dans V10",
        "finding": "Les notes des deux fichiers indiquent explicitement que le nombre d'inscrits et les votes nuls ne sont pas reportés.",
        "candidate_status": "known_missing",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check(check_id: str, passed: bool, observed: Any, expected: Any, note: str = "") -> dict[str, Any]:
    return {
        "check_id": check_id,
        "required": True,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "expected": expected,
        "note": note,
    }


def _column(frame: pd.DataFrame, canonical: str) -> str | None:
    folded = {str(name).strip().casefold(): str(name) for name in frame.columns}
    for alias in ALIASES[canonical]:
        if alias.casefold() in folded:
            return folded[alias.casefold()]
    return None


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _integer_domain(series: pd.Series, *, positive: bool) -> tuple[pd.Series, pd.Series]:
    numeric = _numeric(series)
    valid = numeric.notna() & (numeric % 1 == 0)
    valid &= numeric > 0 if positive else numeric >= 0
    return numeric, valid


def _privacy_columns(frame: pd.DataFrame) -> list[str]:
    return sorted(
        str(column)
        for column in frame.columns
        if any(re.search(pattern, str(column).strip(), flags=re.IGNORECASE) for pattern in PERSONAL_FIELD_PATTERNS)
    )


def normalize_candidate(frame: pd.DataFrame, expected_year: int) -> pd.DataFrame:
    normalized = pd.DataFrame(index=frame.index)
    id_column = _column(frame, "idCommune")
    geo_column = _column(frame, "geo_id")
    if id_column:
        normalized["idCommune"] = frame[id_column]
    elif geo_column:
        normalized["geo_id"] = frame[geo_column]
    year_column = _column(frame, "year")
    normalized["year"] = frame[year_column] if year_column else expected_year
    for field in ("registered_voters", "voters", "valid_votes", "invalid_votes", "blank_votes", "turnout_rate"):
        source = _column(frame, field)
        if source:
            normalized[field] = frame[source]
    return normalized


def evaluate_frame(
    frame: pd.DataFrame,
    *,
    year: int,
    baseline_ids: set[int],
    canonical_ids: set[str],
    baseline_turnout: dict[int, float],
    provenance_verified: bool,
    readable: bool = True,
) -> dict[str, Any]:
    normalized = normalize_candidate(frame, year)
    checks: list[dict[str, Any]] = []
    checks.append(_check("file_readable", readable, readable, True))
    checks.append(
        _check(
            "provenance",
            provenance_verified,
            "official aggregate provenance verified" if provenance_verified else "missing or unverified",
            "official aggregate provenance and reuse conditions documented",
        )
    )
    personal_columns = _privacy_columns(frame)
    checks.append(_check("aggregate_only", not personal_columns, personal_columns, []))
    checks.append(_check("row_count", len(normalized) == EXPECTED_ROWS, len(normalized), EXPECTED_ROWS))

    key = "idCommune" if "idCommune" in normalized else "geo_id" if "geo_id" in normalized else None
    duplicate_count = int(normalized[key].duplicated(keep=False).sum()) if key else len(normalized)
    missing_keys = int(normalized[key].isna().sum()) if key else len(normalized)
    checks.append(
        _check(
            "unique_geo_key",
            key is not None and duplicate_count == 0 and missing_keys == 0,
            {"key": key, "duplicate_rows": duplicate_count, "missing_keys": missing_keys},
            {"duplicate_rows": 0, "missing_keys": 0},
        )
    )
    if key == "idCommune":
        numeric_ids = _numeric(normalized[key])
        candidate_ids = set(numeric_ids.dropna().astype(int))
        geography_pass = numeric_ids.notna().all() and candidate_ids == baseline_ids
        missing_geo = len(baseline_ids - candidate_ids)
        extra_geo = len(candidate_ids - baseline_ids)
    elif key == "geo_id":
        candidate_geo = set(normalized[key].dropna().astype(str))
        geography_pass = candidate_geo == canonical_ids
        missing_geo = len(canonical_ids - candidate_geo)
        extra_geo = len(candidate_geo - canonical_ids)
    else:
        geography_pass, missing_geo, extra_geo = False, EXPECTED_ROWS, 0
    checks.append(
        _check(
            "geographic_universe",
            geography_pass,
            {"covered": EXPECTED_ROWS - missing_geo, "missing": missing_geo, "extra": extra_geo},
            {"covered": EXPECTED_ROWS, "missing": 0, "extra": 0, "fuzzy_matching": False},
        )
    )

    years = _numeric(normalized["year"])
    year_pass = years.notna().all() and set(years.astype(int)) == {year}
    checks.append(_check("election_year", year_pass, sorted(years.dropna().unique().tolist()), [year]))

    registered_column = "registered_voters" if "registered_voters" in normalized else None
    if registered_column:
        registered, registered_valid = _integer_domain(normalized[registered_column], positive=True)
    else:
        registered = pd.Series(float("nan"), index=normalized.index)
        registered_valid = pd.Series(False, index=normalized.index)
    invalid_registered = int((~registered_valid).sum())
    checks.append(
        _check(
            "registered_voters",
            registered_column is not None and invalid_registered == 0,
            {"field_present": registered_column is not None, "invalid_or_missing": invalid_registered},
            {"field_present": True, "invalid_or_missing": 0, "directly_published": True},
        )
    )
    total = int(registered.sum()) if registered_valid.all() else None
    checks.append(_check("national_total", total == EXPECTED_TOTALS[year], total, EXPECTED_TOTALS[year]))

    optional_invalid: dict[str, int] = {}
    numeric_optional: dict[str, pd.Series] = {}
    for field in ("voters", "valid_votes", "invalid_votes", "blank_votes"):
        if field not in normalized:
            continue
        numeric, valid = _integer_domain(normalized[field], positive=False)
        present = normalized[field].notna()
        optional_invalid[field] = int((present & ~valid).sum())
        numeric_optional[field] = numeric
    voters = numeric_optional.get("voters")
    voters_over_registered = int((voters > registered).fillna(False).sum()) if voters is not None else 0
    optional_pass = all(count == 0 for count in optional_invalid.values()) and voters_over_registered == 0
    checks.append(
        _check(
            "optional_counts",
            optional_pass,
            {"fields_present": sorted(numeric_optional), "invalid_values": optional_invalid, "voters_over_registered": voters_over_registered},
            {"invalid_values": 0, "voters_over_registered": 0},
            "Les champs facultatifs absents ne bloquent pas le GO.",
        )
    )

    accounting_tested = voters is not None and "valid_votes" in numeric_optional and "invalid_votes" in numeric_optional
    accounting_mismatches = 0
    if accounting_tested:
        components = numeric_optional["valid_votes"] + numeric_optional["invalid_votes"]
        if "blank_votes" in numeric_optional:
            components += numeric_optional["blank_votes"]
        complete = voters.notna() & components.notna()
        accounting_mismatches = int((complete & (components != voters)).sum())
    checks.append(
        _check(
            "accounting_identity",
            accounting_mismatches == 0,
            {"tested": accounting_tested, "mismatches": accounting_mismatches},
            {"mismatches": 0},
            "Contrôle appliqué uniquement lorsque tous les champs nécessaires sont directement présents.",
        )
    )

    turnout_tested = voters is not None and key == "idCommune" and registered_valid.all()
    turnout_mismatches = 0
    if turnout_tested:
        ids = _numeric(normalized["idCommune"])
        computed = 100 * voters / registered
        expected = ids.map(lambda value: baseline_turnout.get(int(value)) if pd.notna(value) else None)
        comparable = computed.notna() & expected.notna()
        turnout_mismatches = int((comparable & ((computed - expected).abs() > 0.01)).sum())
    checks.append(
        _check(
            "turnout_reconciliation",
            turnout_mismatches == 0,
            {"tested": turnout_tested, "mismatches_over_0_01_pp": turnout_mismatches},
            {"mismatches_over_0_01_pp": 0},
            "Tolérance maximale: 0,01 point; contrôle non bloquant lorsque voters est absent.",
        )
    )
    decision = "GO" if all(check["status"] == "PASS" for check in checks) else "NO_GO"
    return {
        "year": year,
        "decision": decision,
        "profile": {
            "rows": len(normalized),
            "columns": len(frame.columns),
            "key": key,
            "registered_total": total,
            "optional_fields_present": sorted(numeric_optional),
            "personal_columns": personal_columns,
        },
        "checks": checks,
    }


def _empty_evaluation(year: int) -> dict[str, Any]:
    checks = []
    for check_id in sorted(REQUIRED_CHECKS):
        note = "Aucun candidat agrégé officiel n'a été trouvé pour cette année."
        checks.append(_check(check_id, False, None, "candidat officiel complet", note))
    return {
        "year": year,
        "decision": "NO_GO",
        "profile": {"rows": 0, "columns": 0, "key": None, "registered_total": None, "optional_fields_present": [], "personal_columns": []},
        "checks": checks,
    }


def _load_frame(path: Path) -> tuple[pd.DataFrame, str]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return pd.read_csv(path), ""
    if suffix in {".xlsx", ".xls"}:
        book = pd.ExcelFile(path)
        data_sheet = "données" if "données" in book.sheet_names else "donnees" if "donnees" in book.sheet_names else book.sheet_names[0]
        frame = pd.read_excel(book, sheet_name=data_sheet)
        notes = ""
        if "notes" in book.sheet_names:
            notes = " ".join(pd.read_excel(book, sheet_name="notes", header=None).fillna("").astype(str).to_numpy().ravel())
        return frame, notes
    raise ValueError("Format candidat accepté: CSV, XLS ou XLSX")


def _provenance_verified(notes: str) -> bool:
    folded = notes.casefold()
    official = any(domain in folded for domain in ("elections.ma", "interieur.gov.ma", "listeselectorales.ma"))
    reusable = any(token in folded for token in ("licence", "license", "réutilisation", "reutilisation", "public"))
    return official and reusable


def _baseline_context(workbook_path: Path, year: int) -> tuple[set[int], set[str], dict[int, float]]:
    raw_sheet = f"RAW_COMM{year}_FULL"
    raw = pd.read_excel(workbook_path, sheet_name=raw_sheet, header=3, usecols=["idCommune", "txParticipation"])
    ids = set(raw["idCommune"].dropna().astype(int))
    turnout = {
        int(row.idCommune): float(row.txParticipation) * (100 if float(row.txParticipation) <= 1 else 1)
        for row in raw.itertuples()
        if pd.notna(row.idCommune) and pd.notna(row.txParticipation)
    }
    crosswalk = pd.read_excel(workbook_path, sheet_name="CROSSWALK_GEO", header=3)
    source_ids = {f"TAFRA_COMM_{item}" for item in ids}
    canonical = set(
        crosswalk.loc[
            crosswalk["source_geo_id"].astype(str).isin(source_ids) & crosswalk["canonical_geo_id"].notna(),
            "canonical_geo_id",
        ].astype(str)
    )
    return ids, canonical, turnout


def _candidate_record(path: Path, notes: str) -> dict[str, Any]:
    return {
        "local_name": path.name,
        "byte_size": path.stat().st_size,
        "sha256": sha256_file(path),
        "tracked": False,
        "provenance_in_file": _provenance_verified(notes),
    }


def build_metadata(
    *,
    workbook_path: Path,
    candidate_paths: dict[int, Path | None],
    as_of: str,
) -> dict[str, Any]:
    baseline_hash = sha256_file(workbook_path)
    evaluations: dict[str, dict[str, Any]] = {}
    candidates: dict[str, dict[str, Any] | None] = {}
    for year in YEARS:
        candidate = candidate_paths.get(year)
        if candidate is None:
            candidates[str(year)] = None
            evaluations[str(year)] = _empty_evaluation(year)
            continue
        frame, notes = _load_frame(candidate)
        ids, canonical, turnout = _baseline_context(workbook_path, year)
        provenance = _provenance_verified(notes)
        candidates[str(year)] = _candidate_record(candidate, notes)
        evaluations[str(year)] = evaluate_frame(
            frame,
            year=year,
            baseline_ids=ids,
            canonical_ids=canonical,
            baseline_turnout=turnout,
            provenance_verified=provenance,
        )
    if sha256_file(workbook_path) != baseline_hash:
        raise RuntimeError("La baseline V10 a changé pendant la qualification")
    decision = "GO" if all(evaluations[str(year)]["decision"] == "GO" for year in YEARS) else "NO_GO"
    return {
        "schema_version": 1,
        "phase": "V10-QA-1",
        "generated_on": as_of,
        "decision": decision,
        "scope": "Qualification des inscrits communaux 2015 et 2021; aucune ingestion.",
        "gate": {
            "required_years": list(YEARS),
            "expected_rows_per_year": EXPECTED_ROWS,
            "expected_rows_total": EXPECTED_ROWS * len(YEARS),
            "mandatory_field": "registered_voters directly published",
            "optional_fields": ["voters", "valid_votes", "invalid_votes", "blank_votes"],
            "partial_go_allowed": False,
            "reconstruction_allowed": False,
        },
        "national_controls": {str(year): total for year, total in EXPECTED_TOTALS.items()},
        "baseline": {
            "release": "V10",
            "workbook": "data/exports/excel/v10/Morocco_Electoral_Data_Warehouse_V10.xlsx",
            "sha256_before": baseline_hash,
            "sha256_after": sha256_file(workbook_path),
            "modified": False,
        },
        "candidates": candidates,
        "year_results": evaluations,
        "research_sources": RESEARCH_SOURCES,
        "anomalies": [
            {
                "anomaly_id": f"DENOM_{year}_SOURCE_NOT_FOUND",
                "year": year,
                "type": "missing_official_aggregate_source",
                "status": "unresolved",
                "affected_rows": EXPECTED_ROWS,
                "decision": "no_reconstruction_no_ingestion",
            }
            for year in YEARS
            if evaluations[str(year)]["decision"] != "GO"
        ],
        "next_action": (
            "Ouvrir une branche d'ingestion séparée des 3 076 inscrits directement publiés."
            if decision == "GO"
            else "Maintenir l'interdiction d'ingestion et passer à la qualification des 135 présidences communales."
        ),
    }


def validate_metadata(metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if metadata.get("schema_version") != 1 or metadata.get("phase") != "V10-QA-1":
        errors.append("Métadonnées racine invalides")
    if metadata.get("decision") not in {"GO", "NO_GO"}:
        errors.append("Décision binaire absente")
    gate = metadata.get("gate", {})
    if gate.get("expected_rows_total") != 3076 or gate.get("partial_go_allowed") is not False or gate.get("reconstruction_allowed") is not False:
        errors.append("Gate strict 3 076 lignes invalide")
    year_results = metadata.get("year_results", {})
    if set(year_results) != {"2015", "2021"}:
        errors.append("Résultats annuels incomplets")
        return errors
    for year in YEARS:
        result = year_results[str(year)]
        checks = result.get("checks", [])
        if {check.get("check_id") for check in checks} != REQUIRED_CHECKS:
            errors.append(f"{year}: contrôles obligatoires incorrects")
        expected = "GO" if checks and all(check.get("status") == "PASS" for check in checks) else "NO_GO"
        if result.get("decision") != expected:
            errors.append(f"{year}: décision incohérente")
    expected_overall = "GO" if all(year_results[str(year)].get("decision") == "GO" for year in YEARS) else "NO_GO"
    if metadata.get("decision") != expected_overall:
        errors.append("Décision globale incohérente")
    baseline = metadata.get("baseline", {})
    if baseline.get("modified") is not False or baseline.get("sha256_before") != baseline.get("sha256_after"):
        errors.append("Immutabilité V10 non démontrée")
    for candidate in metadata.get("candidates", {}).values():
        if candidate is not None and (candidate.get("tracked") is not False or not re.fullmatch(r"[0-9a-f]{64}", str(candidate.get("sha256", "")))):
            errors.append("Candidat incorrectement déclaré")
    return errors


def render_report(metadata: dict[str, Any]) -> str:
    lines = [
        "V10-QA-1 — QUALIFICATION DES DÉNOMINATEURS ÉLECTORAUX 2015–2021",
        "",
        "VERSION : V10-QA-1 (recherche, sans export warehouse)",
        f"DATE DE GÉNÉRATION : {metadata['generated_on']}",
        "PÉRIMÈTRE : 1 538 communes/arrondissements × élections 2015 et 2021",
        "RENVOIS : metadata/v10qa1_electoral_denominators.json ; V10-QA ; V10 immuable",
        "",
        f"DÉCISION BINAIRE : {metadata['decision']}",
        "",
        "Aucune ligne d'inscrits n'a été ingérée. V10, ses RAW, ses documents et ses tags n'ont pas été modifiés.",
        "Les inscrits, votants ou votes valides/invalides ne sont jamais reconstruits depuis les voix ou un taux.",
        "",
        "GATE",
        "GO exige 1 538 inscrits directement publiés en 2015 et 1 538 en 2021; aucun GO partiel n'est autorisé.",
        "Les votants et votes valides, invalides ou blancs sont facultatifs et ne sont retenus que si leur sémantique est explicite.",
        "",
        "RÉSULTATS PAR ANNÉE",
    ]
    for year in YEARS:
        result = metadata["year_results"][str(year)]
        profile = result["profile"]
        lines.append(
            f"{year} — {result['decision']} — lignes={profile['rows']} — total inscrits={profile['registered_total']} "
            f"— champs facultatifs={profile['optional_fields_present']}"
        )
        for check in result["checks"]:
            lines.append(f"  [{check['status']}] {check['check_id']} — observé={json.dumps(check['observed'], ensure_ascii=False)}")
    lines.extend(["", "RECHERCHE ET PROVENANCE"])
    for source in metadata["research_sources"]:
        lines.append(f"[{source['candidate_status']}] {source['source_id']} — {source['url']}")
        lines.append(f"  Constat : {source['finding']}")
    lines.extend(["", "CONTRÔLES NATIONAUX"])
    for year, total in metadata["national_controls"].items():
        lines.append(f"{year} : {total:,} inscrits".replace(",", " "))
    lines.extend(["", "ANOMALIES"])
    for anomaly in metadata["anomalies"]:
        lines.append(
            f"{anomaly['anomaly_id']} — {anomaly['type']} — lignes affectées={anomaly['affected_rows']} "
            f"— décision={anomaly['decision']}"
        )
    lines.extend(
        [
            "",
            "COMMANDE DE REPRODUCTION",
            "python -m morocco_elections qualify electoral-denominators --baseline v10 --as-of " + metadata["generated_on"],
            "",
            "SUITE",
            metadata["next_action"],
            "",
            "Ce rapport est généré intégralement depuis metadata/v10qa1_electoral_denominators.json.",
            "",
        ]
    )
    return "\n".join(lines)


def qualify(
    *,
    candidate_2015: str | Path | None = None,
    candidate_2021: str | Path | None = None,
    baseline: str = "v10",
    as_of: str | None = None,
    metadata_output: str | Path | None = None,
    decision_output: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> int:
    if baseline != "v10":
        raise ValueError("La qualification accepte uniquement la baseline v10")
    selected_date = as_of or date.today().isoformat()
    date.fromisoformat(selected_date)
    paths = get_paths(data_dir)
    if not paths.v10_workbook.is_file():
        print(f"ELECTORAL_DENOMINATORS_FAILED baseline V10 absente: {paths.v10_workbook}")
        return 2
    release = json.loads(V10_REPORT.read_text(encoding="utf-8"))
    if sha256_file(paths.v10_workbook) != release["workbooks"]["V10"]:
        print("ELECTORAL_DENOMINATORS_FAILED empreinte V10 différente de la release")
        return 2
    raw_candidates = {2015: candidate_2015, 2021: candidate_2021}
    candidate_paths: dict[int, Path | None] = {}
    for year, candidate in raw_candidates.items():
        if candidate is None:
            candidate_paths[year] = None
            continue
        path = Path(candidate).resolve()
        if not path.is_file():
            print(f"ELECTORAL_DENOMINATORS_FAILED candidat {year} absent: {path}")
            return 2
        candidate_paths[year] = path
    try:
        metadata = build_metadata(workbook_path=paths.v10_workbook, candidate_paths=candidate_paths, as_of=selected_date)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ELECTORAL_DENOMINATORS_FAILED candidat illisible ou invalide: {exc}")
        return 2
    errors = validate_metadata(metadata)
    if errors:
        print("ELECTORAL_DENOMINATORS_FAILED " + "; ".join(errors))
        return 2
    metadata_path = Path(metadata_output).resolve() if metadata_output else DEFAULT_METADATA
    report_path = Path(decision_output).resolve() if decision_output else DEFAULT_REPORT
    for output in (metadata_path, report_path):
        output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(metadata), encoding="utf-8")
    print(f"ELECTORAL_DENOMINATORS_{metadata['decision']} expected=3076 observed={sum(metadata['year_results'][str(y)]['profile']['rows'] for y in YEARS)}")
    return 0 if metadata["decision"] == "GO" else 1
