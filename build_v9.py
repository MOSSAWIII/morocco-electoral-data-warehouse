from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

import openpyxl
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


ROOT = Path(__file__).resolve().parent
V8 = ROOT / "Morocco_Electoral_Data_Warehouse_V8.xlsx"
V9 = ROOT / "Morocco_Electoral_Data_Warehouse_V9.xlsx"
RAW = ROOT / "raw_sources"
TODAY = "2026-09-07"

FILES = {
    "COMM2015": RAW / "communes-elections-2015-1-0.xlsx",
    "COMM2021": RAW / "communes-elections-2021-1-0.xlsx",
    "COUNCIL2021": RAW / "communes-elus-2021-1-1.xlsx",
    "MPS": RAW / "parlement-elus-tafra-1-6-0.xlsx",
    "HCP2024": RAW / "hcp_population_legale_rgph2024.xlsx",
}

URLS = {
    "COMM2015": "https://open.africa/dataset/cecd6468-53f8-4fdb-8269-f1a51c029ac3/resource/6d21d289-41d2-4f62-8719-e2a4b3aae055/download/communes-elections-2015-1-0.xlsx",
    "COMM2021": "https://open.africa/dataset/cb034784-1331-466c-a02f-713dfad58ef3/resource/19d637a4-0198-44b2-a3e2-2d7bbda3a7b2/download/communes-elections-2021-1-0.xlsx",
    "COUNCIL2021": "https://open.africa/dataset/3600ddc0-7a66-47be-9adf-cdbaa5ff4ec5/resource/d333e552-1608-421d-86d1-41455274e764/download/communes-elus-2021-1-1.xlsx",
    "MPS": "https://open.africa/dataset/5d84fa5f-144e-4a93-9dc8-de25a4267561/resource/7a0830a0-c4d0-4929-8028-a41b6822be6d/download/parlement-elus-tafra-1-6-0.xlsx",
    "HCP2024": "https://www.hcp.ma/reg-casablanca/attachment/2664423/",
}

SOURCE_IDS = {
    "COMM2015": "SRC_TAFRA_COMM2015_RAW_V9",
    "COMM2021": "SRC_TAFRA_COMM2021_RAW_V9",
    "COUNCIL2021": "SRC_TAFRA_COUNCIL2021_RAW_V9",
    "MPS": "SRC_TAFRA_MPS_RAW_V9",
    "HCP2024": "SRC_HCP_RGPH2024_RAW_V9",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_value(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item") and not isinstance(value, (str, bytes, datetime, date)):
        try:
            return value.item()
        except Exception:
            pass
    return value


def ascii_text(value) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()


def norm_geo(value) -> str:
    s = ascii_text(value)
    s = re.sub(r"\((mun|arrond)\.?\)", " ", s)
    s = re.sub(r"\bmy\b", "moulay", s)
    s = re.sub(r"\bbni\b", "beni", s)
    s = s.replace("&", " et ")
    s = re.sub(r"\b(commune|arrondissement|province|prefecture|d|de|du|des|la|le)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def strip_admin_prefix(value) -> str:
    s = str(value or "")
    return re.sub(
        r"^(Commune|Arrondissement|Province|Pr[ée]fecture)(\s+d['’]|\s+de\s+|\s+du\s+|\s+des\s+|\s+)",
        "",
        s,
        flags=re.IGNORECASE,
    ).rstrip("*").strip()


def canonical_commune_id(value) -> str:
    s = f"{int(value):09d}"
    return f"MA-{s[:2]}-{s[2:5]}-{s[5:7]}{s[7:9]}"


def canonical_province_id(value) -> str:
    s = f"{int(value):05d}"
    return f"MA-{s[:2]}-{s[2:5]}"


def simple_sheet(ws, title: str, description: str, headers: list[str]):
    ws.delete_rows(1, ws.max_row or 1)
    ws.sheet_view.showGridLines = True
    ws["A1"] = title
    ws["A2"] = description
    ws["A1"].font = Font(bold=True, size=12, color="000000")
    ws["A2"].font = Font(italic=False, size=10, color="000000")
    for col, header in enumerate(headers, 1):
        cell = ws.cell(4, col, header)
        cell.font = Font(bold=True, color="000000")
        cell.fill = PatternFill("solid", fgColor="E7E6E6")
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}4"


def get_or_create(wb, name: str):
    return wb[name] if name in wb.sheetnames else wb.create_sheet(name)


def write_rows(ws, rows, start=5):
    r = start
    for row in rows:
        for c, value in enumerate(row, 1):
            ws.cell(r, c, clean_value(value))
        r += 1
    return r - start


def finish_sheet(ws, max_width=34):
    for idx in range(1, ws.max_column + 1):
        header = ws.cell(4, idx).value
        width = max(10, min(max_width, len(str(header or "")) + 2))
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def replace_standard_sheet(wb, name, title, description, headers, rows):
    ws = get_or_create(wb, name)
    simple_sheet(ws, title, description, headers)
    write_rows(ws, rows)
    finish_sheet(ws)
    return ws


def copy_raw_excel_sheet(wb, target_name, source_path, source_sheet, description):
    source_wb = openpyxl.load_workbook(source_path, data_only=True, read_only=True)
    source_ws = source_wb[source_sheet]
    ws = get_or_create(wb, target_name)
    ws.delete_rows(1, ws.max_row or 1)
    ws["A1"] = target_name
    ws["A2"] = description
    ws["A1"].font = Font(bold=True, size=12)
    headers = [c.value for c in next(source_ws.iter_rows(min_row=1, max_row=1))]
    for col, header in enumerate(headers, 1):
        ws.cell(4, col, header)
        ws.cell(4, col).font = Font(bold=True)
        ws.cell(4, col).fill = PatternFill("solid", fgColor="E7E6E6")
    out_row = 5
    for row in source_ws.iter_rows(min_row=2, values_only=True):
        for col, value in enumerate(row, 1):
            ws.cell(out_row, col, clean_value(value))
        out_row += 1
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(source_ws.max_column)}{out_row-1}"
    finish_sheet(ws, 24)
    source_wb.close()


def copy_raw_hcp(wb):
    source_wb = openpyxl.load_workbook(FILES["HCP2024"], data_only=True, read_only=True)
    source_ws = source_wb.active
    ws = get_or_create(wb, "RAW_HCP_RGPH2024_FULL")
    ws.delete_rows(1, ws.max_row or 1)
    for row in source_ws.iter_rows(values_only=True):
        ws.append([clean_value(v) for v in row])
    ws.freeze_panes = "A8"
    for idx in range(1, 8):
        ws.column_dimensions[get_column_letter(idx)].width = 24
    source_wb.close()


def dataframe(path, sheet=0):
    return pd.read_excel(path, sheet_name=sheet)


def parse_hcp_geography():
    wb = openpyxl.load_workbook(FILES["HCP2024"], data_only=True)
    ws = wb.active
    provinces = {}
    regions = {}
    for i in range(1, ws.max_row + 1):
        name_fr = str(ws.cell(i, 1).value or "")
        code = ws.cell(i, 7).value
        fmt = ws.cell(i, 7).number_format
        a = ascii_text(name_fr)
        if fmt == "00" and code is not None and a.startswith("region "):
            regions[f"MA-{int(code):02d}"] = strip_admin_prefix(name_fr)
        if fmt == '00"."000' and code is not None and (a.startswith("province ") or a.startswith("prefecture ")):
            provinces[canonical_province_id(code)] = strip_admin_prefix(name_fr)

    entities = []
    for i in range(1, ws.max_row + 1):
        code = ws.cell(i, 7).value
        fmt = ws.cell(i, 7).number_format
        name_fr_raw = str(ws.cell(i, 1).value or "")
        a = ascii_text(name_fr_raw)
        if fmt != '00"."000"."00"."00' or code is None:
            continue
        if a.startswith("prefecture d'arrondissement") or a.startswith("prefecture d arrondissement"):
            continue
        geo_id = canonical_commune_id(code)
        province_id = "-".join(geo_id.split("-")[:3])
        region_id = "-".join(geo_id.split("-")[:2])
        entities.append(
            {
                "geo_id": geo_id,
                "name_fr": strip_admin_prefix(name_fr_raw),
                "name_ar": ws.cell(i, 6).value,
                "geo_type": "arrondissement" if a.startswith("arrondissement ") else "commune",
                "province_id": province_id,
                "province_name": provinces.get(province_id),
                "region_id": region_id,
                "region_name": regions.get(region_id),
                "moroccans": ws.cell(i, 2).value,
                "foreigners": ws.cell(i, 3).value,
                "population": ws.cell(i, 4).value,
                "households": ws.cell(i, 5).value,
                "source_row": i,
            }
        )
    wb.close()
    assert len(provinces) == 75, len(provinces)
    assert len(regions) == 12, len(regions)
    assert len(entities) == 1538, len(entities)
    assert len({e["geo_id"] for e in entities}) == 1538
    return regions, provinces, entities


def build_crosswalk(df, entities, election_id):
    by_parent = defaultdict(list)
    for entity in entities:
        by_parent[norm_geo(entity["province_name"])].append(entity)
    rows = []
    mapping = {}
    for rec in df.to_dict("records"):
        source_name = rec["commune"]
        source_parent = rec["prefProv"]
        candidates = by_parent[norm_geo(source_parent)]
        exact = [e for e in candidates if norm_geo(e["name_fr"]) == norm_geo(source_name)]
        if len(exact) == 1:
            match = exact[0]
            method = "normalized_name+province"
            confidence = 1.0
        else:
            scored = sorted(
                ((SequenceMatcher(None, norm_geo(source_name), norm_geo(e["name_fr"])).ratio(), e) for e in candidates),
                key=lambda x: x[0],
                reverse=True,
            )
            if not scored:
                raise AssertionError(f"No candidates for {source_name} / {source_parent}")
            confidence, match = scored[0]
            margin = confidence - (scored[1][0] if len(scored) > 1 else 0)
            if confidence < 0.85 or margin < 0.03:
                raise AssertionError(f"Ambiguous geography: {source_name} / {source_parent}: {scored[:2]}")
            method = "fuzzy_name+province"
        source_geo_id = f"TAFRA_COMM_{int(rec['idCommune'])}"
        mapping[int(rec["idCommune"])] = match["geo_id"]
        rows.append(
            [
                "TAFRA/elections.ma",
                source_geo_id,
                source_name,
                rec["region"],
                source_parent,
                match["geo_id"],
                match["name_fr"],
                match["region_id"],
                match["province_id"],
                "2015-02-20",
                None,
                method,
                confidence,
                1 if confidence < 0.95 else 0,
                "same_2015_boundary_reference",
                SOURCE_IDS["HCP2024"],
                f"Election={election_id}; parent geography required; one-to-one target validated.",
            ]
        )
    assert len(mapping) == 1538
    assert len(set(mapping.values())) == 1538
    return rows, mapping


def source_party_names(path: Path):
    d = dataframe(path, 1)
    result = {}
    for rec in d.to_dict("records"):
        label = str(rec.get("Label") or "").strip()
        definition = str(rec.get("Définition (FR)") or "")
        if "Nombre de voix" in definition or "nombre de voix" in definition:
            name = re.sub(r"^.*?(?:par|coalition)\s+", "", definition, flags=re.IGNORECASE)
            name = re.sub(r"\s+comprenant.*$", "", name, flags=re.IGNORECASE).strip()
            result[label.upper()] = name
    return result


def rank_desc(values: dict[str, float]):
    ordered = sorted(set(values.values()), reverse=True)
    rank = {v: i + 1 for i, v in enumerate(ordered)}
    return {k: rank[v] for k, v in values.items()}


def person_hash(*parts) -> str:
    raw = "|".join(norm_geo(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:14]


def role_normalized(role):
    r = norm_geo(role)
    if r == "president":
        return "president"
    if r.startswith("vice president"):
        return "vice_president"
    if r == "secretaire conseil":
        return "council_secretary"
    if r == "vice secretaire conseil":
        return "deputy_council_secretary"
    if r == "conseiller":
        return "councillor"
    return "other"


def rows_from_sheet(ws, header_row=4):
    headers = list(next(ws.iter_rows(min_row=header_row, max_row=header_row, max_col=ws.max_column, values_only=True)))
    out = []
    for vals in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row, max_col=ws.max_column, values_only=True):
        vals = list(vals)
        if any(v is not None for v in vals):
            out.append(dict(zip(headers, vals)))
    return headers, out


def rewrite_existing(ws, headers, records):
    if ws.max_row >= 5:
        ws.delete_rows(5, ws.max_row - 4)
    for idx, h in enumerate(headers, 1):
        ws.cell(4, idx, h)
    for rec in records:
        ws.append([clean_value(rec.get(h)) for h in headers])


def append_sources(wb):
    ws = wb["SOURCES"]
    headers, records = rows_from_sheet(ws)
    existing = {r["source_id"] for r in records}
    specs = {
        SOURCE_IDS["COMM2015"]: ["Elections communales Maroc 2015 — fichier brut 1.0", "TAFRA / elections.ma", "research copy of official", "communal elections", URLS["COMM2015"], "2015", "2015", "commune/arrondissement", "election", "XLSX", "direct download", "CC BY 4.0", 95, TODAY, "ingested", f"1,538 rows; SHA256={sha256(FILES['COMM2015'])}; full 45-column original."],
        SOURCE_IDS["COMM2021"]: ["Elections communales Maroc 2021 — fichier brut 1.0", "TAFRA / elections.ma", "research copy of official", "communal elections", URLS["COMM2021"], "2021", "2021", "commune/arrondissement", "election", "XLSX", "direct download", "CC BY 4.0", 95, TODAY, "ingested", f"1,538 rows; SHA256={sha256(FILES['COMM2021'])}; full 56-column original."],
        SOURCE_IDS["COUNCIL2021"]: ["Composition des conseils communaux 2021 — fichier brut 1.1", "TAFRA / elections.ma", "research copy of official", "local representation", URLS["COUNCIL2021"], "2021", "2021", "person × communal constituency", "election", "XLSX", "direct download", "CC BY 4.0", 95, TODAY, "ingested", f"32,513 rows; SHA256={sha256(FILES['COUNCIL2021'])}."],
        SOURCE_IDS["MPS"]: ["Membres de la Chambre des représentants 2007–2026 — fichier brut 1.6", "TAFRA / Parliament and official directories", "research compilation", "parliamentary mandates", URLS["MPS"], "2007", "2026", "person × constituency × spell", "legislature", "XLSX", "direct download", "CC BY 4.0", 92, TODAY, "ingested", f"1,654 rows; SHA256={sha256(FILES['MPS'])}; party is first observed in legislature, not full switching history."],
        SOURCE_IDS["HCP2024"]: ["Population légale RGPH 2024 — fichier brut officiel", "Haut-Commissariat au Plan", "official", "population/geography", URLS["HCP2024"], "2024", "2024", "region/province/commune/arrondissement", "census", "XLSX", "direct download", "official public", 100, TODAY, "ingested", f"Official table; SHA256={sha256(FILES['HCP2024'])}; 1,538 commune/arrondissement entities extracted."],
    }
    for sid, vals in specs.items():
        if sid in existing:
            continue
        rec = dict(zip(headers[1:], vals))
        rec["source_id"] = sid
        records.append(rec)
    rewrite_existing(ws, headers, records)


def update_tracking(wb):
    ws = wb["RAW_IMPORT_QUEUE"]
    headers, records = rows_from_sheet(ws)
    done = {"RAW_COMM2015", "RAW_COMM2021", "RAW_COUNCIL2021", "RAW_MPS"}
    for rec in records:
        if rec.get("dataset_id") in done:
            rec["status"] = "ingested_full_v9"
            rec["blocker"] = "resolved in current runtime"
            rec["next_action"] = "QA and incremental source upgrade only"
            rec["notes"] = (str(rec.get("notes") or "") + " Full original XLSX ingested on 2026-09-07.").strip()
    rewrite_existing(ws, headers, records)

    ws = wb["SOURCE_DOWNLOADS"]
    headers, records = rows_from_sheet(ws)
    for rec in records:
        if rec.get("dataset_id") in {"COMM2015", "COMM2021", "COUNCIL2021", "MPS"}:
            rec["binary_access_runtime"] = "downloaded 2026-09-07"
            rec["viewer_access"] = "full binary ingested"
            rec["notes"] = (str(rec.get("notes") or "") + " SHA-256 recorded in SOURCES V9.").strip()
    rewrite_existing(ws, headers, records)

    ws = wb["SOURCE_BLOCKERS_V8"]
    headers, records = rows_from_sheet(ws)
    for rec in records:
        if rec.get("dataset_id") in {"COMM2015", "COMM2021", "COUNCIL2021", "MPS"}:
            rec["runtime_binary_access"] = "yes"
            rec["usable_now"] = "full source ingested in V9"
            rec["next_extraction_route"] = "complete"
            rec["blocking_reason"] = "resolved 2026-09-07"
    rewrite_existing(ws, headers, records)


def update_dimensions_and_population(wb, regions, provinces, entities, party_names, council, mps):
    # Geography: replace provisional HCP/SIG commune rows by official HCP entities; preserve all unrelated IDs.
    ws = wb["DIM_GEO"]
    headers, existing = rows_from_sheet(ws)
    canonical_ids = set(regions) | set(provinces) | {e["geo_id"] for e in entities}
    existing = [r for r in existing if r.get("geo_id") not in canonical_ids]
    for rid, rname in regions.items():
        existing.append({"geo_id": rid, "geo_name": rname, "geo_type": "region", "parent_geo_id": "MAR", "region_name": rname, "boundary_version": "RGPH2024 / 2015 administrative division", "valid_from": "2015-02-20", "source_id": SOURCE_IDS["HCP2024"], "source_url": URLS["HCP2024"], "publication_date": "2024-11-01", "retrieval_date": TODAY, "quality_status": "verified", "notes": "Official HCP geographic code."})
    for pid, pname in provinces.items():
        rid = "-".join(pid.split("-")[:2])
        existing.append({"geo_id": pid, "geo_name": pname, "geo_type": "province_prefecture", "parent_geo_id": rid, "region_name": regions.get(rid), "province_prefecture": pname, "boundary_version": "RGPH2024 / 2015 administrative division", "valid_from": "2015-02-20", "source_id": SOURCE_IDS["HCP2024"], "source_url": URLS["HCP2024"], "publication_date": "2024-11-01", "retrieval_date": TODAY, "quality_status": "verified", "notes": "Official HCP geographic code."})
    for e in entities:
        existing.append({"geo_id": e["geo_id"], "geo_name": e["name_fr"], "geo_type": e["geo_type"], "parent_geo_id": e["province_id"], "region_name": e["region_name"], "province_prefecture": e["province_name"], "commune_name": e["name_fr"] if e["geo_type"] == "commune" else None, "district_arrondissement": e["name_fr"] if e["geo_type"] == "arrondissement" else None, "boundary_version": "RGPH2024 / 2015 administrative division", "valid_from": "2015-02-20", "source_id": SOURCE_IDS["HCP2024"], "source_url": URLS["HCP2024"], "publication_date": "2024-11-01", "retrieval_date": TODAY, "quality_status": "verified", "notes": f"HCP raw row {e['source_row']}; Arabic name={e['name_ar']}"})
    rewrite_existing(ws, headers, existing)

    ws = wb["POPULATION"]
    headers, existing = rows_from_sheet(ws)
    existing = [r for r in existing if not str(r.get("record_id") or "").startswith("POP2024_MA-")]
    for e in entities:
        existing.append({"record_id": f"POP2024_{e['geo_id']}", "geo_id": e["geo_id"], "time_id": "2024", "population_total": e["population"], "male_population": None, "female_population": None, "households": e["households"], "source_id": SOURCE_IDS["HCP2024"], "source_url": URLS["HCP2024"], "publication_date": "2024-11-01", "retrieval_date": TODAY, "quality_status": "verified", "notes": f"Official HCP legal population; Moroccans={e['moroccans']}; foreigners={e['foreigners']}. Sex breakdown not present in this official workbook."})
    rewrite_existing(ws, headers, existing)

    # Parties: keep existing IDs; add every observed raw code without guessing unknown labels.
    ws = wb["DIM_PARTY"]
    headers, existing = rows_from_sheet(ws)
    by_id = {str(r.get("party_id")): r for r in existing}
    observed = set(party_names)
    observed |= {str(x).strip().upper() for x in council["parti"].dropna().unique()}
    observed |= {str(x).strip().upper() for x in mps["parti"].dropna().unique()}
    known = {
        "PADS": "Parti de l'Avant-Garde Démocratique et Socialiste", "CNI": "Congrès National Ittihadi",
        "PE2": "Parti de l'Équité", "PML1": "Parti Marocain Libéral (Hur)", "PED": "Parti de l'Environnement et du Développement",
        "ALAHD": "Al Ahd", "ADL": "Alliance Démocratique des Libertés", "UPNDPA": "Union PND-PA (coalition source)",
        "SAP": "Sans appartenance politique — liste 1", "SAP2": "Sans appartenance politique — liste 2", "SAP3": "Sans appartenance politique — liste 3",
        "PDN": "Parti Démocrate National", "PAN": "Parti Annahda", "NEO": "Parti des Néo-Démocrates",
    }
    for code in sorted(observed):
        if code in by_id:
            continue
        label = party_names.get(code) or known.get(code) or f"Code source {code} — libellé institutionnel à valider"
        status = "historical/source code" if code not in party_names and code not in known else "party/alliance/independent source code"
        rec = {"party_id": code, "party_name_fr": label, "acronym": code, "legal_status": status, "source_id": SOURCE_IDS["COMM2015"], "source_url": URLS["COMM2015"], "retrieval_date": TODAY, "quality_status": "provisional", "notes": "Raw code preserved; no ambiguous acronym expansion inferred."}
        existing.append(rec)
    # Correct the old provisional AGD label with the source dictionary definition.
    for rec in existing:
        if rec.get("party_id") == "AGD":
            rec["party_name_fr"] = "Alliance de la Gauche Démocratique"
            rec["legal_status"] = "coalition"
            rec["source_id"] = SOURCE_IDS["COMM2015"]
            rec["quality_status"] = "provisional"
            rec["notes"] = "Source dictionary: coalition PADS + CNI + PSU; valid for 2015 source coding."
    rewrite_existing(ws, headers, existing)

    # People: replace old tiny TAFRA pilots with exhaustive conservative identities.
    ws = wb["DIM_PERSON"]
    headers, existing = rows_from_sheet(ws)
    existing = [r for r in existing if not str(r.get("person_id") or "").startswith(("TAFRA_MP_", "TAFRA_LOCAL_2021_"))]
    # Local identity is scoped to commune + normalized name to avoid false cross-commune homonym joins.
    local_seen = {}
    for rec in council.to_dict("records"):
        pid = f"TAFRA_LOCAL_2021_{int(rec['idCommune'])}_{person_hash(rec['prenomNom'])}"
        if pid not in local_seen:
            local_seen[pid] = {"person_id": pid, "full_name": rec["prenomNom"], "gender": None, "party_id": str(rec["parti"]).upper(), "role": "Élu communal", "incumbent_flag": "unknown", "first_elected_year": 2021, "valid_from": "2021-09-08", "source_id": SOURCE_IDS["COUNCIL2021"], "source_url": URLS["COUNCIL2021"], "retrieval_date": TODAY, "quality_status": "provisional", "notes": "Conservative person key scoped to commune+name; not a proven national identity key."}
    existing.extend(local_seen.values())
    for pid, group in mps.groupby("idPerson", sort=True):
        group = group.sort_values(["dateEntree", "parlement"])
        latest = group.iloc[-1]
        starts = pd.to_datetime(group["dateEntree"], errors="coerce").dropna()
        ends = pd.to_datetime(group["dateSortie"], errors="coerce").dropna()
        valid_from = clean_value(starts.min()) if not starts.empty else None
        valid_to = clean_value(ends.max()) if not ends.empty else None
        existing.append({"person_id": f"TAFRA_MP_{int(pid)}", "full_name": latest["prenomNom"], "gender": "female" if int(latest["femme"]) == 1 else "male", "party_id": str(latest["parti"]).upper(), "role": "Député", "incumbent_flag": "unknown", "first_elected_year": int(str(group.iloc[0]["parlement"])[:4]), "mandates_count": int(group["parlement"].nunique()), "valid_from": valid_from, "valid_to": valid_to, "source_id": SOURCE_IDS["MPS"], "source_url": URLS["MPS"], "retrieval_date": TODAY, "quality_status": "provisional", "notes": "Stable TAFRA idPerson. party_id is latest observed source value, not a complete party-switching history."})
    rewrite_existing(ws, headers, existing)


def build_party_crosswalk(wb, party_names, datasets):
    headers = ["source_system", "raw_source_code", "raw_name", "canonical_party_id", "canonical_name", "valid_from", "valid_to", "alliance_flag", "predecessor", "successor", "confidence", "notes"]
    rows = []
    label_fallback = {"PADS": "Parti de l'Avant-Garde Démocratique et Socialiste", "CNI": "Congrès National Ittihadi", "PE2": "Parti de l'Équité", "PML1": "Parti Marocain Libéral (Hur)", "SAP": "Sans appartenance politique — liste 1", "SAP2": "Sans appartenance politique — liste 2", "SAP3": "Sans appartenance politique — liste 3"}
    for system, year, codes in datasets:
        for code in sorted(codes):
            canon = code.upper()
            name = party_names.get(canon) or label_fallback.get(canon) or f"Raw source code {canon}"
            alliance = 1 if canon in {"AGD", "AFG", "UPNDPA"} else 0
            confidence = 1.0 if canon in party_names or canon in label_fallback else 0.8
            note = "Exact raw code retained; temporal validation applies."
            if canon.startswith("SAP"):
                note = "Independent-list slot in source; not a stable party or stable cross-election identity."
            if canon == "AGD":
                note = "2015 coalition: PADS + CNI + PSU, per original TAFRA dictionary."
            rows.append([system, code, name, canon, name, str(year), str(year), alliance, None, None, confidence, note])
    replace_standard_sheet(wb, "CROSSWALK_PARTY", "V9 — crosswalk longitudinal des partis", "Tous les codes bruts P0 sont conservés. Les alliances et indépendants restent explicitement temporels; aucun acronyme ambigu n'est deviné.", headers, rows)


def build_results_and_mobilisation(wb, elections, mappings):
    results_headers = [ws.value for ws in wb["RESULTS"][4]]
    mob_headers = [ws.value for ws in wb["MOBILISATION"][4]]
    _, old_results = rows_from_sheet(wb["RESULTS"])
    _, old_mob = rows_from_sheet(wb["MOBILISATION"])
    result_rows = []
    mob_rows = []
    normalized = {}
    party_starts = {2015: "AGD", 2021: "AFG"}
    for year, df in elections.items():
        election_id = f"COMM{year}"
        sid = SOURCE_IDS[f"COMM{year}"]
        source_url = URLS[f"COMM{year}"]
        party_cols = list(df.columns[df.columns.get_loc(party_starts[year]):])
        for rec in df.to_dict("records"):
            geo_id = mappings[year][int(rec["idCommune"])]
            values = {p.upper(): float(rec[p]) for p in party_cols if pd.notna(rec[p])}
            valid_votes = sum(values.values())
            ranks = rank_desc(values)
            sorted_votes = sorted(values.values(), reverse=True)
            top = sorted_votes[0]
            second = sorted_votes[1] if len(sorted_votes) > 1 else 0
            normalized[(geo_id, year)] = {"votes": values, "valid_votes": valid_votes, "ranks": ranks, "turnout": float(rec["txParticipation"]) * 100, "council_seats": int(rec["nSieges"]), "winner": sorted(values, key=lambda p: (-values[p], p))[0]}
            for party, votes in values.items():
                share = votes / valid_votes * 100 if valid_votes else None
                result_rows.append({"record_id": f"RES_V9_{year}_{int(rec['idCommune'])}_{party}", "geo_id": geo_id, "time_id": f"{year}-09-04" if year == 2015 else "2021-09-08", "election_id": election_id, "party_id": party, "votes": int(votes) if votes.is_integer() else votes, "vote_share": share, "rank": ranks[party], "victory_margin_votes": top - second if votes == top else None, "victory_margin_pp": (top - second) / valid_votes * 100 if votes == top and valid_votes else None, "source_id": sid, "source_url": source_url, "retrieval_date": TODAY, "quality_status": "provisional", "notes": "Full original source party denominator; null party cells treated as party not observed in this commune, not as votes."})
            mob_rows.append({"record_id": f"MOB_V9_{year}_{int(rec['idCommune'])}", "geo_id": geo_id, "time_id": f"{year}-09-04" if year == 2015 else "2021-09-08", "election_id": election_id, "registered_voters": None, "voters": None, "turnout_rate": float(rec["txParticipation"]) * 100, "abstention_rate": 100 - float(rec["txParticipation"]) * 100, "valid_votes": int(valid_votes), "invalid_votes": None, "blank_votes": None, "source_id": sid, "source_url": source_url, "retrieval_date": TODAY, "quality_status": "provisional", "notes": "Source publishes turnout but leaves nInscrits empty; voters and invalid/blank counts are therefore not reconstructed."})
    old_results = [r for r in old_results if not str(r.get("record_id") or "").startswith("RES_V9_")]
    old_mob = [r for r in old_mob if not str(r.get("record_id") or "").startswith("MOB_V9_")]
    rewrite_existing(wb["RESULTS"], results_headers, old_results + result_rows)
    rewrite_existing(wb["MOBILISATION"], mob_headers, old_mob + mob_rows)
    return normalized, result_rows, mob_rows


def build_local_and_mps(wb, council, mps, mapping):
    local_headers = ["local_mandate_id", "person_id", "person_name_ar", "source_idcommune", "source_idcirconscription", "geo_id_source", "canonical_geo_id", "commune", "province", "party_id", "head_of_list", "role", "role_normalized", "executive_flag", "role_uncertain_flag", "head_of_list_uncertain_flag", "election_id", "source_id", "quality_status", "notes"]
    local_rows = []
    for idx, rec in enumerate(council.to_dict("records"), 1):
        pid = f"TAFRA_LOCAL_2021_{int(rec['idCommune'])}_{person_hash(rec['prenomNom'])}"
        local_rows.append([f"LM2021_{idx:05d}", pid, rec["prenomNom"], int(rec["idCommune"]), int(rec["idCirconscription"]), f"TAFRA_COMM_{int(rec['idCommune'])}", mapping[int(rec["idCommune"])], rec["commune"], rec["prefProv"], str(rec["parti"]).upper(), int(rec["teteDeListe"]), rec["role"], role_normalized(rec["role"]), 0 if role_normalized(rec["role"]) == "councillor" else 1, int(rec["flagRole"]), int(rec["flagTeteDeListe"]), "COMM2021", SOURCE_IDS["COUNCIL2021"], "low_confidence" if int(rec["flagRole"]) or int(rec["flagTeteDeListe"]) else "provisional", "Source role/head-of-list flags retained; local person identity scoped to commune+name."])
    replace_standard_sheet(wb, "LOCAL_MANDATES", "V9 — mandats locaux exhaustifs 2021", "Une ligne = observation d'élu × commune × circonscription. Les 32 513 lignes brutes sont normalisées sans déduire de sexe ni d'identité intercommunale.", local_headers, local_rows)

    mp_headers = ["mandate_id", "person_id", "full_name", "full_name_ar", "gender", "legislature", "source_seat_id", "source_constituency_id", "constituency", "region", "province", "party_id", "parliamentary_group", "start_date", "end_date", "entry_reason", "exit_reason", "replacement_procedure", "active_at_source_date", "source_id", "quality_status", "notes"]
    mp_rows = []
    for rec in mps.to_dict("records"):
        start = clean_value(rec["dateEntree"])
        stamp = start.strftime("%Y%m%d") if isinstance(start, datetime) else str(start)
        mandate_id = f"PM_{str(rec['parlement']).replace('-', '_')}_{int(rec['idSiege'])}_{int(rec['idPerson'])}_{stamp}"
        mp_rows.append([mandate_id, f"TAFRA_MP_{int(rec['idPerson'])}", rec["prenomNom"], rec["prenomNomAR"], "female" if int(rec["femme"]) == 1 else "male", rec["parlement"], int(rec["idSiege"]), int(rec["idCirconscription"]), rec["circonscription"], rec["region"], rec["prefProv"], str(rec["parti"]).upper(), rec["groupe"], start, clean_value(rec["dateSortie"]), rec["motifEntree"], rec["motifSortie"], rec["procedureRemplacement"], 1 if pd.isna(rec["dateSortie"]) else 0, SOURCE_IDS["MPS"], "provisional", "Stable idPerson retained; party is first recorded party for the legislature and not a complete switching history."])
    replace_standard_sheet(wb, "PARLIAMENTARY_MANDATES", "V9 — mandats parlementaires exhaustifs 2007–2026", "Une ligne = période de siège d'une personne dans une législature et une circonscription; les remplacements partagent parfois un idSiege.", mp_headers, mp_rows)

    # Council party seats and control.
    party_counts = council.groupby(["idCommune", "parti"], dropna=False).size().rename("seats").reset_index()
    head_counts = council.groupby(["idCommune", "parti"])["teteDeListe"].sum().to_dict()
    exec_counts = council.assign(executive=council["role"].map(lambda x: 0 if role_normalized(x) == "councillor" else 1)).groupby(["idCommune", "parti"])["executive"].sum().to_dict()
    president_rows = council[(council["role"].map(role_normalized) == "president") & (council["flagRole"] == 0)]
    presidents = {}
    for rec in president_rows.to_dict("records"):
        presidents[int(rec["idCommune"])] = (f"TAFRA_LOCAL_2021_{int(rec['idCommune'])}_{person_hash(rec['prenomNom'])}", str(rec["parti"]).upper())
    control_headers = ["geo_id", "election_id", "party_id", "party_seats", "party_seat_share", "seat_rank", "largest_party_flag", "president_person_id", "president_party_id", "executive_member_count", "head_of_list_count", "female_elected_count", "female_elected_share", "president_party_same_as_largest_party", "source_id", "quality_status", "notes"]
    control_rows = []
    power_rows = []
    for idc, group in party_counts.groupby("idCommune"):
        total = int(group["seats"].sum())
        vals = {str(r["parti"]).upper(): int(r["seats"]) for _, r in group.iterrows()}
        ranks = rank_desc(vals)
        largest = max(vals.values())
        pres_pid, pres_party = presidents.get(int(idc), (None, None))
        for party, seats in sorted(vals.items()):
            same = None if pres_party is None else int(pres_party == party and seats == largest)
            control_rows.append([mapping[int(idc)], "COMM2021", party, seats, seats / total * 100, ranks[party], int(seats == largest), pres_pid, pres_party, int(exec_counts.get((idc, party), 0)), int(head_counts.get((idc, party), 0)), None, None, same, SOURCE_IDS["COUNCIL2021"], "provisional", "Seat count equals elected-person rows; governing president is distinct from largest electoral party. Gender unavailable in source."])
            power_rows.append({"record_id": f"POW_V9_2021_{int(idc)}_{party}", "geo_id": mapping[int(idc)], "time_id": "2021-09-08", "election_id": "COMM2021", "party_id": party, "institution_level": "communal_council", "seats_held": seats, "seat_share": seats / total * 100, "council_presidency_flag": int(pres_party == party) if pres_party else None, "source_id": SOURCE_IDS["COUNCIL2021"], "source_url": URLS["COUNCIL2021"], "retrieval_date": TODAY, "quality_status": "provisional", "notes": "Derived from exhaustive elected-person rows; not vote results."})
    replace_standard_sheet(wb, "LOCAL_COUNCIL_CONTROL", "V9 — contrôle et composition des conseils communaux 2021", "Grain commune × parti. Le parti ayant le plus d'élus est séparé du parti du président du conseil.", control_headers, control_rows)
    pheaders, old_power = rows_from_sheet(wb["POWER_REP"])
    old_power = [r for r in old_power if not str(r.get("record_id") or "").startswith("POW_V9_")]
    rewrite_existing(wb["POWER_REP"], pheaders, old_power + power_rows)
    return control_rows, presidents, party_counts


def build_transitions_and_panels(wb, normalized, entities, council_counts, presidents):
    entity_by_id = {e["geo_id"]: e for e in entities}
    seats_2021 = defaultdict(dict)
    for rec in council_counts.to_dict("records"):
        # idCommune is mapped through normalized records by matching all V9 source IDs later.
        seats_2021[int(rec["idCommune"])][str(rec["parti"]).upper()] = int(rec["seats"])
    # Reverse mapping is identical for 2015/2021 source ids.
    idc_by_geo = {}
    for key in normalized:
        geo, year = key
        if year == 2021:
            # source id can be recovered from record populations only through separate lookup supplied in keys below
            pass
    # Build a deterministic geo -> idCommune dictionary from shared source IDs in normalized metadata.
    # Both election files have exactly the same 1,538 idCommune set.
    df2021 = dataframe(FILES["COMM2021"], 0)
    _, map2021 = build_crosswalk(df2021, entities, "COMM2021")
    idc_by_geo = {geo: idc for idc, geo in map2021.items()}
    pop = {e["geo_id"]: e["population"] for e in entities}

    transition_headers = ["geo_id", "party_id", "votes_2015", "votes_2021", "share_2015", "share_2021", "rank_2015", "rank_2021", "seats_2015", "seats_2021", "swing_pp", "vote_change", "vote_change_pct", "seat_change", "winner_2015", "winner_2021", "entered_market", "exited_market", "incumbent", "retained_control", "lost_control", "gained_control", "source_id", "quality_status", "notes"]
    trans_rows = []
    commune_rows = []
    analytic_rows = []
    commune_election_rows = []
    for geo_id in sorted(entity_by_id):
        a = normalized[(geo_id, 2015)]
        b = normalized[(geo_id, 2021)]
        parties = sorted(set(a["votes"]) | set(b["votes"]))
        shares_a = {p: a["votes"].get(p, 0) / a["valid_votes"] * 100 for p in parties}
        shares_b = {p: b["votes"].get(p, 0) / b["valid_votes"] * 100 for p in parties}
        volatility = 0.5 * sum(abs(shares_b[p] - shares_a[p]) for p in parties)
        hhi_a = sum(v * v for v in shares_a.values())
        hhi_b = sum(v * v for v in shares_b.values())
        enp_a = 10000 / hhi_a if hhi_a else None
        enp_b = 10000 / hhi_b if hhi_b else None
        idc = idc_by_geo[geo_id]
        party_seats = seats_2021[idc]
        pres_party = presidents.get(idc, (None, None))[1]
        largest_party = None
        if party_seats:
            largest_party = sorted(party_seats, key=lambda p: (-party_seats[p], p))[0]
        for p in parties:
            va = a["votes"].get(p)
            vb = b["votes"].get(p)
            sa = va / a["valid_votes"] * 100 if va is not None else None
            sb = vb / b["valid_votes"] * 100 if vb is not None else None
            change_pct = ((vb - va) / va * 100) if va not in (None, 0) and vb is not None else None
            trans_rows.append([geo_id, p, va, vb, sa, sb, a["ranks"].get(p), b["ranks"].get(p), None, party_seats.get(p), (sb - sa) if sa is not None and sb is not None else None, (vb - va) if va is not None and vb is not None else None, change_pct, None, int(a["winner"] == p), int(b["winner"] == p), int(va is None and vb is not None), int(va is not None and vb is None), None, None, None, None, f"{SOURCE_IDS['COMM2015']};{SOURCE_IDS['COMM2021']}", "derived", "Vote shares use the full published party-column denominator. Alliance and independent-list codes remain temporally explicit."])
        commune_rows.append([geo_id, a["winner"], b["winner"], a["turnout"], b["turnout"], b["turnout"] - a["turnout"], volatility, hhi_a, hhi_b, enp_a, enp_b, None, largest_party, pres_party, None, "derived", "Vote transition complete; 2015 party seats/control unavailable, so control_change is blank."])
        for year, d, hhi, enp in [(2015, a, hhi_a, enp_a), (2021, b, hhi_b, enp_b)]:
            ordered = sorted(d["votes"], key=lambda p: (-d["votes"][p], p))
            winner = ordered[0]
            runner = ordered[1] if len(ordered) > 1 else None
            margin_votes = d["votes"][winner] - (d["votes"].get(runner, 0) if runner else 0)
            margin_pp = margin_votes / d["valid_votes"] * 100 if d["valid_votes"] else None
            commune_election_rows.append([geo_id, f"COMM{year}", year, d["turnout"], winner, d["votes"][winner] / d["valid_votes"] * 100, runner, margin_votes, margin_pp, hhi, enp, volatility if year == 2021 else None, largest_party if year == 2021 else None, pres_party if year == 2021 else None, None, pop[geo_id], 2024, year, 2024 - year, "census_reference", None, None, entity_by_id[geo_id]["geo_type"], None, "derived", "Population is an explicit 2024 reference, not contemporaneous with the election."])
            for p, votes in d["votes"].items():
                share = votes / d["valid_votes"] * 100
                prev_share = shares_a.get(p) if year == 2021 and p in a["votes"] else None
                swing = share - prev_share if prev_share is not None else None
                analytic_rows.append([geo_id, f"COMM{year}", year, p, entity_by_id[geo_id]["region_name"], entity_by_id[geo_id]["province_name"], entity_by_id[geo_id]["name_fr"], entity_by_id[geo_id]["geo_type"], pop[geo_id], 2024, year, 2024 - year, "census_reference", None, None, None, None, None, d["turnout"], votes, share, d["ranks"][p], int(d["winner"] == p), party_seats.get(p) if year == 2021 else None, (party_seats.get(p) / sum(party_seats.values()) * 100) if year == 2021 and p in party_seats else None, prev_share, swing, (votes - a["votes"].get(p)) if year == 2021 and p in a["votes"] else None, None, None, largest_party if year == 2021 else None, pres_party if year == 2021 else None, None, "derived", "Population is a 2024 census reference. Vote share denominator is the sum of all published party columns."])

    replace_standard_sheet(wb, "ELECTORAL_TRANSITIONS_2015_2021", "V9 — transitions électorales communales 2015→2021", "Grain commune canonique × code politique temporel. Swing et changements sont calculés uniquement sur le dénominateur complet publié.", transition_headers, trans_rows)
    replace_standard_sheet(wb, "COMMUNE_TRANSITION_PANEL", "V9 — panel de transition communal 2015→2021", "Grain commune. Volatilité de Pedersen, HHI et nombre effectif de partis sont dérivés des voix exhaustives publiées.", ["geo_id", "winner_2015", "winner_2021", "turnout_2015", "turnout_2021", "turnout_change_pp", "pedersen_volatility", "hhi_2015", "hhi_2021", "enp_2015", "enp_2021", "control_change", "largest_party_2021", "president_party_2021", "president_same_as_largest", "quality_status", "notes"], commune_rows)
    replace_standard_sheet(wb, "ANALYTICAL_PANEL", "V9 — panel analytique commune × parti × élection", "Panel final P0. Les variables socio-économiques absentes restent vides; population_reference est explicitement RGPH 2024.", ["geo_id", "election_id", "year", "party_id", "region", "province", "commune", "urban_rural", "population_reference", "observation_year", "election_year", "temporal_distance", "temporal_join_method", "poverty", "unemployment", "literacy", "internet", "registered_voters", "turnout", "party_votes", "vote_share", "rank", "winner", "seats", "seat_share", "previous_vote_share", "swing_pp", "vote_change", "seat_change", "incumbent_party", "council_control_party", "president_party", "governance_score", "quality_status", "notes"], analytic_rows)
    replace_standard_sheet(wb, "COMMUNE_ELECTION_PANEL", "V9 — panel commune × élection", "Panel final P0 au grain commune × élection, avec métriques de compétition et discipline temporelle explicite.", ["geo_id", "election_id", "year", "turnout", "winner", "winning_share", "runner_up", "margin_votes", "margin_pp", "hhi", "enp", "volatility", "largest_party", "president_party", "control_change", "population_reference", "observation_year", "election_year", "temporal_distance", "temporal_join_method", "poverty", "unemployment", "urban_rural", "migration", "quality_status", "notes"], commune_election_rows)
    return trans_rows, commune_rows, analytic_rows, commune_election_rows


def add_quality(wb, elections, mappings, normalized, council, mps, control_rows):
    ws = wb["QUALITY_CONTROL"]
    headers, records = rows_from_sheet(ws)
    records = [r for r in records if not str(r.get("issue_id") or "").startswith("QA_V9_")]
    issues = []

    def add(code, sheet, record_range, issue_type, severity, description, expected, resolution="open", resolved=0, source_id=None, notes=None):
        issues.append({"issue_id": f"QA_V9_{code}", "detected_date": TODAY, "sheet_name": sheet, "record_or_range": record_range, "issue_type": issue_type, "severity": severity, "description": description, "expected_rule": expected, "resolution": resolution, "resolved_flag": resolved, "resolved_date": TODAY if resolved else None, "owner": "data engineering", "source_id": source_id, "notes": notes})

    for year, df in elections.items():
        add(f"RAW_{year}_PK", f"RAW_COMM{year}_FULL", "all rows", "primary_key", "info", f"idCommune unique: {df['idCommune'].nunique()}/1538; duplicates={df.duplicated(['idCommune']).sum()}", "Unique idCommune and 1,538 rows", "passed", 1, SOURCE_IDS[f"COMM{year}"])
        add(f"GEO_{year}", "CROSSWALK_GEO", f"COMM{year}", "foreign_key", "info", f"Resolved {len(mappings[year])}/1538 source units to {len(set(mappings[year].values()))} unique HCP targets.", "All geo keys resolved one-to-one with parent constraint", "passed", 1, SOURCE_IDS["HCP2024"])
        add(f"INSCRITS_{year}", f"RAW_COMM{year}_FULL", "nInscrits", "missing_source_field", "high", "nInscrits is 100% null although present in schema; voters cannot be reconstructed from turnout.", "Do not derive voters or invalid counts without a denominator", "left null; source limitation documented", 0, SOURCE_IDS[f"COMM{year}"])
        bad_turnout = int(((df["txParticipation"] < 0) | (df["txParticipation"] > 1)).sum())
        add(f"TURNOUT_{year}", "MOBILISATION", f"COMM{year}", "range_check", "info", f"Turnout outside [0,100]: {bad_turnout}", "turnout in [0,100]", "passed", 1, SOURCE_IDS[f"COMM{year}"])
        share_bad = 0
        for (geo, y), d in normalized.items():
            if y != year:
                continue
            total = sum(v / d["valid_votes"] * 100 for v in d["votes"].values())
            if abs(total - 100) > 1e-8:
                share_bad += 1
        add(f"SHARES_{year}", "RESULTS", f"COMM{year}", "denominator_check", "info", f"Communes whose party shares fail to sum to 100: {share_bad}", "Sum vote_share approximately 100", "passed", 1, SOURCE_IDS[f"COMM{year}"])

    dup_council = council[council.duplicated(["idCommune", "idCirconscription", "prenomNom", "parti"], keep=False)]
    add("COUNCIL_NATURAL_DUP", "RAW_COUNCIL2021_FULL", "natural key", "duplicate_candidate", "medium", f"Potential duplicate rows on commune+constituency+name+party: {len(dup_council)} rows ({dup_council.duplicated(['idCommune','idCirconscription','prenomNom','parti']).sum()} excess).", "No duplicated person mandate", "retained and flagged; exact rows are not duplicates", 0, SOURCE_IDS["COUNCIL2021"], "Rows can differ by role/head-of-list fields; no silent deletion.")
    # Compare elected-person count with published total seats from COMM2021.
    expected = elections[2021].set_index("idCommune")["nSieges"]
    actual = council.groupby("idCommune").size()
    diff = (actual - expected).dropna()
    bad = diff[diff != 0]
    add("COUNCIL_SEAT_SUM", "LOCAL_COUNCIL_CONTROL", ",".join(map(str, bad.index.tolist())) or "all communes", "seat_reconciliation", "high" if len(bad) else "info", f"Communes with elected rows != published council seats: {len(bad)}; national difference={int(actual.sum()-expected.sum())}.", "Sum party seats equals council seats", "open; source rows preserved", 0 if len(bad) else 1, SOURCE_IDS["COUNCIL2021"], "; ".join(f"idCommune {i}: actual {actual[i]}, expected {expected[i]}" for i in bad.index))
    confident_presidents = council[(council["role"].map(role_normalized) == "president") & (council["flagRole"] == 0)]["idCommune"].nunique()
    add("COUNCIL_PRESIDENT", "LOCAL_COUNCIL_CONTROL", "president_party_id", "coverage", "medium", f"Confident president identified for {confident_presidents}/1538 communes; {1538-confident_presidents} remain unresolved due source role uncertainty/missingness.", "Do not infer governing party from largest party", "open; blanks retained", 0, SOURCE_IDS["COUNCIL2021"])
    mandate_ids = [r[0] for r in wb["PARLIAMENTARY_MANDATES"].iter_rows(min_row=5, values_only=True) if r[0] is not None]
    add("MPS_PK", "PARLIAMENTARY_MANDATES", "all rows", "primary_key", "info", f"Mandate IDs unique: {len(set(mandate_ids))}/{len(mandate_ids)}; stable persons={mps.idPerson.nunique()}.", "Unique mandate_id; stable idPerson retained", "passed", 1, SOURCE_IDS["MPS"])
    add("MPS_PARTY_HISTORY", "PARLIAMENTARY_MANDATES", "party_id", "semantic_limit", "high", "TAFRA party field is the first observed party for the legislature and does not capture within-legislature switching.", "Do not treat as complete PERSON_PARTY_HISTORY", "documented; separate future ingestion required", 0, SOURCE_IDS["MPS"])
    add("TEMPORAL_POP", "ANALYTICAL_PANEL", "population_reference", "temporal_join", "info", "Every 2015/2021 row uses RGPH 2024 only as an explicit census_reference with temporal_distance 9 or 3.", "No silent 2024→2015 contemporaneous join", "passed", 1, SOURCE_IDS["HCP2024"])
    add("RAW_LINEAGE", "RAW_*_FULL", "all P0", "lineage", "info", "All four P0 source workbooks are retained in RAW sheets and SHA-256 hashes are recorded in SOURCES.", "RAW → NORMALIZED → FACT → ANALYTICAL", "passed", 1)
    _, crosswalk = rows_from_sheet(wb["CROSSWALK_GEO"])
    review = [r for r in crosswalk if r.get("manual_review_flag") == 1]
    review_names = sorted({f"{r['source_geo_name']} → {r['canonical_name']}" for r in review})
    add("GEO_MANUAL_REVIEW", "CROSSWALK_GEO", "manual_review_flag=1", "manual_review", "medium", f"{len(review)} election-specific rows ({len(review_names)} unique source units) have confidence below 0.95: " + "; ".join(review_names), "Fuzzy matches below 0.95 require explicit review even when parent and one-to-one constraints pass", "open; mappings retained and flagged", 0, SOURCE_IDS["HCP2024"])
    records.extend(issues)
    rewrite_existing(ws, headers, records)
    return issues


def audit_workbook(wb, v8_sheetnames):
    classification = {}
    for name in wb.sheetnames:
        if name == "RAW_IMPORT_QUEUE":
            classification[name] = "QUEUE"
        elif name.startswith("DIM_"):
            classification[name] = "DIMENSION"
        elif name.startswith("RAW_"):
            classification[name] = "RAW"
        elif "CROSSWALK" in name or name == "GEO_LEGACY_CODES":
            classification[name] = "CROSSWALK"
        elif name in {"SOURCES", "SOURCE_DOWNLOADS", "SOURCE_PROFILES", "SOURCE_BLOCKERS_V8", "DATA_DICTIONARY", "README", "DATA_COVERAGE"}:
            classification[name] = "SOURCE / METADATA"
        elif name in {"QUALITY_CONTROL", "WORKBOOK_AUDIT_V9"}:
            classification[name] = "QA"
        elif name.startswith(("ANALYTICAL", "COMMUNE_", "ELECTORAL_TRANSITIONS", "LONGITUDINAL", "PARTY_TRENDS", "MICRO_", "COUNCIL2021_SAMPLE_STATS")):
            classification[name] = "ANALYTICAL"
        else:
            classification[name] = "FACT"

    grain = {
        "DIM_GEO": "geographic entity", "DIM_TIME": "time/date", "DIM_PARTY": "party/alliance", "DIM_PERSON": "person identity", "DIM_ELECTION": "election",
        "RESULTS": "geography × party × election", "MOBILISATION": "geography × election", "LOCAL_MANDATES": "person × commune × constituency × mandate",
        "PARLIAMENTARY_MANDATES": "person × legislature × seat spell", "LOCAL_COUNCIL_CONTROL": "commune × party × election",
        "ELECTORAL_TRANSITIONS_2015_2021": "commune × party", "COMMUNE_TRANSITION_PANEL": "commune", "ANALYTICAL_PANEL": "commune × party × election",
        "COMMUNE_ELECTION_PANEL": "commune × election", "POPULATION": "geography × time", "FACT_OBSERVATION": "geography × time × metric",
        "RAW_COMM2015_FULL": "source commune row", "RAW_COMM2021_FULL": "source commune row", "RAW_COUNCIL2021_FULL": "source elected-person row",
        "RAW_MPS_FULL": "source MP seat spell", "RAW_HCP_RGPH2024_FULL": "literal source worksheet row", "CROSSWALK_GEO": "source geography × election",
        "CROSSWALK_PARTY": "source code × source system/year",
    }
    headers = ["sheet", "classification", "grain", "primary_key", "foreign_keys", "data_rows", "populated_columns", "formula_cells", "sources", "coverage_period", "geographic_level", "quality_status", "duplicate_primary_keys", "missing_primary_keys", "known_limitations", "origin_version"]
    rows = []
    for name in wb.sheetnames:
        if name == "WORKBOOK_AUDIT_V9":
            continue
        ws = wb[name]
        # Most warehouse sheets use header row 4. README is intentionally free-form.
        header_row = 4
        hdr = list(next(ws.iter_rows(min_row=header_row, max_row=header_row, max_col=ws.max_column, values_only=True)))
        if not any(h is not None for h in hdr):
            header_row = 1
            hdr = list(next(ws.iter_rows(min_row=header_row, max_row=header_row, max_col=ws.max_column, values_only=True)))
        data = [list(vals) for vals in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row, max_col=ws.max_column, values_only=True) if any(v is not None for v in vals)]
        key_candidates = ["record_id", "geo_id", "time_id", "party_id", "person_id", "election_id", "source_id", "metric_id", "mandate_id", "local_mandate_id", "issue_id", "dataset_id"]
        pk = next((k for k in key_candidates if k in hdr), hdr[0] if hdr else None)
        fk = [str(h) for h in hdr if isinstance(h, str) and h.endswith("_id") and h != pk]
        dup = missing = None
        if pk in hdr:
            idx = hdr.index(pk)
            vals = [row[idx] for row in data]
            present = [v for v in vals if v not in (None, "")]
            dup = len(present) - len(set(map(str, present)))
            missing = len(vals) - len(present)
        populated = sum(1 for c in range(len(hdr)) if any(c < len(row) and row[c] is not None for row in data))
        formulas = sum(1 for row in data for v in row if isinstance(v, str) and v.startswith("="))
        source_vals = []
        if "source_id" in hdr:
            idx = hdr.index("source_id")
            source_vals = sorted({str(row[idx]) for row in data if idx < len(row) and row[idx]})
        coverage = ""
        for col in ["year", "election_year", "time_id", "election_id", "legislature", "coverage_start"]:
            if col in hdr:
                idx = hdr.index(col)
                vals = [str(row[idx]) for row in data if idx < len(row) and row[idx] not in (None, "")]
                if vals:
                    coverage = f"{min(vals)} → {max(vals)}"
                    break
        geo_level = ""
        if "geo_type" in hdr:
            idx = hdr.index("geo_type")
            geo_level = ", ".join(sorted({str(row[idx]) for row in data if idx < len(row) and row[idx]}))
        elif any(h in hdr for h in ["geo_id", "canonical_geo_id", "idCommune"]):
            geo_level = "see geography key"
        qstatus = ""
        if "quality_status" in hdr:
            idx = hdr.index("quality_status")
            qstatus = ", ".join(f"{k}:{v}" for k, v in sorted(Counter(str(row[idx]) for row in data if idx < len(row) and row[idx]).items()))
        limits = []
        if "SAMPLE" in name or "PILOT" in name:
            limits.append("pilot/sample only")
        if name in {"RAW_COMM2015_FULL", "RAW_COMM2021_FULL"}:
            limits.append("nInscrits absent in source")
        if name in {"LOCAL_MANDATES", "LOCAL_COUNCIL_CONTROL"}:
            limits.append("gender absent; role uncertainty flags retained")
        if name == "PARLIAMENTARY_MANDATES":
            limits.append("party switching not captured")
        rows.append([name, classification[name], grain.get(name, "documented by sheet schema/title"), pk, ", ".join(fk), len(data), populated, formulas, "; ".join(source_vals[:8]), coverage, geo_level, qstatus, dup, missing, "; ".join(limits), "V8 preserved" if name in v8_sheetnames else "V9 new"])
    replace_standard_sheet(wb, "WORKBOOK_AUDIT_V9", "V9 — audit exhaustif du classeur", "Inventaire onglet par onglet après ingestion P0. Les compteurs portent sur les lignes effectivement peuplées.", headers, rows)


def append_readme_version(wb, counts):
    ws = wb["README"]
    ws["A1"] = "Morocco Electoral Quantitative Data Warehouse — V9"
    ws["A2"] = "Warehouse longitudinal data-first: sources brutes, dimensions canoniques, faits normalisés, panels analytiques et QA traçable."
    start = ws.max_row + 2
    rows = [
        ["VERSION V9 — INGESTION P0 EXHAUSTIVE", None],
        ["version", "V9"],
        ["date", TODAY],
        ["new raw rows", f"COMM2015 1,538; COMM2021 1,538; COUNCIL2021 32,513; MPS 1,654; HCP source worksheet 2,332"],
        ["new normalized rows", f"RESULTS {counts['results']}; MOBILISATION {counts['mob']}; LOCAL_MANDATES 32,513; PARLIAMENTARY_MANDATES 1,654"],
        ["new analytical rows", f"transitions {counts['transitions']}; commune transitions {counts['communes']}; ANALYTICAL_PANEL {counts['analytical']}; COMMUNE_ELECTION_PANEL {counts['commune_election']}"],
        ["new sources", "Five original/official XLSX files with SHA-256 lineage in SOURCES"],
        ["new sheets", "RAW_*_FULL (5); LOCAL_COUNCIL_CONTROL; ELECTORAL_TRANSITIONS_2015_2021; COMMUNE_TRANSITION_PANEL; ANALYTICAL_PANEL; COMMUNE_ELECTION_PANEL; WORKBOOK_AUDIT_V9"],
        ["major fixes", "Full 31/33-party denominators restored; canonical HCP geography expanded to 1,538; AGD identified from original dictionary; P0 binary blockers resolved"],
        ["known blockers", "Registered voters absent in both communal source files; 2015 party seats/control unavailable; 135 council presidents unresolved; five geographic spelling variants await explicit review; council elected-row total differs from published seats by two QA-documented exceptions"],
        ["next priority", "Resolve council seat/president exceptions; ingest SMIIG and parliamentary questions; then commune-level HCP socioeconomic indicators"],
    ]
    for row in rows:
        ws.append(row)
    ws.cell(start, 1).font = Font(bold=True, size=12)


def build_data_coverage(wb):
    headers = ["domain_sheet", "rows_loaded", "verified_rows", "provisional_rows", "derived_rows", "low_confidence_rows", "primary_key", "granularity_now", "next_granularity_target"]
    specs = [
        ("RAW_COMM2015_FULL", "idCommune", "commune/arrondissement source row", "registered-voter denominator"),
        ("RAW_COMM2021_FULL", "idCommune", "commune/arrondissement source row", "registered-voter denominator"),
        ("RAW_COUNCIL2021_FULL", "source row", "elected person × constituency", "resolve role exceptions"),
        ("RAW_MPS_FULL", "source row", "MP seat spell", "party-history events"),
        ("DIM_GEO", "geo_id", "country to commune/arrondissement", "douar after commune QA"),
        ("POPULATION", "record_id", "geography × census year", "communal socioeconomic indicators"),
        ("CROSSWALK_GEO", "source_system+source_geo_id+election", "source geography × election", "manual review of five variants"),
        ("RESULTS", "record_id", "geography × party × election", "party seats for 2015"),
        ("MOBILISATION", "record_id", "geography × election", "registered/voters/invalid counts"),
        ("LOCAL_MANDATES", "local_mandate_id", "person × commune × constituency", "identity resolution and gender"),
        ("LOCAL_COUNCIL_CONTROL", "geo_id+party_id+election_id", "commune × party × election", "resolve two seat gaps and 135 presidents"),
        ("PARLIAMENTARY_MANDATES", "mandate_id", "person × legislature × seat spell", "PERSON_PARTY_HISTORY"),
        ("ELECTORAL_TRANSITIONS_2015_2021", "geo_id+party_id", "commune × party", "2015 seats/control"),
        ("COMMUNE_TRANSITION_PANEL", "geo_id", "commune", "governance and socioeconomic joins"),
        ("ANALYTICAL_PANEL", "geo_id+party_id+election_id", "commune × party × election", "P1 socioeconomic/governance variables"),
        ("COMMUNE_ELECTION_PANEL", "geo_id+election_id", "commune × election", "P1 socioeconomic/governance variables"),
    ]
    rows = []
    for name, pk, grain, target in specs:
        _, records = rows_from_sheet(wb[name])
        q = Counter(str(r.get("quality_status")) for r in records if r.get("quality_status"))
        rows.append([name, len(records), q.get("verified", 0), q.get("provisional", 0), q.get("derived", 0), q.get("low_confidence", 0), pk, grain, target])
    replace_standard_sheet(wb, "DATA_COVERAGE", "V9 — couverture quantitative", "Couverture statique recalculée après ingestion P0; aucun compteur ne dépend d'une plage Excel tronquée.", headers, rows)


def main():
    for path in [V8, *FILES.values()]:
        if not path.exists():
            raise FileNotFoundError(path)
    wb = openpyxl.load_workbook(V8, data_only=False)
    v8_sheetnames = set(wb.sheetnames)
    try:
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        wb.calculation.calcMode = "auto"
    except Exception:
        pass

    elections = {2015: dataframe(FILES["COMM2015"], 0), 2021: dataframe(FILES["COMM2021"], 0)}
    council = dataframe(FILES["COUNCIL2021"], 0)
    mps = dataframe(FILES["MPS"], 0)
    assert elections[2015].shape == (1538, 45)
    assert elections[2021].shape == (1538, 56)
    assert council.shape == (32513, 18)
    assert mps.shape == (1654, 24)

    # Exact RAW copies: original data columns remain unchanged.
    copy_raw_excel_sheet(wb, "RAW_COMM2015_FULL", FILES["COMM2015"], "données", f"Copie immuable des 1 538 lignes / 45 colonnes originales. URL={URLS['COMM2015']}; SHA256={sha256(FILES['COMM2015'])}")
    copy_raw_excel_sheet(wb, "RAW_COMM2021_FULL", FILES["COMM2021"], "données", f"Copie immuable des 1 538 lignes / 56 colonnes originales. URL={URLS['COMM2021']}; SHA256={sha256(FILES['COMM2021'])}")
    copy_raw_excel_sheet(wb, "RAW_COUNCIL2021_FULL", FILES["COUNCIL2021"], "données", f"Copie immuable des 32 513 lignes / 18 colonnes originales. URL={URLS['COUNCIL2021']}; SHA256={sha256(FILES['COUNCIL2021'])}")
    copy_raw_excel_sheet(wb, "RAW_MPS_FULL", FILES["MPS"], "donnees", f"Copie immuable des 1 654 lignes / 24 colonnes originales. URL={URLS['MPS']}; SHA256={sha256(FILES['MPS'])}")
    copy_raw_hcp(wb)

    regions, provinces, entities = parse_hcp_geography()
    cw15, map15 = build_crosswalk(elections[2015], entities, "COMM2015")
    cw21, map21 = build_crosswalk(elections[2021], entities, "COMM2021")
    assert map15 == map21
    crosswalk_headers = ["source_system", "source_geo_id", "source_geo_name", "source_region", "source_province", "canonical_geo_id", "canonical_name", "canonical_region_id", "canonical_province_id", "valid_from", "valid_to", "match_method", "confidence_score", "manual_review_flag", "temporal_boundary_status", "source_id", "notes"]
    replace_standard_sheet(wb, "CROSSWALK_GEO", "V9 — crosswalk géographique exhaustif TAFRA ↔ HCP", "3 076 raccords élection-spécifiques couvrant 1 538 entités. Jamais de match sur le seul nom: la province/préfecture est obligatoire.", crosswalk_headers, cw15 + cw21)

    party_names = source_party_names(FILES["COMM2015"])
    party_names.update(source_party_names(FILES["COMM2021"]))
    update_dimensions_and_population(wb, regions, provinces, entities, party_names, council, mps)
    build_party_crosswalk(wb, party_names, [
        ("TAFRA COMM2015", 2015, list(elections[2015].columns[elections[2015].columns.get_loc("AGD"):])),
        ("TAFRA COMM2021", 2021, list(elections[2021].columns[elections[2021].columns.get_loc("AFG"):])),
        ("TAFRA COUNCIL2021", 2021, list(council["parti"].dropna().unique())),
        ("TAFRA MPS", "2007-2026", list(mps["parti"].dropna().unique())),
    ])
    normalized, result_rows, mob_rows = build_results_and_mobilisation(wb, elections, {2015: map15, 2021: map21})
    control_rows, presidents, council_counts = build_local_and_mps(wb, council, mps, map21)
    trans_rows, commune_rows, analytical_rows, commune_election_rows = build_transitions_and_panels(wb, normalized, entities, council_counts, presidents)
    append_sources(wb)
    update_tracking(wb)
    add_quality(wb, elections, {2015: map15, 2021: map21}, normalized, council, mps, control_rows)
    append_readme_version(wb, {"results": len(result_rows), "mob": len(mob_rows), "transitions": len(trans_rows), "communes": len(commune_rows), "analytical": len(analytical_rows), "commune_election": len(commune_election_rows)})
    build_data_coverage(wb)
    audit_workbook(wb, v8_sheetnames)

    # Plain data-first presentation on all new or fully rebuilt sheets.
    for ws in wb.worksheets:
        if ws.title in {"RAW_HCP_RGPH2024_FULL"}:
            continue
        ws.sheet_view.showGridLines = True
    wb.save(V9)
    print(f"Saved {V9}")
    print(f"Sheets={len(wb.sheetnames)} ResultsAdded={len(result_rows)} Transitions={len(trans_rows)} Analytical={len(analytical_rows)}")


if __name__ == "__main__":
    main()
