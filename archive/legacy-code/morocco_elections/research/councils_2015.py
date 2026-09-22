from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.provenance import sha256_file


EXPECTED_COLUMNS = [
    "idRegion",
    "idWilaya",
    "idPrefProv",
    "idSousPref",
    "idCommune",
    "idCirconscription",
    "region",
    "wilaya",
    "prefProv",
    "sousPref",
    "commune",
    "circonscription",
    "prenomNom",
    "parti",
    "teteDeListe",
    "role",
]
REQUIRED_COLUMNS = [column for column in EXPECTED_COLUMNS if column not in {"idSousPref", "sousPref"}]
EXPECTED_SHEETS = ["données", "dictionnaire", "notes"]
DATASET_URL = "https://bulk.openafrica.net/ko_KR/dataset/composition-des-conseils-communaux-2015-maroc"
DOWNLOAD_URL = (
    "https://open.africa/dataset/07a04224-c0ad-4861-9705-0518f5d49dbd/resource/"
    "7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/download/communes-elus-2015-1-0.xlsx"
)
FINAL_URL = (
    "https://s3-eu-west-1.amazonaws.com/cfa-openafrica/resources/"
    "7ae81ece-1b3d-4cdc-ac49-acd6ba37f6ea/communes-elus-2015-1-0.xlsx"
    "?ETag=7fca1f51b56bff28ef48caa33a9dd562"
)
MEDIA24_URL = (
    "https://medias24.com/2015/09/14/elections-en-nombre-de-sieges-les-resultats-complets-et-definitifs-"
    "commune-par-commune-parti-par-parti/"
)
TAFRA_BOOKLET_URL = "https://tafra.ma/wp-content/uploads/2023/04/LivretRegionalisation2017.pdf"
MEDIA24_PUBLISHED_SEATS = {"PAM": 6655, "PI": 5106, "PJD": 5021, "RNI": 4408, "MP": 3007, "USFP": 2656, "PPS": 1766, "UC": 1489}


@dataclass(frozen=True)
class Contract:
    expected_rows: int = 31_482
    expected_columns: int = 16
    expected_communes: int = 1_538
    expected_parties: int = 32


def _scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _digest_group(row: pd.Series) -> str:
    fields = ["idCommune", "idCirconscription", "prenomNom", "parti"]
    serialized = json.dumps([_scalar(row[field]) for field in fields], ensure_ascii=False, separators=(",", ":"))
    return "DUP2015_" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]


def _check(check_id: str, passed: bool, observed: Any, expected: Any, note: str = "") -> dict[str, Any]:
    return {
        "check_id": check_id,
        "required": True,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "expected": expected,
        "note": note,
    }


def evaluate_frames(
    data: pd.DataFrame,
    dictionary: pd.DataFrame,
    notes: pd.DataFrame,
    baseline_communes: pd.DataFrame,
    crosswalk: pd.DataFrame,
    parties: pd.DataFrame,
    *,
    contract: Contract = Contract(),
    sheet_names: list[str] | None = None,
    readable: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    sheets = sheet_names or EXPECTED_SHEETS
    checks.append(_check("xlsx_readable", readable, readable, True))
    checks.append(_check("sheets", sheets == EXPECTED_SHEETS, sheets, EXPECTED_SHEETS))
    checks.append(
        _check(
            "data_shape",
            data.shape == (contract.expected_rows, contract.expected_columns) and list(data.columns) == EXPECTED_COLUMNS,
            {"rows": len(data), "columns": len(data.columns), "column_names": list(data.columns)},
            {"rows": contract.expected_rows, "columns": contract.expected_columns, "column_names": EXPECTED_COLUMNS},
        )
    )

    baseline_ids = set(baseline_communes["idCommune"].dropna().astype(int))
    candidate_ids = set(data["idCommune"].dropna().astype(int)) if "idCommune" in data else set()
    checks.append(
        _check(
            "commune_universe",
            len(candidate_ids) == contract.expected_communes and candidate_ids == baseline_ids,
            {
                "count": len(candidate_ids),
                "missing_count": len(baseline_ids - candidate_ids),
                "extra_count": len(candidate_ids - baseline_ids),
            },
            {"count": contract.expected_communes, "identical_to_v10": True},
        )
    )

    missing = {column: int(data[column].isna().sum()) for column in REQUIRED_COLUMNS if column in data}
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    checks.append(
        _check(
            "required_values",
            not missing_columns and all(count == 0 for count in missing.values()),
            {"null_counts": missing, "missing_columns": missing_columns},
            "zero null in mandatory columns",
        )
    )

    actual_seats = data.groupby("idCommune").size().rename("observed") if "idCommune" in data else pd.Series(dtype=int)
    legal_seats = baseline_communes.set_index("idCommune")["nSieges"].rename("legal")
    seat_comparison = pd.concat([actual_seats, legal_seats], axis=1)
    mismatches = seat_comparison[seat_comparison["observed"] != seat_comparison["legal"]]
    checks.append(
        _check(
            "communal_seat_reconciliation",
            mismatches.empty and len(seat_comparison) == contract.expected_communes,
            {"communes_compared": len(seat_comparison), "mismatch_count": len(mismatches)},
            {"mismatch_count": 0},
        )
    )
    checks.append(_check("national_seat_total", len(data) == contract.expected_rows, len(data), contract.expected_rows))

    required_geo_ids = {f"TAFRA_COMM_{item}" for item in candidate_ids}
    available_geo = set(
        crosswalk.loc[
            crosswalk.get("canonical_geo_id", pd.Series(index=crosswalk.index, dtype=object)).notna(), "source_geo_id"
        ].astype(str)
    )
    checks.append(
        _check(
            "v10_geographic_crosswalk",
            required_geo_ids <= available_geo,
            {"covered": len(required_geo_ids & available_geo), "required": len(required_geo_ids)},
            {"coverage_percent": 100.0},
        )
    )

    known_parties = set(parties.get("party_id", pd.Series(dtype=object)).dropna().astype(str))
    known_parties |= set(parties.get("acronym", pd.Series(dtype=object)).dropna().astype(str))
    observed_parties = set(data.get("parti", pd.Series(dtype=object)).dropna().astype(str))
    unknown_parties = sorted(observed_parties - known_parties)
    checks.append(
        _check(
            "party_codes",
            len(observed_parties) == contract.expected_parties and not unknown_parties,
            {"count": len(observed_parties), "unknown_codes": unknown_parties},
            {"count": contract.expected_parties, "unknown_codes": []},
        )
    )

    duplicate_keys = ["idCommune", "idCirconscription", "prenomNom", "parti"]
    duplicate_rows = data[data.duplicated(duplicate_keys, keep=False)] if set(duplicate_keys) <= set(data.columns) else data.iloc[0:0]
    anomalies: list[dict[str, Any]] = []
    if not duplicate_rows.empty:
        for _, group in duplicate_rows.groupby(duplicate_keys, dropna=False, sort=False):
            differing = [column for column in data.columns if group[column].nunique(dropna=False) > 1]
            anomalies.append(
                {
                    "anomaly_id": _digest_group(group.iloc[0]),
                    "type": "duplicate_candidate_key",
                    "source_row_numbers": [int(index) + 2 for index in group.index],
                    "row_count": len(group),
                    "differing_columns": differing,
                    "status": "unresolved",
                    "decision": "no_deletion_no_ingestion",
                }
            )
    exact_duplicate_count = int(data.duplicated(list(data.columns), keep=False).sum()) if len(data.columns) else 0
    duplicate_pass = not anomalies
    checks.append(
        _check(
            "duplicate_candidates_explained",
            duplicate_pass,
            {
                "candidate_groups": len(anomalies),
                "exact_duplicate_rows": exact_duplicate_count,
                "unresolved_groups": sum(item["status"] == "unresolved" for item in anomalies),
            },
            {"unresolved_groups": 0},
            "Une différence de rôle ou de tête de liste ne prouve pas que deux sièges distincts sont valides.",
        )
    )

    dictionary_labels = set(dictionary.iloc[:, 0].dropna().astype(str)) if not dictionary.empty else set()
    notes_text = " ".join(notes.fillna("").astype(str).to_numpy().ravel()).casefold()
    head_values = set(data.get("teteDeListe", pd.Series(dtype=object)).dropna().tolist())
    roles = sorted(data.get("role", pd.Series(dtype=object)).dropna().astype(str).unique())
    role_rows = dictionary[dictionary.iloc[:, 0].astype(str) == "role"]
    role_documentation = " ".join(role_rows.fillna("").astype(str).to_numpy().ravel()).casefold()
    roles_enumerated = bool(roles) and all(role.casefold() in role_documentation for role in roles)
    domain_pass = (
        set(EXPECTED_COLUMNS) <= dictionary_labels
        and head_values <= {True, False}
        and roles_enumerated
    )
    checks.append(
        _check(
            "documented_domains",
            domain_pass,
            {"dictionary_labels": len(dictionary_labels), "head_values": sorted(str(item) for item in head_values), "role_values": roles},
            "16 columns documented; teteDeListe boolean; all role modalities explicitly enumerated",
            "Le dictionnaire définit le champ rôle mais n'énumère pas ses modalités observées.",
        )
    )
    license_pass = "cc by 4.0" in notes_text or "creativecommons.org/licenses/by/4.0" in notes_text
    checks.append(_check("license", license_pass, "CC BY 4.0" if license_pass else "not demonstrated", "CC BY 4.0"))

    critical_consistency = list(data.columns) == EXPECTED_COLUMNS and set(EXPECTED_COLUMNS) <= dictionary_labels
    checks.append(
        _check(
            "file_dictionary_notes_consistency",
            critical_consistency,
            {"undocumented_columns": sorted(set(data.columns) - dictionary_labels)},
            {"undocumented_columns": []},
        )
    )
    decision = "GO" if all(item["status"] == "PASS" for item in checks if item["required"]) else "NO_GO"
    return {
        "decision": decision,
        "checks": checks,
        "anomalies": anomalies,
        "profile": {
            "rows": len(data),
            "columns": len(data.columns),
            "communes": len(candidate_ids),
            "parties": len(observed_parties),
            "circonscriptions": int(data["idCirconscription"].nunique()) if "idCirconscription" in data else 0,
            "party_distribution": {
                str(key): int(value) for key, value in data["parti"].value_counts().sort_index().items()
            },
            "role_distribution": {
                str(key): int(value) for key, value in data["role"].value_counts().sort_index().items()
            },
            "head_of_list_distribution": {
                str(key): int(value) for key, value in data["teteDeListe"].value_counts().sort_index().items()
            },
        },
    }


def load_and_evaluate(candidate: Path, baseline_workbook: Path) -> dict[str, Any]:
    excel = pd.ExcelFile(candidate, engine="openpyxl")
    sheets = excel.sheet_names
    data = pd.read_excel(excel, sheet_name="données")
    dictionary = pd.read_excel(excel, sheet_name="dictionnaire")
    notes = pd.read_excel(excel, sheet_name="notes")
    baseline = pd.read_excel(baseline_workbook, sheet_name="RAW_COMM2015_FULL", header=3)
    crosswalk = pd.read_excel(baseline_workbook, sheet_name="CROSSWALK_GEO", header=3)
    parties = pd.read_excel(baseline_workbook, sheet_name="DIM_PARTY", header=3)
    return evaluate_frames(data, dictionary, notes, baseline, crosswalk, parties, sheet_names=sheets)


def build_metadata(candidate: Path, baseline_workbook: Path, evaluation: dict[str, Any]) -> dict[str, Any]:
    candidate_party_totals = evaluation["profile"]["party_distribution"]
    media24_comparison = {
        party: {
            "candidate_2019": candidate_party_totals.get(party),
            "published_2015": published,
            "difference": candidate_party_totals.get(party, 0) - published,
        }
        for party, published in MEDIA24_PUBLISHED_SEATS.items()
    }
    return {
        "schema_version": 1,
        "phase": "V11-A",
        "generated_on": date.today().isoformat(),
        "decision": evaluation["decision"],
        "scope": "Qualification uniquement; aucune ingestion et aucune modification de V10.",
        "candidate": {
            "candidate_id": "TAFRA_COUNCILS_2015_V1_0_0",
            "expected_local_name": "communes-elus-2015-1-0.xlsx",
            "dataset_url": DATASET_URL,
            "download_url": DOWNLOAD_URL,
            "final_url": FINAL_URL,
            "producer": "Association TAFRA; copie déclarée de elections.ma",
            "license": "CC BY 4.0",
            "version": "1.0.0 (novembre 2019)",
            "retrieved_on": date.today().isoformat(),
            "etag": "7fca1f51b56bff28ef48caa33a9dd562",
            "last_modified": "2024-02-05T13:15:49Z",
            "byte_size": candidate.stat().st_size,
            "sha256": sha256_file(candidate),
            "tracked": False,
        },
        "baseline": {
            "release": "V10",
            "workbook": "data/exports/excel/v10/Morocco_Electoral_Data_Warehouse_V10.xlsx",
            "sha256_before": sha256_file(baseline_workbook),
            "sha256_after": sha256_file(baseline_workbook),
            "modified": False,
        },
        "profile": evaluation["profile"],
        "checks": evaluation["checks"],
        "anomalies": evaluation["anomalies"],
        "secondary_controls": [
            {
                "source": "Médias24",
                "url": MEDIA24_URL,
                "usage": "contrôle externe agrégé uniquement",
                "comparison": media24_comparison,
                "interpretation": "Écarts attribuables à la version 2019 corrigée et/ou au périmètre; jamais utilisés pour reconstruire des lignes.",
            },
            {
                "source": "Livret TAFRA — Régionalisation",
                "url": TAFRA_BOOKLET_URL,
                "usage": "contrôle externe agrégé; inclut 819 élus d'arrondissement",
            },
        ],
        "next_action": (
            "Ouvrir feat/v11b-ingest-councils-2015."
            if evaluation["decision"] == "GO"
            else "Interdire l'ingestion; conserver la preuve du blocage et passer au chantier SMIIG."
        ),
    }


def render_decision(metadata: dict[str, Any]) -> str:
    profile = metadata["profile"]
    lines = [
        "V11-A — DÉCISION DE QUALIFICATION DES CONSEILS COMMUNAUX 2015",
        "",
        "VERSION : V11-A (recherche, sans export warehouse)",
        "CLASSEUR CANDIDAT : communes-elus-2015-1-0.xlsx (non versionné)",
        f"DATE DE GÉNÉRATION : {metadata['generated_on']}",
        "PÉRIMÈTRE : qualification de la composition des conseils communaux issue du scrutin de 2015",
        "RENVOIS : metadata/v11a_source_candidates.json ; V10 reste la baseline immuable",
        "",
        f"DÉCISION BINAIRE : {metadata['decision']}",
        "",
        "La décision porte uniquement sur l'aptitude à une ingestion ultérieure. Aucune ligne n'a été ingérée,",
        "aucun classeur V10 n'a été modifié et aucun siège n'a été reconstruit à partir des voix.",
        "",
        "PROVENANCE",
        f"Page du jeu : {metadata['candidate']['dataset_url']}",
        f"URL finale : {metadata['candidate']['final_url']}",
        f"Producteur/source déclarée : {metadata['candidate']['producer']}",
        f"Licence : {metadata['candidate']['license']}",
        f"Version : {metadata['candidate']['version']}",
        f"Taille : {metadata['candidate']['byte_size']} octets",
        f"ETag : {metadata['candidate']['etag']}",
        f"SHA-256 : {metadata['candidate']['sha256']}",
        "",
        "PROFIL AGRÉGÉ",
        f"Lignes : {profile['rows']}",
        f"Colonnes : {profile['columns']}",
        f"Communes : {profile['communes']}",
        f"Circonscriptions : {profile['circonscriptions']}",
        f"Partis/codes source : {profile['parties']}",
        "",
        "CRITÈRES OBLIGATOIRES",
    ]
    for check in metadata["checks"]:
        lines.append(f"[{check['status']}] {check['check_id']} — observé={json.dumps(check['observed'], ensure_ascii=False)}")
        if check["note"]:
            lines.append(f"  Note : {check['note']}")
    lines.extend(["", "ANOMALIES PSEUDONYMISÉES"])
    if metadata["anomalies"]:
        for item in metadata["anomalies"]:
            lines.append(
                f"{item['anomaly_id']} — lignes source {item['source_row_numbers']} — "
                f"colonnes divergentes {item['differing_columns']} — statut {item['status']}"
            )
    else:
        lines.append("Aucune.")
    lines.extend(["", "DISTRIBUTION AGRÉGÉE DES PARTIS"])
    lines.extend(f"{key} : {value}" for key, value in profile["party_distribution"].items())
    lines.extend(["", "DISTRIBUTION AGRÉGÉE DES RÔLES"])
    lines.extend(f"{key} : {value}" for key, value in profile["role_distribution"].items())
    lines.extend(
        [
            "",
            "LIMITES ET INTERPRÉTATION",
            "Les publications externes servent seulement de contrôles agrégés. Elles ne remplacent jamais le fichier granulaire.",
            "Le dictionnaire définit le champ role mais n'énumère pas formellement toutes ses modalités.",
            "Une égalité de nom, commune, circonscription et parti ne suffit pas à expliquer deux lignes de siège.",
            "Aucun nom d'élu ni extrait RAW n'est reproduit dans ce rapport.",
            "",
            "CONTRÔLES EXTERNES",
            f"Médias24 : {MEDIA24_URL}",
            "Comparaison candidat 2019 / publication Médias24 2015 (écart) :",
            *[
                f"{party} : {values['candidate_2019']} / {values['published_2015']} ({values['difference']:+d})"
                for party, values in metadata["secondary_controls"][0]["comparison"].items()
            ],
            "Ces écarts sont qualifiés comme différences de version et/ou de périmètre; aucune ligne n'est reconstruite.",
            f"Livret TAFRA : {TAFRA_BOOKLET_URL}",
            "Le livret indique que les 819 élus d'arrondissement sont inclus dans les élus communaux.",
            "",
            "COMMANDE DE REPRODUCTION",
            "python -m morocco_elections qualify councils-2015 --candidate "
            "data/staging/v11a/source_candidates/communes-elus-2015-1-0.xlsx --baseline v10",
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
        raise ValueError("V11-A accepte uniquement la baseline v10")
    candidate_path = Path(candidate).resolve()
    paths = get_paths(data_dir)
    baseline_path = paths.v10_workbook
    if not candidate_path.is_file():
        print(f"QUALIFICATION_FAILED candidate absent: {candidate_path}")
        return 2
    if not baseline_path.is_file():
        print(f"QUALIFICATION_FAILED baseline absente: {baseline_path}")
        return 2
    baseline_hash = sha256_file(baseline_path)
    try:
        evaluation = load_and_evaluate(candidate_path, baseline_path)
    except (OSError, ValueError, KeyError) as exc:
        print(f"QUALIFICATION_FAILED fichier illisible ou schéma invalide: {exc}")
        return 2
    if sha256_file(baseline_path) != baseline_hash:
        raise RuntimeError("La baseline V10 a changé pendant la qualification")
    metadata = build_metadata(candidate_path, baseline_path, evaluation)
    metadata["baseline"]["sha256_before"] = baseline_hash
    metadata["baseline"]["sha256_after"] = sha256_file(baseline_path)
    metadata["baseline"]["modified"] = metadata["baseline"]["sha256_before"] != metadata["baseline"]["sha256_after"]
    metadata_path = Path(metadata_output).resolve() if metadata_output else paths.v11a_candidate_metadata
    decision_path = Path(decision_output).resolve() if decision_output else paths.v11a_decision_report
    for output in (metadata_path, decision_path):
        output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decision_path.write_text(render_decision(metadata), encoding="utf-8")
    print(
        f"QUALIFICATION_{metadata['decision']} rows={metadata['profile']['rows']} "
        f"communes={metadata['profile']['communes']} anomalies={len(metadata['anomalies'])}"
    )
    return 0 if metadata["decision"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit("Utiliser python -m morocco_elections qualify councils-2015 --candidate <xlsx> --baseline v10")
