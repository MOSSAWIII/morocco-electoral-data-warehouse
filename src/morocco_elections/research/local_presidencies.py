from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from morocco_elections.config import PROJECT_ROOT, get_paths


EXPECTED_UNRESOLVED = 135
INSTALLATION_START = date(2021, 9, 8)
INSTALLATION_END = date(2021, 10, 31)
DEFAULT_METADATA = PROJECT_ROOT / "metadata" / "v10qa2_local_presidencies.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "research" / "V10QA2_LOCAL_PRESIDENCIES.txt"
EVIDENCE_COLUMNS = {
    "evidence_id",
    "source_idcommune",
    "person_id",
    "party_id",
    "source_class",
    "publisher",
    "origin_id",
    "source_url",
    "published_on",
    "event_on",
    "local_path",
    "locator",
    "direct_person",
    "direct_party",
    "initial_2021",
    "identity_disambiguator",
    "contradiction",
}
SOURCE_CLASSES = {"official_primary", "secondary"}
RESEARCH_SOURCES = [
    {
        "source_id": "DGCT_OPEN_DATA",
        "url": "https://www.collectivites-territoriales.gov.ma/index.php/fr/open-data-1",
        "publisher": "Direction générale des collectivités territoriales",
        "priority": 1,
        "finding": "Point d'entrée officiel prioritaire; aucun registre national nominatif 2021 exploitable n'a été identifié.",
    },
    {
        "source_id": "TAFRA_COUNCILS_2021",
        "url": "http://www.elections.ma",
        "publisher": "TAFRA, copie de la publication du ministère de l'Intérieur",
        "priority": 1,
        "finding": "Le dictionnaire confirme que flagRole signale les homonymies ou données absentes; 135 communes n'ont aucune ligne président.",
    },
    {
        "source_id": "SECONDARY_INSTALLATION_REPORTS",
        "url": "https://fr.le360.ma/politique/voici-la-liste-des-presidents-des-conseils-communaux-elus-ce-vendredi-17-septembre-2021-245841/",
        "publisher": "Presse contemporaine",
        "priority": 2,
        "finding": "Piste secondaire seulement; deux origines indépendantes sont nécessaires en l'absence de preuve officielle.",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _records(workbook: Path, sheet: str) -> pd.DataFrame:
    return pd.read_excel(workbook, sheet_name=sheet, header=3)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().casefold() in {"1", "true", "vrai", "yes", "oui"}


def _as_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def _safe_local_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def load_baseline_context(workbook_path: Path) -> dict[str, Any]:
    mandates = _records(workbook_path, "LOCAL_MANDATES")
    control = _records(workbook_path, "LOCAL_COUNCIL_CONTROL")
    audit = _records(workbook_path, "IDENTITY_AUDIT_V10")
    raw_council = _records(workbook_path, "RAW_COUNCIL2021_FULL")

    grouped = control.groupby("geo_id", dropna=False)["president_person_id"].apply(
        lambda values: values.dropna().astype(str).nunique()
    )
    unresolved_geos = sorted(str(item) for item in grouped[grouped == 0].index)
    mapping = mandates[["source_idcommune", "canonical_geo_id"]].dropna().drop_duplicates()
    geo_to_source = {
        str(row.canonical_geo_id): int(row.source_idcommune)
        for row in mapping.itertuples(index=False)
    }
    universe = [
        {"geo_id": geo_id, "source_idcommune": geo_to_source[geo_id]}
        for geo_id in unresolved_geos
    ]
    ambiguous = {
        int(value)
        for value in pd.to_numeric(audit.get("source_idcommune"), errors="coerce").dropna()
    }
    mandate_lookup: dict[str, dict[str, Any]] = {}
    for row in mandates.itertuples(index=False):
        mandate_lookup[str(row.person_id)] = {
            "source_idcommune": int(row.source_idcommune),
            "geo_id": str(row.canonical_geo_id),
            "party_id": str(row.party_id).strip().upper(),
        }
    if len(universe) != EXPECTED_UNRESOLVED:
        raise RuntimeError(f"V10 contient {len(universe)} présidences non résolues au lieu de {EXPECTED_UNRESOLVED}")
    unresolved_source_ids = {item["source_idcommune"] for item in universe}
    raw_subset = raw_council[
        pd.to_numeric(raw_council["idCommune"], errors="coerce").isin(unresolved_source_ids)
    ]
    president_mask = raw_subset["role"].fillna("").astype(str).str.strip().str.casefold().eq("président")
    president_rows = int(president_mask.sum())
    confident_president_rows = int(
        (president_mask & pd.to_numeric(raw_subset["flagRole"], errors="coerce").fillna(1).eq(0)).sum()
    )
    communes_with_role = int(raw_subset.loc[president_mask, "idCommune"].nunique())
    if confident_president_rows:
        raise RuntimeError(f"Le périmètre contient {confident_president_rows} présidence(s) RAW non incertaine(s)")
    return {
        "universe": universe,
        "ambiguous_communes": ambiguous,
        "mandates": mandate_lookup,
        "raw_rows_in_scope": len(raw_subset),
        "raw_president_rows": president_rows,
        "raw_confident_president_rows": confident_president_rows,
        "communes_without_president_role": EXPECTED_UNRESOLVED - communes_with_role,
    }


def _empty_evidence() -> pd.DataFrame:
    return pd.DataFrame(columns=sorted(EVIDENCE_COLUMNS))


def load_evidence_index(index_path: Path | None) -> tuple[pd.DataFrame, list[str]]:
    if index_path is None:
        return _empty_evidence(), []
    if not index_path.is_file():
        raise RuntimeError(f"Index de preuves absent: {index_path}")
    frame = pd.read_csv(index_path, dtype=str, keep_default_na=False)
    missing = sorted(EVIDENCE_COLUMNS - set(frame.columns))
    if missing:
        raise RuntimeError(f"Colonnes absentes de l'index de preuves: {', '.join(missing)}")
    errors: list[str] = []
    if frame["evidence_id"].duplicated().any() or (frame["evidence_id"].str.strip() == "").any():
        errors.append("evidence_id vide ou dupliqué")
    return frame, errors


def evaluate_case(
    case: dict[str, Any],
    evidence: pd.DataFrame,
    mandates: dict[str, dict[str, Any]],
    *,
    ambiguous: bool,
    index_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_id = int(case["source_idcommune"])
    rows = evidence[pd.to_numeric(evidence.get("source_idcommune"), errors="coerce") == source_id]
    evaluated: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []
    reasons: set[str] = set()

    for raw in rows.to_dict("records"):
        evidence_id = str(raw.get("evidence_id", "")).strip()
        person_id = str(raw.get("person_id", "")).strip()
        party_id = str(raw.get("party_id", "")).strip().upper()
        source_class = str(raw.get("source_class", "")).strip()
        published_on = _as_date(raw.get("published_on"))
        event_on = _as_date(raw.get("event_on"))
        local_value = str(raw.get("local_path", "")).strip()
        local_path = Path(local_value)
        if local_value and not local_path.is_absolute():
            local_path = index_dir / local_path
        mandate = mandates.get(person_id)
        checks = {
            "known_source_class": source_class in SOURCE_CLASSES,
            "direct_person": _as_bool(raw.get("direct_person")),
            "direct_party": _as_bool(raw.get("direct_party")),
            "initial_2021": _as_bool(raw.get("initial_2021")),
            "event_window": event_on is not None and INSTALLATION_START <= event_on <= INSTALLATION_END,
            "publication_after_event": published_on is not None and event_on is not None and published_on >= event_on,
            "valid_url": bool(re.match(r"^https?://", str(raw.get("source_url", "")).strip())),
            "proof_file": bool(local_value) and local_path.is_file(),
            "person_in_commune": mandate is not None and mandate["source_idcommune"] == source_id,
            "party_matches": mandate is not None and mandate["party_id"] == party_id,
            "disambiguated": not ambiguous or _as_bool(raw.get("identity_disambiguator")),
            "not_marked_contradictory": not _as_bool(raw.get("contradiction")),
        }
        valid = all(checks.values())
        proof_hash = sha256_file(local_path) if checks["proof_file"] else None
        record = {
            "evidence_id": evidence_id,
            "source_class": source_class,
            "publisher": str(raw.get("publisher", "")).strip(),
            "origin_id": str(raw.get("origin_id", "")).strip(),
            "source_url": str(raw.get("source_url", "")).strip(),
            "published_on": published_on.isoformat() if published_on else None,
            "event_on": event_on.isoformat() if event_on else None,
            "local_path": _safe_local_path(local_path) if local_value else None,
            "locator": str(raw.get("locator", "")).strip(),
            "sha256": proof_hash,
            "byte_size": local_path.stat().st_size if checks["proof_file"] else None,
            "person_id": person_id or None,
            "party_id": party_id or None,
            "checks": checks,
            "valid": valid,
        }
        evaluated.append(record)
        if valid:
            valid_rows.append(record)

    candidate_pairs = {(item["person_id"], item["party_id"]) for item in valid_rows}
    if not rows.shape[0]:
        reasons.add("NO_EVIDENCE")
    if rows.shape[0] and not valid_rows:
        reasons.add("NO_VALID_EVIDENCE")
    if len(candidate_pairs) > 1 or any(_as_bool(row.get("contradiction")) for row in rows.to_dict("records")):
        reasons.add("CONTRADICTORY_EVIDENCE")

    go = False
    selected_person: str | None = None
    selected_party: str | None = None
    if len(candidate_pairs) == 1 and "CONTRADICTORY_EVIDENCE" not in reasons:
        selected_person, selected_party = next(iter(candidate_pairs))
        matching = [item for item in valid_rows if (item["person_id"], item["party_id"]) == (selected_person, selected_party)]
        official = any(item["source_class"] == "official_primary" for item in matching)
        secondary = [item for item in matching if item["source_class"] == "secondary"]
        independent_secondary = len({item["origin_id"] for item in secondary if item["origin_id"]}) >= 2 and len(
            {item["publisher"].casefold() for item in secondary if item["publisher"]}
        ) >= 2
        go = official or independent_secondary
        if not go:
            reasons.add("INSUFFICIENT_INDEPENDENT_SOURCES")

    if go:
        reasons = {"EVIDENCE_GATE_PASSED"}
    return (
        {
            "case_id": f"V10QA2_PRES_{case['geo_id']}",
            "geo_id": case["geo_id"],
            "source_idcommune": source_id,
            "identity_ambiguity": ambiguous,
            "decision": "GO" if go else "NO_GO",
            "person_id": selected_person if go else None,
            "party_id": selected_party if go else None,
            "evidence_ids": sorted(item["evidence_id"] for item in valid_rows),
            "reason_codes": sorted(reasons),
        },
        evaluated,
    )


def build_metadata(workbook_path: Path, evidence_index: Path | None, as_of: str) -> dict[str, Any]:
    baseline_hash = sha256_file(workbook_path)
    context = load_baseline_context(workbook_path)
    evidence, index_errors = load_evidence_index(evidence_index)
    decisions: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    index_dir = evidence_index.parent if evidence_index else PROJECT_ROOT
    for case in context["universe"]:
        decision, records = evaluate_case(
            case,
            evidence,
            context["mandates"],
            ambiguous=int(case["source_idcommune"]) in context["ambiguous_communes"],
            index_dir=index_dir,
        )
        decisions.append(decision)
        evidence_records.extend(records)
    if index_errors:
        for decision in decisions:
            decision["decision"] = "NO_GO"
            decision["person_id"] = None
            decision["party_id"] = None
            decision["reason_codes"] = sorted(set(decision["reason_codes"]) | {"INVALID_EVIDENCE_INDEX"})
    if sha256_file(workbook_path) != baseline_hash:
        raise RuntimeError("La baseline V10 a changé pendant la qualification")
    validated = sum(item["decision"] == "GO" for item in decisions)
    return {
        "schema_version": 1,
        "phase": "V10-QA-2",
        "generated_on": as_of,
        "decision": "GO" if validated else "NO_GO",
        "scope": "Qualification individuelle des 135 présidences communales 2021; aucune ingestion.",
        "gate": {
            "expected_cases": EXPECTED_UNRESOLVED,
            "decision_level": "commune",
            "official_sources_required": 1,
            "independent_secondary_sources_required": 2,
            "person_and_party_required": True,
            "inference_from_head_or_largest_party_allowed": False,
            "installation_window": [INSTALLATION_START.isoformat(), INSTALLATION_END.isoformat()],
        },
        "baseline": {
            "release": "V10",
            "workbook": "data/exports/excel/v10/Morocco_Electoral_Data_Warehouse_V10.xlsx",
            "sha256_before": baseline_hash,
            "sha256_after": sha256_file(workbook_path),
            "modified": False,
        },
        "evidence_index": {
            "provided": evidence_index is not None,
            "local_path": _safe_local_path(evidence_index) if evidence_index else None,
            "sha256": sha256_file(evidence_index) if evidence_index and evidence_index.is_file() else None,
            "tracked": False,
            "errors": index_errors,
        },
        "summary": {
            "expected": EXPECTED_UNRESOLVED,
            "validated": validated,
            "unresolved": EXPECTED_UNRESOLVED - validated,
            "ambiguous_identity_communes": len(context["ambiguous_communes"] & {item["source_idcommune"] for item in context["universe"]}),
            "raw_rows_in_scope": context["raw_rows_in_scope"],
            "raw_president_rows": context["raw_president_rows"],
            "raw_confident_president_rows": context["raw_confident_president_rows"],
            "communes_without_president_role": context["communes_without_president_role"],
        },
        "decisions": decisions,
        "evidence": evidence_records,
        "research_sources": RESEARCH_SOURCES,
        "next_action": (
            "Ouvrir feat/v11-local-presidencies pour les seuls cas GO; maintenir les autres à NULL."
            if validated
            else "Ne rien ingérer; poursuivre la recherche de preuves sur les 135 communes."
        ),
    }


def validate_metadata(metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if metadata.get("schema_version") != 1 or metadata.get("phase") != "V10-QA-2":
        errors.append("Métadonnées racine invalides")
    if metadata.get("decision") not in {"GO", "NO_GO"}:
        errors.append("Décision globale invalide")
    decisions = metadata.get("decisions", [])
    if len(decisions) != EXPECTED_UNRESOLVED:
        errors.append("La qualification doit contenir exactement 135 décisions")
    geo_ids = [item.get("geo_id") for item in decisions]
    source_ids = [item.get("source_idcommune") for item in decisions]
    if len(set(geo_ids)) != len(geo_ids) or len(set(source_ids)) != len(source_ids):
        errors.append("Commune dupliquée dans les décisions")
    for item in decisions:
        if item.get("decision") not in {"GO", "NO_GO"} or not item.get("reason_codes"):
            errors.append(f"Décision communale incomplète: {item.get('case_id')}")
        if item.get("decision") == "GO" and (not item.get("person_id") or not item.get("party_id")):
            errors.append(f"Cas GO sans personne et parti: {item.get('case_id')}")
        if item.get("decision") == "NO_GO" and (item.get("person_id") is not None or item.get("party_id") is not None):
            errors.append(f"Cas NO_GO exposant une identité: {item.get('case_id')}")
    validated = sum(item.get("decision") == "GO" for item in decisions)
    summary = metadata.get("summary", {})
    if summary.get("expected") != EXPECTED_UNRESOLVED or summary.get("validated") != validated or summary.get("unresolved") != EXPECTED_UNRESOLVED - validated:
        errors.append("Résumé de couverture incohérent")
    if summary.get("raw_confident_president_rows") != 0 or not isinstance(summary.get("raw_rows_in_scope"), int):
        errors.append("Diagnostic du RAW communal incohérent")
    if metadata.get("decision") != ("GO" if validated else "NO_GO"):
        errors.append("Décision globale incohérente")
    baseline = metadata.get("baseline", {})
    if baseline.get("modified") is not False or baseline.get("sha256_before") != baseline.get("sha256_after"):
        errors.append("Immutabilité V10 non démontrée")
    serialized = json.dumps(metadata, ensure_ascii=False)
    forbidden = ("prenomNom", "person_name_ar", "person_name_normalized", "person_name_match_key")
    if any(token in serialized for token in forbidden):
        errors.append("Champ nominatif interdit dans l'artefact suivi")
    for record in metadata.get("evidence", []):
        if record.get("valid") and not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", ""))):
            errors.append(f"Preuve valide sans SHA-256: {record.get('evidence_id')}")
    return errors


def render_report(metadata: dict[str, Any]) -> str:
    summary = metadata["summary"]
    lines = [
        "V10-QA-2 — QUALIFICATION DES PRÉSIDENCES COMMUNALES 2021",
        "",
        "VERSION : V10-QA-2 (recherche, sans export warehouse)",
        f"DATE DE GÉNÉRATION : {metadata['generated_on']}",
        "PÉRIMÈTRE : 135 communes sans ligne président dans le RAW communal 2021",
        "RENVOIS : metadata/v10qa2_local_presidencies.json ; V10-QA ; V10 immuable",
        "",
        f"DÉCISION GLOBALE : {metadata['decision']}",
        f"COUVERTURE : {summary['validated']}/{summary['expected']} présidences validées; {summary['unresolved']} restent non résolues.",
        f"DIAGNOSTIC V10 : {summary['raw_rows_in_scope']} lignes d'élus; {summary['communes_without_president_role']} communes sans rôle président; "
        f"{summary['raw_president_rows']} rôles président incertains; {summary['raw_confident_president_rows']} présidence certaine.",
        "",
        "Aucune présidence n'a été ingérée. V10, ses RAW, ses documents et ses tags n'ont pas été modifiés.",
        "Aucune présidence n'est déduite d'une tête de liste, du plus grand parti ou d'une vice-présidence.",
        "",
        "GATE PAR COMMUNE",
        "GO exige personne et parti dans LOCAL_MANDATES, une preuve officielle ou deux origines secondaires indépendantes,",
        "un événement d'installation entre le 8 septembre et le 31 octobre 2021, et aucune contradiction.",
        f"Les {summary['ambiguous_identity_communes']} communes touchées par une ambiguïté d'identité exigent un élément discriminant.",
        "",
        "FORMAT DE L'INDEX LOCAL (NON SUIVI)",
        "Une ligne par preuve : evidence_id, source_idcommune, person_id, party_id, source_class, publisher, origin_id,",
        "source_url, published_on, event_on, local_path, locator, direct_person, direct_party, initial_2021,",
        "identity_disambiguator, contradiction. source_class vaut official_primary ou secondary.",
        "",
        "DÉCISIONS",
    ]
    for item in metadata["decisions"]:
        lines.append(
            f"[{item['decision']}] {item['case_id']} — source_idcommune={item['source_idcommune']} "
            f"— preuves={len(item['evidence_ids'])} — motifs={','.join(item['reason_codes'])}"
        )
    lines.extend(["", "SOURCES DE RECHERCHE"])
    for source in metadata["research_sources"]:
        lines.append(f"[{source['priority']}] {source['source_id']} — {source['url']}")
        lines.append(f"  Constat : {source['finding']}")
    command = "python -m morocco_elections qualify local-presidencies --baseline v10 --as-of " + metadata["generated_on"]
    if metadata["evidence_index"]["provided"]:
        command += " --evidence-index " + str(metadata["evidence_index"]["local_path"])
    lines.extend(["", "COMMANDE DE REPRODUCTION", command, "", "SUITE", metadata["next_action"], ""])
    return "\n".join(lines)


def qualify(
    *,
    evidence_index: str | Path | None = None,
    baseline: str = "v10",
    as_of: str | None = None,
    metadata_output: str | Path | None = None,
    decision_output: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> int:
    if baseline != "v10":
        raise ValueError("Seule la baseline v10 est prise en charge")
    try:
        generated_on = as_of or date.today().isoformat()
        datetime.strptime(generated_on, "%Y-%m-%d")
        workbook = get_paths(data_dir).v10_workbook
        if not workbook.is_file():
            raise RuntimeError(f"Baseline V10 absente: {workbook}")
        index = Path(evidence_index).resolve() if evidence_index else None
        metadata = build_metadata(workbook, index, generated_on)
        errors = validate_metadata(metadata)
        if errors:
            raise RuntimeError("; ".join(errors))
        metadata_path = Path(metadata_output) if metadata_output else DEFAULT_METADATA
        report_path = Path(decision_output) if decision_output else DEFAULT_REPORT
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path.write_text(render_report(metadata), encoding="utf-8")
        print(f"LOCAL_PRESIDENCIES_{metadata['decision']} validated={metadata['summary']['validated']}/135")
        return 0 if metadata["decision"] == "GO" else 1
    except (OSError, RuntimeError, ValueError, pd.errors.ParserError) as exc:
        print(f"LOCAL_PRESIDENCIES_FAILED: {exc}")
        return 2
