from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.domains.identity.registry import _source_id
from morocco_elections.provenance import sha256_file
from morocco_elections.research.electoral_archives import NON_PARTY_COLUMNS


INVENTORY_PATH = PROJECT_ROOT / "metadata" / "acquisition_inventory.json"
REGISTRY_PATH = PROJECT_ROOT / "metadata" / "v13_identity_registry.json"
QUALIFICATION_PATH = PROJECT_ROOT / "metadata" / "v13_electoral_qualification.json"


def stable_result_id(contest_id: str, party_id: str) -> str:
    digest = hashlib.sha256(f"{contest_id}|{party_id}".encode("utf-8")).hexdigest()[:32].upper()
    return f"RESULT_V13_{digest}"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_path(record: dict, data_dir: str | Path | None) -> Path:
    relative = Path(record["local_path"])
    if not relative.parts or relative.parts[0].lower() != "data":
        raise RuntimeError(f"Chemin d'acquisition hors contrat: {relative}")
    return get_paths(data_dir).data_root.joinpath(*relative.parts[1:])


def _integer(value: object, field: str) -> int | None:
    if pd.isna(value):
        return None
    numeric = float(value)
    if numeric < 0 or not numeric.is_integer():
        raise RuntimeError(f"{field} doit être un entier positif ou nul: {value!r}")
    return int(numeric)


def _ratio(value: object, field: str) -> float | None:
    if pd.isna(value):
        return None
    numeric = float(value)
    if not 0 <= numeric <= 1:
        raise RuntimeError(f"{field} doit être compris entre 0 et 1: {value!r}")
    return numeric


def _contest_source_key(row: pd.Series, regional: bool) -> tuple[str, str]:
    if regional:
        source_id = _source_id(row["idSousPref"] if pd.notna(row["idSousPref"]) else row["idPrefProv"])
        return source_id, "regional_council"
    return _source_id(row["idCirconscription"]), str(row["typeListe"]).strip()


def build_electoral_core(data_dir: str | Path | None = None) -> dict[str, list[dict[str, Any]]]:
    inventory = _read_json(INVENTORY_PATH)
    registry = _read_json(REGISTRY_PATH)
    qualification = _read_json(QUALIFICATION_PATH)
    if qualification.get("ingestion_executed") is not False:
        raise RuntimeError("Artefact de qualification invalide")
    qualified = {
        item["source_id"]: set(item["measures"])
        for item in qualification["authorized_for_future_ingestion"]
    }
    records = {item["source_id"]: item for item in inventory["records"]}
    contest_lookup = {
        (item["source_system"], item["source_contest_id"], item["list_type"]): item
        for item in registry["contests"]
    }
    party_lookup = {
        (item["source_system"], item["source_record_id"].removeprefix("party:")): item
        for item in registry["crosswalks"]
        if item["entity_type"] == "party_or_alliance"
    }

    results: list[dict[str, Any]] = []
    mobilization: list[dict[str, Any]] = []
    for source_id in sorted(qualified):
        record = records[source_id]
        payload = _source_path(record, data_dir)
        if not payload.is_file() or sha256_file(payload) != record["sha256"]:
            raise RuntimeError(f"Source absente ou modifiée: {source_id}")
        frame = pd.read_excel(payload, sheet_name=0)
        party_codes = [str(column) for column in frame.columns if str(column) not in NON_PARTY_COLUMNS]
        regional = source_id.startswith("TAFRA_REGIONAL_")
        for offset, row in frame.iterrows():
            source_contest_id, list_type = _contest_source_key(row, regional)
            contest = contest_lookup[(source_id, source_contest_id, list_type)]
            source_row = int(offset) + 2
            if "party_votes" in qualified[source_id]:
                for party_code in party_codes:
                    votes = _integer(row[party_code], f"{source_id}:{source_row}:{party_code}")
                    if votes is None:
                        continue
                    party = party_lookup[(source_id, party_code)]
                    result = {
                        "result_id": stable_result_id(contest["contest_id"], party["canonical_id"]),
                        "contest_id": contest["contest_id"],
                        "election_id": contest["election_id"],
                        "geo_id": contest["geo_id"],
                        "party_id": party["canonical_id"],
                        "votes": votes,
                        "seats": None,
                        "source_id": source_id,
                        "evidence_id": contest["evidence_id"],
                        "source_row": source_row,
                        "source_party_code": party_code,
                        "identity_review_status": party["review_status"],
                        "quality_status": "observed",
                        "notes": "Valeur non nulle publiée; une cellule absente n'est jamais convertie en zéro.",
                    }
                    results.append(result)

            allowed = qualified[source_id]
            mobilization.append(
                {
                    "contest_id": contest["contest_id"],
                    "election_id": contest["election_id"],
                    "geo_id": contest["geo_id"],
                    "contest_seats": _integer(row.get("nSieges"), "nSieges") if "contest_seats" in allowed else None,
                    "registered_voters": _integer(row.get("nInscrits"), "nInscrits") if "registered_voters" in allowed else None,
                    "voters": None,
                    "valid_votes": _integer(row.get("nValides"), "nValides") if "valid_votes" in allowed else None,
                    "invalid_votes": None,
                    "blank_votes": None,
                    "turnout_rate": _ratio(row.get("txParticipation"), "txParticipation") if "turnout_rate" in allowed else None,
                    "invalid_vote_rate": _ratio(row.get("pctNuls"), "pctNuls") if "invalid_vote_rate" in allowed else None,
                    "source_id": source_id,
                    "evidence_id": contest["evidence_id"],
                    "source_row": source_row,
                    "quality_status": "observed_partial_measures",
                    "notes": "Seules les mesures GO directement publiées sont renseignées; aucune reconstruction.",
                }
            )

    contests = [dict(item) for item in registry["contests"] if item["source_system"] in qualified]
    territories = [dict(item) for item in registry["new_entities"] if item["entity_type"] == "territory"]
    parties = [dict(item) for item in registry["new_entities"] if item["entity_type"] in {"party", "alliance"}]
    core = {
        "contests": contests,
        "results": results,
        "mobilization": mobilization,
        "new_territories": territories,
        "new_parties": parties,
    }
    validate_electoral_core(core)
    return core


def validate_electoral_core(core: dict[str, list[dict[str, Any]]]) -> None:
    contests = core["contests"]
    results = core["results"]
    mobilization = core["mobilization"]
    contest_ids = [item["contest_id"] for item in contests]
    result_ids = [item["result_id"] for item in results]
    if len(contests) != 639 or len(contest_ids) != len(set(contest_ids)):
        raise RuntimeError("Le noyau doit contenir 639 contests uniques")
    if len(mobilization) != 639 or {item["contest_id"] for item in mobilization} != set(contest_ids):
        raise RuntimeError("Le fait de mobilisation doit contenir exactement un enregistrement par contest")
    if len(result_ids) != len(set(result_ids)):
        raise RuntimeError("result_id dupliqué")
    result_grain = [(item["contest_id"], item["party_id"]) for item in results]
    if len(result_grain) != len(set(result_grain)):
        raise RuntimeError("Grain contest_id × party_id dupliqué")
    if any(item["contest_id"] not in set(contest_ids) for item in results):
        raise RuntimeError("Résultat rattaché à un contest inconnu")
    if any(item["votes"] < 0 or item["seats"] is not None for item in results):
        raise RuntimeError("Mesure de résultat invalide")
    geo_ids = {item["canonical_id"] for item in core["new_territories"]}
    if len(geo_ids) != 159:
        raise RuntimeError("159 territoires historiques/provisoires sont attendus")
    party_ids = {item["canonical_id"] for item in core["new_parties"]}
    if len(party_ids) != 4:
        raise RuntimeError("Quatre entités partisanes provisoires sont attendues")
