from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.provenance import sha256_file
from morocco_elections.research.electoral_archives import (
    INVENTORY_PATH,
    NON_PARTY_COLUMNS,
    SOURCE_SPECS,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "metadata" / "v13_identity_registry.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "research" / "V13_IDENTITY_REGISTRY.txt"

CURRENT_REGION_MAP = {str(623 + index): f"MA-{index + 1:02d}" for index in range(12)}
CASABLANCA_DISTRICTS = {
    "casablanca anfa": "GEO_PA_CASABLANCA_ANFA",
    "al fida mers sultan": "GEO_PA_AL_FIDA_MERS_SULTAN",
    "ain sebaa hay mohammadi": "GEO_PA_AIN_SEBAA_HAY_MOHAMMADI",
    "ain chock": "GEO_PA_AIN_CHOCK",
    "hay hassani": "GEO_PA_HAY_HASSANI",
    "sidi bernoussi": "GEO_PA_SIDI_BERNOUSSI",
    "ben m sick": "GEO_PA_BEN_MSIK",
    "moulay rachid": "GEO_PA_MOULAY_RACHID",
    "a n seba hay mohammadi": "GEO_PA_AIN_SEBAA_HAY_MOHAMMADI",
    "a n chock": "GEO_PA_AIN_CHOCK",
}
PARTY_OVERRIDES = {
    "BH": ("BH", "party", "Parti d'Al Badil al Hadari"),
    "PFC": ("PFC", "party", "Parti des Forces Citoyennes"),
    "PADSCNIPSU": ("ALLIANCE_PADS_CNI_PSU_2007", "alliance", "Coalition PADS-CNI-PSU"),
    "PNDALAHD": ("ALLIANCE_PND_ALAHD_2007", "alliance", "Coalition PND-Al Ahd"),
}
DICTIONARY_ALIASES = {"ALAHD": "AIAD"}


def normalize_label(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def stable_contest_id(election_id: str, list_type: str, source_contest_id: str) -> str:
    token = f"{election_id}|{list_type}|{source_contest_id}"
    suffix = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12].upper()
    return f"CONTEST_{election_id}_{normalize_label(list_type).upper().replace(' ', '_')}_{suffix}"


def build_registry(data_dir: str | Path | None, as_of: str, baseline: str = "v12") -> dict:
    date.fromisoformat(as_of)
    if baseline.lower() != "v12":
        raise ValueError("La baseline doit être v12")
    paths = get_paths(data_dir)
    if not paths.v12_workbook.is_file():
        raise RuntimeError(f"Classeur V12 absent: {paths.v12_workbook}")
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    acquired = {item["source_id"]: item for item in inventory["records"]}

    geo = pd.read_excel(paths.v12_workbook, sheet_name="DIM_GEO", header=3)
    parties = pd.read_excel(paths.v12_workbook, sheet_name="DIM_PARTY", header=3)
    party_crosswalk = pd.read_excel(paths.v12_workbook, sheet_name="CROSSWALK_PARTY", header=3)
    elections = pd.read_excel(paths.v12_workbook, sheet_name="DIM_ELECTION", header=3)
    election_lookup = elections.set_index("election_id").to_dict("index")
    province_lookup = _unique_geo_lookup(geo[geo["geo_type"].eq("province_prefecture")])
    party_lookup = _party_lookup(parties, party_crosswalk)

    crosswalks: list[dict] = []
    contests: list[dict] = []
    new_entities: dict[str, dict] = {}
    for source_id, spec in SOURCE_SPECS.items():
        if spec["destination"] != "CANONICAL_CANDIDATE":
            continue
        record = acquired.get(source_id)
        if not record:
            raise RuntimeError(f"Source candidate absente: {source_id}")
        relative = Path(record["local_path"])
        payload = paths.data_root / relative.relative_to("data")
        if not payload.is_file() or sha256_file(payload) != record["sha256"]:
            raise RuntimeError(f"Payload absent ou modifié: {source_id}")
        frame = pd.read_excel(payload, sheet_name=0)
        dictionary = pd.read_excel(payload, sheet_name="dictionnaire")
        election = election_lookup.get(spec["election_id"])
        if not election:
            raise RuntimeError(f"Élection absente de V12: {spec['election_id']}")
        election_date = _iso_date(election["election_date"])
        evidence_id = record["acquisition_id"]

        crosswalks.append(
            _crosswalk(
                "election",
                source_id,
                f"{spec['election_type']}:{spec['year']}",
                spec["election_id"],
                f"{spec['election_type']} {spec['year']}",
                election_date,
                evidence_id,
                "type+year+official_date",
                1.0,
                "automatic",
            )
        )
        region_map = _register_regions(
            frame, source_id, spec, election_date, evidence_id, crosswalks, new_entities
        )
        admin_map = _register_admin_units(
            frame,
            source_id,
            spec,
            election_date,
            evidence_id,
            province_lookup,
            crosswalks,
            new_entities,
        )
        _register_parties(
            frame,
            dictionary,
            source_id,
            election_date,
            evidence_id,
            party_lookup,
            crosswalks,
            new_entities,
        )
        contests.extend(
            _register_contests(frame, source_id, spec, election_date, evidence_id, region_map, admin_map)
        )

    crosswalks.sort(key=lambda item: (item["entity_type"], item["source_system"], item["source_record_id"]))
    contests.sort(key=lambda item: item["contest_id"])
    entities = sorted(new_entities.values(), key=lambda item: (item["entity_type"], item["canonical_id"]))
    statuses = Counter(item["review_status"] for item in crosswalks)
    by_type = Counter(item["entity_type"] for item in crosswalks)
    warnings = sum("�" in str(item.get("source_label", "")) for item in crosswalks)
    limitations = [
        "Les unités administratives de 2007 et 2011 sont conservées comme snapshots historiques; leurs ponts vers le découpage courant restent à valider.",
        "Huit préfectures d'arrondissements de Casablanca sont des entités agrégées distinctes des arrondissements qui les composent.",
        "Quatre codes politiques historiques de 2007 créent deux partis et deux alliances provisoires à confirmer.",
        "Le registre normalise les identités mais n'autorise pas encore l'ingestion des faits V13."
    ]
    if warnings:
        limitations.insert(
            3,
            "Les caractères de remplacement déjà présents dans certains libellés source sont conservés et signalés; ils ne sont pas reconstruits.",
        )
    return {
        "schema_version": 1,
        "registry_version": "1.0.0",
        "phase": "V13_IDENTITY_REGISTRY",
        "baseline_release": "V12",
        "as_of": as_of,
        "scope": "Six sources candidates: législatives 2007–2021 et régionales 2015–2021.",
        "integration_authorized": False,
        "counts": {
            "crosswalks": len(crosswalks),
            "contests": len(contests),
            "new_entities": len(entities),
            "crosswalks_by_entity_type": dict(sorted(by_type.items())),
            "review_statuses": dict(sorted(statuses.items())),
            "source_labels_with_replacement_character": warnings,
        },
        "new_entities": entities,
        "crosswalks": crosswalks,
        "contests": contests,
        "limitations": limitations,
        "next_gate": "Valider les ponts géographiques historiques et les quatre entités partisanes de 2007, puis qualifier les faits source.",
    }


def _unique_geo_lookup(frame: pd.DataFrame) -> dict[str, tuple[str, str]]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for row in frame[["geo_id", "geo_name"]].dropna().itertuples(index=False):
        grouped.setdefault(normalize_label(row.geo_name), []).append((str(row.geo_id), str(row.geo_name)))
    return {key: values[0] for key, values in grouped.items() if len(values) == 1}


def _party_lookup(parties: pd.DataFrame, crosswalk: pd.DataFrame) -> dict[str, str]:
    candidates: dict[str, set[str]] = {}
    for value in parties["party_id"].dropna().astype(str):
        candidates.setdefault(value.strip(), set()).add(value.strip())
    for row in crosswalk[["raw_source_code", "canonical_party_id"]].dropna().itertuples(index=False):
        candidates.setdefault(str(row.raw_source_code).strip(), set()).add(str(row.canonical_party_id).strip())
    return {code: next(iter(values)) for code, values in candidates.items() if len(values) == 1}


def _register_regions(
    frame: pd.DataFrame,
    source_id: str,
    spec: dict,
    election_date: str,
    evidence_id: str,
    crosswalks: list[dict],
    entities: dict[str, dict],
) -> dict[str, str]:
    result = {}
    for row in frame[["idRegion", "region"]].drop_duplicates().itertuples(index=False):
        source_code = _source_id(row.idRegion)
        label = str(row.region)
        if source_code in CURRENT_REGION_MAP and spec["year"] >= 2015:
            canonical_id = CURRENT_REGION_MAP[source_code]
            method, confidence, status = "source_code+12_region_label", 1.0, "automatic"
        else:
            canonical_id = f"GEO_REGION_1997_{source_code}"
            method, confidence, status = "source_defined_historical_snapshot", 1.0, "source_defined"
            entities.setdefault(
                canonical_id,
                _entity("territory", canonical_id, label, "region", election_date, evidence_id, "1997_region_division"),
            )
        result[source_code] = canonical_id
        crosswalks.append(
            _crosswalk(
                "territory", source_id, f"region:{source_code}", canonical_id, label, election_date,
                evidence_id, method, confidence, status,
            )
        )
    return result


def _register_admin_units(
    frame: pd.DataFrame,
    source_id: str,
    spec: dict,
    election_date: str,
    evidence_id: str,
    province_lookup: dict[str, tuple[str, str]],
    crosswalks: list[dict],
    entities: dict[str, dict],
) -> dict[str, str]:
    result = {}
    columns = ["idPrefProv", "prefProv", "idSousPref", "sousPref"]
    for row in frame[columns].drop_duplicates().itertuples(index=False):
        if pd.isna(row.idSousPref) and pd.isna(row.idPrefProv):
            continue
        if pd.notna(row.idSousPref):
            source_code = f"subpref:{_source_id(row.idSousPref)}"
            label = str(row.sousPref)
            normalized = normalize_label(label)
            canonical_id = CASABLANCA_DISTRICTS.get(normalized)
            if not canonical_id:
                raise RuntimeError(f"Préfecture d'arrondissements inconnue: {label}")
            method, confidence, status = "source_label+casablanca_parent", 1.0, "source_defined"
            entities.setdefault(
                canonical_id,
                _entity(
                    "territory", canonical_id, label, "prefecture_district", election_date, evidence_id,
                    "casablanca_prefecture_district", parent_id="MA-06-141",
                ),
            )
        else:
            source_code = f"prefprov:{_source_id(row.idPrefProv)}"
            label = str(row.prefProv)
            match = province_lookup.get(normalize_label(label))
            if spec["year"] >= 2015 and match:
                canonical_id = match[0]
                method, confidence, status = "unique_normalized_name+entity_type", 0.95, "automatic"
            else:
                canonical_id = f"GEO_ADMIN_{spec['year']}_{_source_id(row.idPrefProv)}"
                method, confidence, status = "source_defined_historical_snapshot", 1.0, "boundary_bridge_required"
                entities.setdefault(
                    canonical_id,
                    _entity(
                        "territory", canonical_id, label, "province_prefecture_snapshot", election_date,
                        evidence_id, f"election_{spec['year']}_boundary",
                        current_geo_candidate_id=match[0] if match else None,
                    ),
                )
        result[source_code] = canonical_id
        crosswalks.append(
            _crosswalk(
                "territory", source_id, source_code, canonical_id, label, election_date,
                evidence_id, method, confidence, status,
            )
        )
    return result


def _register_parties(
    frame: pd.DataFrame,
    dictionary: pd.DataFrame,
    source_id: str,
    election_date: str,
    evidence_id: str,
    party_lookup: dict[str, str],
    crosswalks: list[dict],
    entities: dict[str, dict],
) -> None:
    party_codes = [str(column) for column in frame.columns if str(column) not in NON_PARTY_COLUMNS]
    dictionary_rows = {
        str(row.iloc[0]).strip(): str(row.iloc[1]).strip()
        for _, row in dictionary.iterrows()
        if pd.notna(row.iloc[0]) and pd.notna(row.iloc[1])
    }
    for code in party_codes:
        dictionary_code = DICTIONARY_ALIASES.get(code, code)
        source_label = dictionary_rows.get(dictionary_code, code)
        if code in PARTY_OVERRIDES:
            canonical_id, entity_type, label = PARTY_OVERRIDES[code]
            method, confidence, status = "source_dictionary_manual_seed", 0.9, "manual_review_required"
            entities.setdefault(
                canonical_id,
                _entity(entity_type, canonical_id, label, entity_type, election_date, evidence_id, "source_2007"),
            )
        else:
            canonical_id = party_lookup.get(code)
            if not canonical_id:
                raise RuntimeError(f"Code partisan sans résolution: {source_id}:{code}")
            method = "dictionary_alias+canonical_code" if dictionary_code != code else "canonical_code_exact"
            confidence = 0.95 if dictionary_code != code else 1.0
            status = "manual_review_required" if dictionary_code != code else "automatic"
        crosswalks.append(
            _crosswalk(
                "party_or_alliance", source_id, f"party:{code}", canonical_id, source_label,
                election_date, evidence_id, method, confidence, status,
            )
        )


def _register_contests(
    frame: pd.DataFrame,
    source_id: str,
    spec: dict,
    election_date: str,
    evidence_id: str,
    region_map: dict[str, str],
    admin_map: dict[str, str],
) -> list[dict]:
    contests = []
    for _, row in frame.iterrows():
        if "idCirconscription" in frame.columns:
            source_contest_id = _source_id(row["idCirconscription"])
            list_type = str(row["typeListe"]).strip()
            source_label = str(row["circonscription"])
        else:
            source_contest_id = _source_id(row["idSousPref"] if pd.notna(row["idSousPref"]) else row["idPrefProv"])
            list_type = "regional_council"
            source_label = str(row["sousPref"] if pd.notna(row["sousPref"]) else row["prefProv"])
        if pd.notna(row.get("idSousPref")):
            admin_key = f"subpref:{_source_id(row['idSousPref'])}"
            geo_id = admin_map[admin_key]
        elif pd.notna(row.get("idPrefProv")):
            admin_key = f"prefprov:{_source_id(row['idPrefProv'])}"
            geo_id = admin_map[admin_key]
        else:
            geo_id = region_map[_source_id(row["idRegion"])]
        contest_id = stable_contest_id(spec["election_id"], list_type, source_contest_id)
        contests.append(
            {
                "contest_id": contest_id,
                "election_id": spec["election_id"],
                "source_system": source_id,
                "source_contest_id": source_contest_id,
                "source_label": source_label,
                "normalized_label": normalize_label(source_label),
                "list_type": list_type,
                "geo_id": geo_id,
                "region_geo_id": region_map[_source_id(row["idRegion"])],
                "boundary_version": f"source_election_{spec['year']}",
                "valid_from": election_date,
                "valid_to": election_date,
                "evidence_id": evidence_id,
                "review_status": "boundary_bridge_required" if spec["year"] < 2015 else "automatic",
            }
        )
    return contests


def _crosswalk(
    entity_type: str,
    source_system: str,
    source_record_id: str,
    canonical_id: str,
    source_label: str,
    observation_date: str,
    evidence_id: str,
    method: str,
    confidence: float,
    review_status: str,
) -> dict:
    return {
        "entity_type": entity_type,
        "source_system": source_system,
        "source_record_id": source_record_id,
        "canonical_id": canonical_id,
        "source_label": source_label,
        "normalized_label": normalize_label(source_label),
        "valid_from": observation_date,
        "valid_to": observation_date,
        "match_method": method,
        "confidence": confidence,
        "evidence_id": evidence_id,
        "review_status": review_status,
    }


def _entity(
    entity_type: str,
    canonical_id: str,
    label: str,
    subtype: str,
    observed_on: str,
    evidence_id: str,
    boundary_version: str,
    parent_id: str | None = None,
    current_geo_candidate_id: str | None = None,
) -> dict:
    return {
        "entity_type": entity_type,
        "canonical_id": canonical_id,
        "canonical_label": label,
        "subtype": subtype,
        "parent_id": parent_id,
        "observed_on": observed_on,
        "boundary_version": boundary_version,
        "current_geo_candidate_id": current_geo_candidate_id,
        "evidence_id": evidence_id,
        "status": "provisional",
    }


def _source_id(value: object) -> str:
    if pd.isna(value):
        raise RuntimeError("Identifiant source vide")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _iso_date(value: object) -> str:
    return pd.Timestamp(value).date().isoformat()


def validate_registry(registry: dict) -> list[str]:
    errors = []
    if registry.get("schema_version") != 1 or registry.get("registry_version") != "1.0.0":
        errors.append("version du registre invalide")
    if registry.get("baseline_release") != "V12" or registry.get("integration_authorized") is not False:
        errors.append("baseline ou autorisation d'ingestion invalide")
    crosswalks = registry.get("crosswalks", [])
    contests = registry.get("contests", [])
    entities = registry.get("new_entities", [])
    crosswalk_key = [
        (item.get("entity_type"), item.get("source_system"), item.get("source_record_id"), item.get("valid_from"))
        for item in crosswalks
    ]
    if not crosswalks or len(crosswalk_key) != len(set(crosswalk_key)):
        errors.append("clés de crosswalk vides ou dupliquées")
    required_crosswalk = {
        "entity_type", "source_system", "source_record_id", "canonical_id", "source_label",
        "normalized_label", "valid_from", "valid_to", "match_method", "confidence", "evidence_id", "review_status",
    }
    for item in crosswalks:
        if required_crosswalk - item.keys() or not item.get("canonical_id") or not item.get("evidence_id"):
            errors.append(f"crosswalk incomplet: {item.get('source_system')}:{item.get('source_record_id')}")
        if not isinstance(item.get("confidence"), (int, float)) or not 0 <= item["confidence"] <= 1:
            errors.append(f"confiance invalide: {item.get('source_system')}:{item.get('source_record_id')}")
    contest_ids = [item.get("contest_id") for item in contests]
    if len(contests) != 639 or len(contest_ids) != len(set(contest_ids)):
        errors.append("639 contest_id uniques sont attendus")
    evidence_ids = {item.get("evidence_id") for item in crosswalks}
    for item in contests:
        if not item.get("geo_id") or not item.get("region_geo_id") or item.get("evidence_id") not in evidence_ids:
            errors.append(f"contest incomplet: {item.get('contest_id')}")
    entity_ids = [item.get("canonical_id") for item in entities]
    if len(entity_ids) != len(set(entity_ids)):
        errors.append("nouvelles entités dupliquées")
    counts = registry.get("counts", {})
    if counts.get("crosswalks") != len(crosswalks) or counts.get("contests") != len(contests) or counts.get("new_entities") != len(entities):
        errors.append("compteurs racine incohérents")
    expected_counts = {
        "crosswalks": 741,
        "contests": 639,
        "new_entities": 163,
        "crosswalks_by_entity_type": {"election": 6, "party_or_alliance": 176, "territory": 559},
        "review_statuses": {
            "automatic": 521,
            "boundary_bridge_required": 135,
            "manual_review_required": 5,
            "source_defined": 80,
        },
    }
    for key, expected in expected_counts.items():
        if counts.get(key) != expected:
            errors.append(f"compteur {key} inattendu: {counts.get(key)}")
    return errors


def render_report(registry: dict) -> str:
    counts = registry["counts"]
    lines = [
        "V13 — REGISTRE CANONIQUE DES IDENTITÉS ÉLECTORALES",
        "",
        f"Version : {registry['registry_version']}",
        f"Baseline : {registry['baseline_release']}",
        f"Date d'observation : {registry['as_of']}",
        "Ingestion autorisée : NON",
        "",
        "VOLUMES",
        "",
        f"Crosswalks : {counts['crosswalks']}",
        f"Courses électorales : {counts['contests']}",
        f"Nouvelles entités provisoires : {counts['new_entities']}",
        f"Par type : {json.dumps(counts['crosswalks_by_entity_type'], ensure_ascii=False, sort_keys=True)}",
        f"Par statut de revue : {json.dumps(counts['review_statuses'], ensure_ascii=False, sort_keys=True)}",
        f"Libellés portant déjà un caractère de remplacement : {counts['source_labels_with_replacement_character']}",
        "",
        "RÈGLES APPLIQUÉES",
        "",
        "- election_id relie exactement type, année et date officielle déjà présents dans V12.",
        "- contest_id est déterministe pour election_id × type de liste × identifiant source.",
        "- Les géographies postérieures au découpage 2015 utilisent un raccord exact et unique quand il existe.",
        "- Les unités 2007–2011 restent des snapshots historiques tant que leur frontière n'est pas validée.",
        "- Les huit préfectures d'arrondissements de Casablanca ne sont pas réduites à un arrondissement.",
        "- Les codes partisans source sont conservés; deux partis et deux alliances historiques restent provisoires.",
        "",
        "LIMITES",
        "",
    ]
    lines.extend(f"- {item}" for item in registry["limitations"])
    lines.extend(["", "PROCHAIN GATE", "", registry["next_gate"], ""])
    return "\n".join(lines)


def generate(
    data_dir: str | Path | None,
    as_of: str,
    baseline: str = "v12",
    output: str | Path | None = None,
    report_output: str | Path | None = None,
) -> int:
    registry = build_registry(data_dir, as_of, baseline)
    errors = validate_registry(registry)
    if errors:
        print("IDENTITY_REGISTRY_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    output_path = Path(output) if output else DEFAULT_OUTPUT
    report_path = Path(report_output) if report_output else DEFAULT_REPORT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(registry), encoding="utf-8")
    print(
        f"IDENTITY_REGISTRY_OK crosswalks={registry['counts']['crosswalks']} "
        f"contests={registry['counts']['contests']} output={output_path}"
    )
    return 0
