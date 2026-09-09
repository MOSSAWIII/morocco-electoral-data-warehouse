from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.provenance import sha256_file


INVENTORY_PATH = PROJECT_ROOT / "metadata" / "acquisition_inventory.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "metadata" / "v13_electoral_sources_profile.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "research" / "V13_ELECTORAL_SOURCES_PROFILE.txt"

SOURCE_SPECS = {
    "TAFRA_LEGISLATIVE_RESULTS_2002": {
        "year": 2002,
        "election_type": "legislative",
        "election_id": "LEG2002",
        "key_fields": ["idCirconscription", "typeListe"],
        "destination": "ARCHIVE_ONLY",
        "limitations": [
            "La notice déclare la source primaire incomplète, la source secondaire erronée et les petits partis absents."
        ],
    },
    "TAFRA_LEGISLATIVE_RESULTS_2007": {
        "year": 2007,
        "election_type": "legislative",
        "election_id": "LEG2007",
        "key_fields": ["idCirconscription", "typeListe"],
        "destination": "CANONICAL_CANDIDATE",
        "limitations": ["Les 30 sièges de la liste nationale ne figurent pas dans nSieges."],
    },
    "TAFRA_LEGISLATIVE_RESULTS_2011": {
        "year": 2011,
        "election_type": "legislative",
        "election_id": "LEG2011",
        "key_fields": ["idCirconscription", "typeListe"],
        "destination": "CANONICAL_CANDIDATE",
        "limitations": [
            "Les données ont été partagées par deux chercheurs et ne constituent pas une publication officielle primaire.",
            "Les 90 sièges de la liste nationale ne figurent pas dans nSieges."
        ],
    },
    "TAFRA_LEGISLATIVE_RESULTS_2016": {
        "year": 2016,
        "election_type": "legislative",
        "election_id": "LEG2016",
        "key_fields": ["idCirconscription", "typeListe"],
        "destination": "CANONICAL_CANDIDATE",
        "limitations": [
            "nInscrits et pctNuls sont entièrement vides.",
            "nSieges est vide pour les lignes de liste nationale; le total renseigné couvre 305 sièges locaux."
        ],
    },
    "TAFRA_LEGISLATIVE_RESULTS_2021": {
        "year": 2021,
        "election_type": "legislative",
        "election_id": "LEG2021",
        "key_fields": ["idCirconscription", "typeListe"],
        "destination": "CANONICAL_CANDIDATE",
        "limitations": [
            "nInscrits est entièrement vide.",
            "invalide est constant à zéro alors que la notice indique que les votes nuls ne sont pas publiés; ce champ est inutilisable."
        ],
    },
    "TAFRA_REGIONAL_RESULTS_2015": {
        "year": 2015,
        "election_type": "regional",
        "election_id": "REG2015",
        "key_fields": ["source_geo_unit"],
        "destination": "CANONICAL_CANDIDATE",
        "limitations": ["nInscrits, nVotants et pctNuls sont entièrement vides."],
    },
    "TAFRA_REGIONAL_RESULTS_2021": {
        "year": 2021,
        "election_type": "regional",
        "election_id": "REG2021",
        "key_fields": ["source_geo_unit"],
        "destination": "CANONICAL_CANDIDATE",
        "limitations": ["nInscrits et invalide sont entièrement vides."],
    },
}

NON_PARTY_COLUMNS = {
    "idRegion", "idWilaya", "idPrefProv", "idSousPref", "idCirconscription",
    "region", "wilaya", "prefProv", "sousPref", "circonscription", "typeListe",
    "nSieges", "nInscrits", "txParticipation", "pctNuls", "nValides", "nVotants", "invalide",
    "repPctFemmes", "repAge34", "repAge3544", "repAge4554", "repAge55",
    "repEduSans", "repEdu1aire", "repEdu2aire", "repEduSup",
}
PERSONAL_HEADER = re.compile(r"(^|_)(nom|prenom|cin|cnie|adresse|telephone|email)(_|$)", re.IGNORECASE)


def build_profile(data_dir: str | Path | None, as_of: str, baseline: str = "v12") -> dict:
    date.fromisoformat(as_of)
    if baseline.lower() != "v12":
        raise ValueError("La baseline doit être v12")
    paths = get_paths(data_dir)
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    records = {item["source_id"]: item for item in inventory["records"]}
    missing = sorted(set(SOURCE_SPECS) - records.keys())
    if missing:
        raise RuntimeError(f"Sources absentes de l'inventaire: {missing}")
    if not paths.v12_workbook.is_file():
        raise RuntimeError(f"Classeur V12 absent: {paths.v12_workbook}")

    parties = pd.read_excel(paths.v12_workbook, sheet_name="DIM_PARTY", header=3)
    party_crosswalk = pd.read_excel(paths.v12_workbook, sheet_name="CROSSWALK_PARTY", header=3)
    elections = pd.read_excel(paths.v12_workbook, sheet_name="DIM_ELECTION", header=3)
    known_party_codes = set(parties["party_id"].dropna().astype(str).str.strip())
    known_party_codes |= set(party_crosswalk["raw_source_code"].dropna().astype(str).str.strip())
    election_rows = elections.set_index("election_id").to_dict("index")

    profiles = []
    for source_id, spec in SOURCE_SPECS.items():
        record = records[source_id]
        relative = Path(record["local_path"])
        payload = paths.data_root / relative.relative_to("data")
        if not payload.is_file() or sha256_file(payload) != record["sha256"]:
            raise RuntimeError(f"Payload absent ou modifié: {source_id}")
        profiles.append(_profile_workbook(payload, record, spec, known_party_codes, election_rows))

    destination_counts = {
        destination: sum(item["destination"] == destination for item in profiles)
        for destination in ("CANONICAL_CANDIDATE", "REFERENCE", "CONTEXTUAL", "PILOT", "BLOCKED", "ARCHIVE_ONLY")
    }
    return {
        "schema_version": 1,
        "phase": "V13_SOURCE_PROFILE",
        "baseline_release": "V12",
        "as_of": as_of,
        "scope": "Sept archives TAFRA de résultats législatifs 2002–2021 et régionaux 2015–2021.",
        "source_count": len(profiles),
        "destination_counts": destination_counts,
        "integration_authorized": False,
        "profiles": profiles,
        "next_gate": "Construire les crosswalks geo_id, party_id, election_id et contest_id pour les six CANONICAL_CANDIDATE.",
    }


def _profile_workbook(
    payload: Path,
    record: dict,
    spec: dict,
    known_party_codes: set[str],
    election_rows: dict,
) -> dict:
    data = pd.read_excel(payload, sheet_name=0)
    dictionary = pd.read_excel(payload, sheet_name="dictionnaire")
    headers = [str(column).strip() for column in data.columns]
    dictionary_labels = set(dictionary.iloc[:, 0].dropna().astype(str).str.strip())
    party_codes = [column for column in headers if column not in NON_PARTY_COLUMNS]
    party_values = data[party_codes].apply(pd.to_numeric, errors="coerce")
    working = data.copy()
    if spec["key_fields"] == ["source_geo_unit"]:
        working["source_geo_unit"] = working["idSousPref"].where(
            working["idSousPref"].notna(), working["idPrefProv"]
        )
    keys = spec["key_fields"]
    missing_key_cells = int(working[keys].isna().sum().sum())
    duplicate_key_rows = int(working.duplicated(keys, keep=False).sum())
    empty_columns = [column for column in headers if int(data[column].notna().sum()) == 0]
    constant_zero_columns = [
        column
        for column in headers
        if data[column].notna().any()
        and pd.to_numeric(data[column], errors="coerce").notna().all()
        and (pd.to_numeric(data[column], errors="coerce") == 0).all()
    ]
    turnout = pd.to_numeric(data.get("txParticipation"), errors="coerce")
    seat_total = _integer_sum(data.get("nSieges"))
    election = election_rows.get(spec["election_id"], {})
    expected_seats = _optional_int(election.get("total_seats"))
    recognized = sorted(set(party_codes) & known_party_codes)
    unrecognized = sorted(set(party_codes) - known_party_codes)
    personal_headers = sorted(column for column in headers if PERSONAL_HEADER.search(column))
    source_geo_units = working[keys].drop_duplicates().shape[0]

    limitations = list(spec["limitations"])
    null_party_cells = int(party_values.isna().sum().sum())
    if null_party_cells:
        limitations.append(
            f"{null_party_cells} cellules parti sont vides; elles ne seront pas converties en zéro sans règle source explicite."
        )
    missing_dictionary = sorted(set(headers) - dictionary_labels)
    extra_dictionary = sorted(dictionary_labels - set(headers))
    if missing_dictionary or extra_dictionary:
        limitations.append("Le dictionnaire et les en-têtes physiques ne concordent pas exactement.")
    if unrecognized:
        limitations.append(f"{len(unrecognized)} codes partisans nécessitent un crosswalk ou une qualification temporelle.")

    valid_reconciliation = None
    if "nValides" in data.columns and data["nValides"].notna().any():
        valid_votes = pd.to_numeric(data["nValides"], errors="coerce")
        differences = party_values.sum(axis=1, min_count=1) - valid_votes
        valid_reconciliation = {
            "rows_compared": int(differences.notna().sum()),
            "mismatched_rows": int((differences.fillna(0) != 0).sum()),
            "difference_sum": _optional_int(differences.sum(min_count=1)),
        }

    return {
        "source_id": record["source_id"],
        "sha256": record["sha256"],
        "byte_size": record["byte_size"],
        "year": spec["year"],
        "election_type": spec["election_type"],
        "election_id": spec["election_id"],
        "probable_grain": " × ".join(keys),
        "key_fields": keys,
        "rows": int(len(data)),
        "columns": int(len(headers)),
        "useful_rows": int(data.dropna(how="all").shape[0]),
        "geographic_units": int(source_geo_units),
        "duplicate_key_rows": duplicate_key_rows,
        "missing_key_cells": missing_key_cells,
        "completely_empty_columns": empty_columns,
        "constant_zero_columns": constant_zero_columns,
        "party_code_count": len(party_codes),
        "party_codes": party_codes,
        "recognized_party_codes": recognized,
        "unrecognized_party_codes": unrecognized,
        "party_null_cells": null_party_cells,
        "negative_party_cells": int((party_values < 0).sum().sum()),
        "party_vote_total": _integer_sum(party_values.stack()),
        "seat_total_in_file": seat_total,
        "election_total_seats_v12": expected_seats,
        "seat_scope_gap": expected_seats - seat_total if expected_seats is not None and seat_total is not None else None,
        "turnout_nonempty_rows": int(turnout.notna().sum()),
        "turnout_out_of_range_rows": int(((turnout < 0) | (turnout > 1)).sum()),
        "valid_vote_reconciliation": valid_reconciliation,
        "dictionary_missing_headers": missing_dictionary,
        "dictionary_extra_labels": extra_dictionary,
        "personal_data_headers": personal_headers,
        "existing_contest_crosswalk": False,
        "destination": spec["destination"],
        "integration_gate": "ARCHIVE_ONLY" if spec["destination"] == "ARCHIVE_ONLY" else "PENDING_CROSSWALKS",
        "limitations": limitations,
    }


def _integer_sum(values: object) -> int | None:
    if values is None:
        return None
    numeric = pd.to_numeric(values, errors="coerce")
    value = numeric.sum(min_count=1)
    return None if pd.isna(value) else int(value)


def _optional_int(value: object) -> int | None:
    return None if pd.isna(value) else int(value)


def validate_profile(profile: dict) -> list[str]:
    errors = []
    if profile.get("schema_version") != 1 or profile.get("phase") != "V13_SOURCE_PROFILE":
        errors.append("métadonnées racine invalides")
    if profile.get("baseline_release") != "V12" or profile.get("source_count") != 7:
        errors.append("baseline ou nombre de sources invalide")
    if profile.get("integration_authorized") is not False:
        errors.append("le profil ne doit pas autoriser l'ingestion")
    profiles = profile.get("profiles", [])
    if len(profiles) != 7 or len({item.get("source_id") for item in profiles}) != 7:
        errors.append("les sept profils uniques sont requis")
    allowed = {"CANONICAL_CANDIDATE", "REFERENCE", "CONTEXTUAL", "PILOT", "BLOCKED", "ARCHIVE_ONLY"}
    actual_counts = {destination: sum(item.get("destination") == destination for item in profiles) for destination in allowed}
    if profile.get("destination_counts") != actual_counts:
        errors.append("les totaux par destination ne concordent pas avec les profils")
    required = {
        "source_id", "sha256", "year", "election_type", "election_id", "probable_grain", "key_fields",
        "rows", "columns", "useful_rows", "geographic_units", "duplicate_key_rows", "missing_key_cells",
        "completely_empty_columns", "party_codes", "personal_data_headers", "destination", "integration_gate", "limitations",
    }
    for item in profiles:
        missing = required - item.keys()
        if missing:
            errors.append(f"{item.get('source_id')}: champs absents {sorted(missing)}")
        if item.get("destination") not in allowed:
            errors.append(f"{item.get('source_id')}: destination invalide")
        if not isinstance(item.get("duplicate_key_rows"), int) or not isinstance(item.get("missing_key_cells"), int):
            errors.append(f"{item.get('source_id')}: compteurs de clé invalides")
        if item.get("destination") == "CANONICAL_CANDIDATE" and (
            item.get("duplicate_key_rows") != 0 or item.get("missing_key_cells") != 0
        ):
            errors.append(f"{item.get('source_id')}: candidat canonique avec grain source invalide")
        if item.get("personal_data_headers"):
            errors.append(f"{item.get('source_id')}: colonnes personnelles détectées")
    return errors


def render_report(profile: dict) -> str:
    lines = [
        "V13 — PROFIL CONSOLIDÉ DES ARCHIVES ÉLECTORALES",
        "",
        f"Baseline : {profile['baseline_release']}",
        f"Date d'observation : {profile['as_of']}",
        f"Sources : {profile['source_count']}",
        "Ingestion autorisée : NON",
        "",
        "MATRICE",
        "",
        "Source | Grain | Période | Couverture | Clés | Provenance/limites | Destination",
    ]
    for item in profile["profiles"]:
        coverage = f"{item['useful_rows']}/{item['rows']} lignes; {item['geographic_units']} unités"
        keys = ", ".join(item["key_fields"])
        limitations = " ".join(item["limitations"])
        lines.append(
            f"{item['source_id']} | {item['probable_grain']} | {item['year']} | {coverage} | "
            f"{keys} | {limitations} | {item['destination']}"
        )
    lines.extend(["", "CONTRÔLES STRUCTURELS", ""])
    for item in profile["profiles"]:
        lines.append(
            f"- {item['source_id']}: doublons={item['duplicate_key_rows']}; clés manquantes={item['missing_key_cells']}; "
            f"partis={item['party_code_count']}; codes non raccordés={len(item['unrecognized_party_codes'])}; "
            f"sièges fichier={item['seat_total_in_file']}; total scrutin V12={item['election_total_seats_v12']}; "
            f"colonnes vides={','.join(item['completely_empty_columns']) or 'aucune'}."
        )
    lines.extend(
        [
            "",
            "DÉCISION",
            "",
            "Six sources sont des candidats canoniques à qualifier par crosswalks; 2002 reste ARCHIVE_ONLY.",
            "Aucune source n'est encore autorisée à rejoindre V13.",
            f"Prochain gate : {profile['next_gate']}",
            "",
        ]
    )
    return "\n".join(lines)


def generate(
    data_dir: str | Path | None,
    as_of: str,
    baseline: str = "v12",
    output: str | Path | None = None,
    report_output: str | Path | None = None,
) -> int:
    profile = build_profile(data_dir, as_of, baseline)
    errors = validate_profile(profile)
    if errors:
        print("ELECTORAL_SOURCE_PROFILE_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    output_path = Path(output) if output else DEFAULT_OUTPUT
    report_path = Path(report_output) if report_output else DEFAULT_REPORT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(profile), encoding="utf-8")
    print(f"ELECTORAL_SOURCE_PROFILE_OK sources=7 output={output_path}")
    return 0
