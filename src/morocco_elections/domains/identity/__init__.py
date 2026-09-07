"""Deterministic, Unicode-safe local identity helpers."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable

_FORMAT_CONTROLS = {"\u061c", "\u200b", "\u200c", "\u200d", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e", "\u2066", "\u2067", "\u2068", "\u2069", "\ufeff"}
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'", "ʼ": "'", "＇": "'"})
_DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-"})


def normalize_person_name(value: Any) -> str:
    """Return a display-safe canonical form without ASCII-folding Arabic."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.translate(_APOSTROPHES).translate(_DASHES).replace("ـ", "")
    text = "".join(ch for ch in text if ch not in _FORMAT_CONTROLS and unicodedata.category(ch) != "Cf")
    text = "".join(ch for ch in text if not (unicodedata.category(ch) == "Mn" and "ARABIC" in unicodedata.name(ch, "")))
    text = re.sub(r"[^\w\s'\-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def person_name_match_key(value: Any) -> str:
    """Return the accent-insensitive Unicode matching key used by V10."""
    decomposed = unicodedata.normalize("NFKD", normalize_person_name(value))
    text = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def canonical_person_tuple(source_id: str, commune_id: Any, constituency_id: Any, party_id: Any, name: Any) -> tuple[str, str, str, str, str]:
    key = person_name_match_key(name)
    if not key:
        raise ValueError("A local person identity cannot be generated from an empty normalized name")
    return (str(source_id), str(int(commune_id)), str(int(constituency_id)), str(party_id).strip().upper(), key)


def local_person_id(source_id: str, commune_id: Any, constituency_id: Any, party_id: Any, name: Any) -> str:
    natural = canonical_person_tuple(source_id, commune_id, constituency_id, party_id, name)
    payload = json.dumps(natural, ensure_ascii=False, separators=(",", ":"))
    return "PERS_LOCAL_V10_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def audit_local_identities(records: Iterable[dict[str, Any]], source_id: str) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str, str, str, str]]]:
    """Build conservative ambiguity groups and prove technical hash uniqueness."""
    id_to_tuple: dict[str, tuple[str, str, str, str, str]] = {}
    by_commune_name: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row_number, rec in enumerate(records, 2):
        natural = canonical_person_tuple(source_id, rec["idCommune"], rec["idCirconscription"], rec["parti"], rec["prenomNom"])
        pid = local_person_id(source_id, rec["idCommune"], rec["idCirconscription"], rec["parti"], rec["prenomNom"])
        previous = id_to_tuple.setdefault(pid, natural)
        if previous != natural:
            raise RuntimeError(f"SHA-256 identity collision: {pid}")
        enriched = dict(rec, _source_row=row_number, _person_id=pid, _match_key=natural[-1])
        by_commune_name[(int(rec["idCommune"]), natural[-1])].append(enriched)

    repeated = [(key, group) for key, group in sorted(by_commune_name.items()) if len(group) > 1]
    audit: list[dict[str, Any]] = []
    for sequence, ((commune, key), group) in enumerate(repeated, 1):
        identities = sorted({r["_person_id"] for r in group})
        audit.append({
            "audit_id": f"IDA_V10_{sequence:04d}", "audit_type": "same_name_within_commune",
            "source_idcommune": commune, "normalized_name_key": key,
            "source_rows": ",".join(str(r["_source_row"]) for r in group),
            "source_row_count": len(group), "distinct_raw_name_count": len({str(r["prenomNom"]) for r in group}),
            "constituency_ids": ",".join(map(str, sorted({int(r["idCirconscription"]) for r in group}))),
            "party_ids": ",".join(sorted({str(r["parti"]).upper() for r in group})),
            "assigned_person_count": len(identities), "person_ids": ",".join(identities),
            "resolution": "kept_separate_by_constituency_and_party" if len(identities) > 1 else "same_conservative_identity",
            "quality_status": "reviewed", "notes": "Name equality alone is not evidence of identity across constituencies or parties.",
        })
    return audit, id_to_tuple


__all__ = ["audit_local_identities", "canonical_person_tuple", "local_person_id", "normalize_person_name", "person_name_match_key"]
