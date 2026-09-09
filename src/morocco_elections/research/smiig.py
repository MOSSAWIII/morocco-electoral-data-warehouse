from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from morocco_elections.config import get_paths
from morocco_elections.provenance import sha256_file

EXPECTED_SHEETS = ["donnees", "dictionnaire", "notes"]
EXPECTED_COLUMNS = [
    "idRegion", "idWilaya", "idPrefProv", "idSousPref", "idCommune", "region", "wilaya", "prefProv",
    "sousPref", "commune", "url", "annee", "participation_contactAministration",
    "participation_compositionConseil", "participation_agendaConseil", "participation_compositionCommissionsConseil",
    "participation_compositionInstancesConsultatives", "participation_espaceConcertationEnLigne",
    "participation_contactCommune", "finances_budgetCommune", "finances_budgetCommuneHistorique",
    "finances_rapportAudit", "finances_etatsComptablesHistorique", "finances_listeBiens",
    "finances_etatsComptables", "finances_marchesPublicsFuturs", "finances_subventions",
    "gouvernance_organigramme", "gouvernance_planAction", "gouvernance_recrutement",
    "gouvernance_livreProcedure", "gouvernance_reglementInterieur", "participation", "finances",
    "gouvernance", "smiigBrut", "smiig", "inDb",
]
REQUIRED_COLUMNS = [
    "idRegion", "idWilaya", "idPrefProv", "idCommune", "region", "wilaya", "prefProv", "commune", "annee",
    *EXPECTED_COLUMNS[12:37],
]
INDICATOR_COLUMNS = EXPECTED_COLUMNS[12:32]
DATASET_URL = "https://open.africa/en_AU/dataset/smiig-data-communes-2023"
RESOURCE_URL = (
    "https://open.africa/dataset/6dd7b9ca-907e-4d26-a9c6-6fd37566db3e/resource/"
    "1f4e6352-beba-4d97-8cd1-8beab2ddd94d/download/2024-01-08-dataset-smiig-v2023-communes.xlsx"
)
FINAL_URL = (
    "https://s3-eu-west-1.amazonaws.com/cfa-openafrica/resources/1f4e6352-beba-4d97-8cd1-8beab2ddd94d/"
    "2024-01-08-dataset-smiig-v2023-communes.xlsx?ETag=bcb539e2cc50312a44e9415ebdb83e59"
)
TAFRA_METHOD_URL = "https://tafra.ma/la-mise-en-oeuvre-du-droit-dacces-a-linformation-lindicateur-smiig-data-des-communes/"


@dataclass(frozen=True)
class Contract:
    expected_rows: int = 464
    expected_columns: int = 38
    expected_units: int = 116
    expected_years: tuple[int, ...] = (2020, 2021, 2022, 2023)


def _plain(value: Any) -> Any:
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def _check(check_id: str, passed: bool, observed: Any, expected: Any, note: str = "") -> dict[str, Any]:
    return {
        "check_id": check_id,
        "required": True,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "expected": expected,
        "note": note,
    }


def _anomaly_id(row: pd.Series, anomaly_type: str, column: str = "") -> str:
    payload = f"{_plain(row.get('idCommune'))}|{_plain(row.get('annee'))}|{anomaly_type}|{column}"
    return "SMIIG_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _dictionary_maxima(dictionary: pd.DataFrame) -> dict[str, int]:
    maxima: dict[str, int] = {}
    if dictionary.shape[1] < 2:
        return maxima
    for _, row in dictionary.iterrows():
        match = re.search(r"(\d+)\s+points max", str(row.iloc[1]), flags=re.IGNORECASE)
        if match:
            maxima[str(row.iloc[0])] = int(match.group(1))
    return maxima


def evaluate_frames(
    data: pd.DataFrame,
    dictionary: pd.DataFrame,
    notes: pd.DataFrame,
    baseline_communes: pd.DataFrame,
    crosswalk: pd.DataFrame,
    dim_geo: pd.DataFrame,
    *,
    contract: Contract = Contract(),
    sheet_names: list[str] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    sheets = sheet_names or EXPECTED_SHEETS
    checks.append(_check("xlsx_and_sheets", sheets == EXPECTED_SHEETS, sheets, EXPECTED_SHEETS))
    shape_ok = data.shape == (contract.expected_rows, contract.expected_columns) and list(data.columns) == EXPECTED_COLUMNS
    checks.append(
        _check(
            "data_shape",
            shape_ok,
            {"rows": len(data), "columns": len(data.columns), "column_names": list(data.columns)},
            {"rows": contract.expected_rows, "columns": contract.expected_columns, "column_names": EXPECTED_COLUMNS},
        )
    )

    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    null_counts = {column: int(data[column].isna().sum()) for column in REQUIRED_COLUMNS if column in data}
    checks.append(
        _check(
            "required_values",
            not missing_columns and all(value == 0 for value in null_counts.values()),
            {"missing_columns": missing_columns, "null_counts": null_counts},
            "zero null in mandatory identifiers, geography, year and measures",
        )
    )

    years = sorted(int(value) for value in data.get("annee", pd.Series(dtype=int)).dropna().unique())
    year_counts = {str(int(key)): int(value) for key, value in data.get("annee", pd.Series(dtype=int)).value_counts().sort_index().items()}
    expected_per_year = contract.expected_rows // len(contract.expected_years)
    temporal_ok = years == list(contract.expected_years) and set(year_counts.values()) == {expected_per_year}
    checks.append(
        _check(
            "temporal_coverage",
            temporal_ok,
            {"years": years, "rows_by_year": year_counts},
            {"years": list(contract.expected_years), "rows_per_year": expected_per_year},
        )
    )

    key_columns = ["idCommune", "annee"]
    duplicate_rows = data[data.duplicated(key_columns, keep=False)] if set(key_columns) <= set(data.columns) else data.iloc[0:0]
    for _, row in duplicate_rows.iterrows():
        anomalies.append(
            {
                "anomaly_id": _anomaly_id(row, "duplicate_grain"),
                "type": "duplicate_grain",
                "source_row_number": int(row.name) + 2,
                "column": None,
                "status": "unresolved",
            }
        )
    checks.append(
        _check(
            "grain_uniqueness",
            duplicate_rows.empty,
            {"duplicate_rows": len(duplicate_rows), "unique_keys": len(data.drop_duplicates(key_columns))},
            {"duplicate_rows": 0, "grain": "idCommune × annee"},
        )
    )

    unit_ids = set(data.get("idCommune", pd.Series(dtype=int)).dropna().astype(int))
    baseline_ids = set(baseline_communes["idCommune"].dropna().astype(int))
    units_ok = len(unit_ids) == contract.expected_units and unit_ids <= baseline_ids
    checks.append(
        _check(
            "v10_universe_subset",
            units_ok,
            {
                "observed_units": len(unit_ids),
                "v10_universe": len(baseline_ids),
                "coverage_percent": round(100 * len(unit_ids & baseline_ids) / len(baseline_ids), 4) if baseline_ids else 0,
                "outside_v10": len(unit_ids - baseline_ids),
            },
            {"observed_units": contract.expected_units, "outside_v10": 0},
            "Une couverture partielle conforme au périmètre >50 000 habitants est classée PILOTE.",
        )
    )

    required_source_ids = {f"TAFRA_COMM_{value}" for value in unit_ids}
    mapping = crosswalk[crosswalk["source_geo_id"].astype(str).isin(required_source_ids)].copy()
    mapping = mapping[mapping["canonical_geo_id"].notna()]
    targets_per_source = mapping.groupby("source_geo_id")["canonical_geo_id"].nunique()
    covered_sources = set(targets_per_source.index)
    crosswalk_ok = required_source_ids <= covered_sources and bool((targets_per_source == 1).all())
    checks.append(
        _check(
            "v10_geographic_crosswalk",
            crosswalk_ok,
            {
                "covered_units": len(required_source_ids & covered_sources),
                "required_units": len(required_source_ids),
                "ambiguous_units": int((targets_per_source > 1).sum()),
            },
            {"coverage_percent": 100.0, "ambiguous_units": 0},
        )
    )

    dictionary_labels = set(dictionary.iloc[:, 0].dropna().astype(str)) if not dictionary.empty else set()
    undocumented = sorted(set(data.columns) - dictionary_labels)
    dictionary_ok = not undocumented and not (dictionary_labels - set(data.columns))
    checks.append(
        _check(
            "dictionary_consistency",
            dictionary_ok,
            {"documented_fields": len(dictionary_labels), "undocumented_fields": undocumented},
            {"documented_fields": contract.expected_columns, "undocumented_fields": []},
        )
    )
    for column in undocumented:
        anomalies.append(
            {
                "anomaly_id": "SMIIG_SCHEMA_" + hashlib.sha256(column.encode("utf-8")).hexdigest()[:20],
                "type": "undocumented_field",
                "source_row_number": None,
                "column": column,
                "status": "unresolved",
            }
        )

    notes_text = " ".join(notes.fillna("").astype(str).to_numpy().ravel()).casefold()
    license_ok = "cc by 4.0" in notes_text and "creativecommons.org/licenses/by/4.0" in notes_text
    checks.append(_check("license", license_ok, "CC BY 4.0" if license_ok else "not demonstrated", "CC BY 4.0"))

    maxima = _dictionary_maxima(dictionary)
    domain_violations = 0
    for column in INDICATOR_COLUMNS:
        if column not in data or column not in maxima:
            continue
        numeric = pd.to_numeric(data[column], errors="coerce")
        invalid = numeric.isna() | (numeric < 0) | (numeric > maxima[column])
        domain_violations += int(invalid.sum())
        for index in data.index[invalid]:
            row = data.loc[index]
            anomalies.append(
                {
                    "anomaly_id": _anomaly_id(row, "indicator_domain", column),
                    "type": "indicator_domain",
                    "source_row_number": int(index) + 2,
                    "column": column,
                    "status": "unresolved",
                }
            )
    checks.append(
        _check(
            "indicator_domains",
            domain_violations == 0 and len(maxima) == len(INDICATOR_COLUMNS),
            {"documented_indicator_maxima": len(maxima), "violating_cells": domain_violations},
            {"documented_indicator_maxima": len(INDICATOR_COLUMNS), "violating_cells": 0},
        )
    )

    numeric_components = data[["participation", "finances", "gouvernance", "smiigBrut", "smiig"]].apply(
        pd.to_numeric, errors="coerce"
    )
    component_error = (
        numeric_components["smiigBrut"]
        - numeric_components[["participation", "finances", "gouvernance"]].sum(axis=1)
    ).abs()
    checks.append(
        _check(
            "component_formula",
            bool((component_error <= 1e-9).all()),
            {"mismatch_rows": int((component_error > 1e-9).sum()), "max_absolute_error": float(component_error.max())},
            {"formula": "smiigBrut = participation + finances + gouvernance", "mismatch_rows": 0},
        )
    )
    score_error = (numeric_components["smiig"] - numeric_components["smiigBrut"] / 242 * 100).abs()
    bad_scores = score_error > 1e-6
    for index in data.index[bad_scores]:
        row = data.loc[index]
        anomalies.append(
            {
                "anomaly_id": _anomaly_id(row, "normalized_score", "smiig"),
                "type": "normalized_score",
                "source_row_number": int(index) + 2,
                "column": "smiig",
                "status": "unresolved",
            }
        )
    checks.append(
        _check(
            "normalized_score_formula",
            not bool(bad_scores.any()),
            {"mismatch_rows": int(bad_scores.sum()), "max_absolute_error": float(score_error.max())},
            {"formula": "smiig = smiigBrut / 242 × 100", "tolerance": 1e-6, "mismatch_rows": 0},
        )
    )

    canonical_types: dict[int, str] = {}
    if not mapping.empty:
        canonical_by_source = mapping.drop_duplicates("source_geo_id").set_index("source_geo_id")["canonical_geo_id"]
        geo_types = dim_geo.set_index("geo_id")["geo_type"]
        for unit_id in unit_ids:
            canonical_id = canonical_by_source.get(f"TAFRA_COMM_{unit_id}")
            canonical_types[unit_id] = str(geo_types.get(canonical_id, ""))
    arrondissement_mask = data["idCommune"].map(canonical_types).eq("arrondissement")
    expected_replication_rows = int(arrondissement_mask.sum())
    linked_replication_rows = int((arrondissement_mask & data["inDb"].notna()).sum())
    missing_replication = data.index[arrondissement_mask & data["inDb"].isna()]
    for index in missing_replication:
        row = data.loc[index]
        anomalies.append(
            {
                "anomaly_id": _anomaly_id(row, "replication_lineage", "inDb"),
                "type": "replication_lineage",
                "source_row_number": int(index) + 2,
                "column": "inDb",
                "status": "unresolved",
            }
        )
    checks.append(
        _check(
            "arrondissement_replication_lineage",
            expected_replication_rows == linked_replication_rows,
            {
                "arrondissement_rows": expected_replication_rows,
                "linked_rows": linked_replication_rows,
                "missing_links": expected_replication_rows - linked_replication_rows,
            },
            {"missing_links": 0},
            "Les notes déclarent une réplication du score municipal vers les arrondissements.",
        )
    )

    role_or_person_columns = [column for column in data.columns if "role" in column.casefold() or "person" in column.casefold()]
    checks.append(
        _check(
            "identity_and_role_scope",
            not role_or_person_columns,
            {"person_or_role_columns": role_or_person_columns, "automatic_identity_merges": 0},
            {"person_or_role_columns": [], "automatic_identity_merges": 0},
            "La source mesure la publication proactive; elle ne contient ni personnes ni rôles individuels.",
        )
    )

    decision = "GO" if all(check["status"] == "PASS" for check in checks if check["required"]) else "NO_GO"
    return {
        "decision": decision,
        "checks": checks,
        "anomalies": anomalies,
        "profile": {
            "rows": len(data),
            "columns": len(data.columns),
            "units": len(unit_ids),
            "years": years,
            "rows_by_year": year_counts,
            "geography_types": {
                str(key): int(value) for key, value in pd.Series(canonical_types).value_counts().sort_index().items()
            },
            "v10_universe": len(baseline_ids),
            "v10_coverage_percent": round(100 * len(unit_ids & baseline_ids) / len(baseline_ids), 4) if baseline_ids else 0,
            "optional_nulls": {
                column: int(data[column].isna().sum()) for column in ("idSousPref", "sousPref", "url", "inDb")
            },
        },
    }


def load_and_evaluate(candidate: Path, baseline: Path) -> dict[str, Any]:
    excel = pd.ExcelFile(candidate, engine="openpyxl")
    data = pd.read_excel(excel, sheet_name="donnees")
    dictionary = pd.read_excel(excel, sheet_name="dictionnaire")
    notes = pd.read_excel(excel, sheet_name="notes")
    baseline_communes = pd.read_excel(baseline, sheet_name="RAW_COMM2015_FULL", header=3)
    crosswalk = pd.read_excel(baseline, sheet_name="CROSSWALK_GEO", header=3)
    dim_geo = pd.read_excel(baseline, sheet_name="DIM_GEO", header=3)
    return evaluate_frames(data, dictionary, notes, baseline_communes, crosswalk, dim_geo, sheet_names=excel.sheet_names)


def build_metadata(candidate: Path, baseline: Path, evaluation: dict[str, Any]) -> dict[str, Any]:
    baseline_hash = sha256_file(baseline)
    return {
        "schema_version": 1,
        "phase": "V11-SMIIG-QUALIFICATION",
        "generated_on": date.today().isoformat(),
        "decision": evaluation["decision"],
        "status": "PILOTE",
        "scope": "Qualification uniquement; aucune ingestion SMIIG et aucune modification de V10.",
        "candidate": {
            "candidate_id": "TAFRA_SMIIG_COMMUNES_2023_V1_0_0",
            "expected_local_name": "2024-01-08-dataset-smiig-v2023-communes.xlsx",
            "dataset_url": DATASET_URL,
            "resource_url": RESOURCE_URL,
            "final_url": FINAL_URL,
            "producer": "TAFRA",
            "license": "CC BY 4.0",
            "version": "1.0.0 (janvier 2024)",
            "retrieved_on": "2026-09-07",
            "etag": "bcb539e2cc50312a44e9415ebdb83e59",
            "last_modified": "2024-01-25T13:33:35Z",
            "byte_size": candidate.stat().st_size,
            "sha256": sha256_file(candidate),
            "tracked": False,
        },
        "baseline": {
            "release": "V10",
            "workbook": "data/exports/excel/v10/Morocco_Electoral_Data_Warehouse_V10.xlsx",
            "sha256_before": baseline_hash,
            "sha256_after": sha256_file(baseline),
            "modified": False,
        },
        "profile": evaluation["profile"],
        "checks": evaluation["checks"],
        "anomalies": evaluation["anomalies"],
        "research_sources": [
            {"title": "Jeu SMIIG Data communes Maroc 2023", "url": DATASET_URL, "role": "source candidate et licence"},
            {"title": "Méthode SMIIG Data — TAFRA", "url": TAFRA_METHOD_URL, "role": "cadre méthodologique"},
        ],
        "next_action": (
            "Ouvrir feat/v11-smiig-governance sans modifier le candidat."
            if evaluation["decision"] == "GO"
            else "Interdire l'ingestion; demander à TAFRA une version corrigée ou une documentation explicative."
        ),
    }


def render_report(metadata: dict[str, Any]) -> str:
    profile = metadata["profile"]
    failed = [check for check in metadata["checks"] if check["status"] == "FAIL"]
    lines = [
        "V11 — QUALIFICATION DE LA SOURCE SMIIG DATA COMMUNES 2023",
        "",
        "VERSION : V11-SMIIG-QUALIFICATION (recherche, sans export warehouse)",
        "CLASSEUR CANDIDAT : 2024-01-08-dataset-smiig-v2023-communes.xlsx (non versionné)",
        f"DATE DE GÉNÉRATION : {metadata['generated_on']}",
        "PÉRIMÈTRE : communes de plus de 50 000 habitants, mesures 2020–2023",
        "RENVOIS : metadata/v11_smiig_source_candidates.json ; issue GitHub #7 ; V10 baseline immuable",
        "",
        f"DÉCISION BINAIRE : {metadata['decision']}",
        f"STATUT DE COUVERTURE : {metadata['status']}",
        "",
        "Aucune ligne SMIIG n'a été ingérée. Aucun export V11 n'a été produit et V10 n'a pas été modifié.",
        "",
        "PROVENANCE",
        f"Jeu : {metadata['candidate']['dataset_url']}",
        f"Ressource : {metadata['candidate']['resource_url']}",
        f"Producteur : {metadata['candidate']['producer']}",
        f"Licence : {metadata['candidate']['license']}",
        f"Version : {metadata['candidate']['version']}",
        f"Taille : {metadata['candidate']['byte_size']} octets",
        f"ETag : {metadata['candidate']['etag']}",
        f"SHA-256 : {metadata['candidate']['sha256']}",
        "",
        "PROFIL AGRÉGÉ",
        f"Lignes × colonnes : {profile['rows']} × {profile['columns']}",
        f"Unités territoriales : {profile['units']}",
        f"Années : {profile['years']}",
        f"Types géographiques : {json.dumps(profile['geography_types'], ensure_ascii=False)}",
        f"Couverture de l'univers V10 : {profile['v10_coverage_percent']} % ({profile['units']}/{profile['v10_universe']})",
        f"Valeurs optionnelles nulles : {json.dumps(profile['optional_nulls'], ensure_ascii=False)}",
        "",
        "CRITÈRES OBLIGATOIRES",
    ]
    for check in metadata["checks"]:
        lines.append(f"[{check['status']}] {check['check_id']} — observé={json.dumps(check['observed'], ensure_ascii=False)}")
        if check["note"]:
            lines.append(f"  Note : {check['note']}")
    lines.extend(["", "BLOQUEURS"])
    if failed:
        lines.extend(f"- {check['check_id']}" for check in failed)
    else:
        lines.append("Aucun.")
    lines.extend(["", "ANOMALIES PSEUDONYMISÉES"])
    for anomaly in metadata["anomalies"]:
        lines.append(
            f"{anomaly['anomaly_id']} — type={anomaly['type']} — ligne={anomaly['source_row_number']} "
            f"— colonne={anomaly['column']} — statut={anomaly['status']}"
        )
    if not metadata["anomalies"]:
        lines.append("Aucune.")
    lines.extend(
        [
            "",
            "LIMITES",
            "La couverture est volontairement partielle et reste PILOTE; elle ne représente pas les 1 538 unités de V10.",
            "Les notes indiquent que les scores des villes à arrondissements sont répliqués sur chaque arrondissement.",
            "La source ne contient ni personne ni rôle individuel; aucune résolution d'identité n'est effectuée.",
            "Aucune anomalie n'est corrigée et aucune valeur n'est reconstruite dans cette phase.",
            "",
            "COMMANDE DE REPRODUCTION",
            "python -m morocco_elections qualify smiig --candidate "
            "data/staging/v11_smiig/source_candidates/2024-01-08-dataset-smiig-v2023-communes.xlsx --baseline v10",
            "",
            "SUITE CONDITIONNELLE",
            metadata["next_action"],
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def qualify_candidate(
    candidate: str | Path,
    baseline: str = "v10",
    metadata_output: str | Path | None = None,
    decision_output: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> int:
    if baseline != "v10":
        raise ValueError("La qualification SMIIG accepte uniquement la baseline v10")
    candidate_path = Path(candidate).resolve()
    paths = get_paths(data_dir)
    baseline_path = paths.v10_workbook
    if not candidate_path.is_file() or not baseline_path.is_file():
        print(f"SMIIG_QUALIFICATION_FAILED candidate={candidate_path.is_file()} baseline={baseline_path.is_file()}")
        return 2
    baseline_hash = sha256_file(baseline_path)
    try:
        evaluation = load_and_evaluate(candidate_path, baseline_path)
    except (OSError, ValueError, KeyError) as exc:
        print(f"SMIIG_QUALIFICATION_FAILED fichier illisible ou schéma invalide: {exc}")
        return 2
    if sha256_file(baseline_path) != baseline_hash:
        raise RuntimeError("La baseline V10 a changé pendant la qualification SMIIG")
    metadata = build_metadata(candidate_path, baseline_path, evaluation)
    metadata_path = Path(metadata_output).resolve() if metadata_output else paths.v11_smiig_candidate_metadata
    report_path = Path(decision_output).resolve() if decision_output else paths.v11_smiig_decision_report
    for output in (metadata_path, report_path):
        output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(metadata), encoding="utf-8")
    print(
        f"SMIIG_QUALIFICATION_{metadata['decision']} rows={metadata['profile']['rows']} "
        f"units={metadata['profile']['units']} anomalies={len(metadata['anomalies'])}"
    )
    return 0 if metadata["decision"] == "GO" else 1
