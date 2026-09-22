from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import openpyxl

from morocco_elections.config import PROJECT_ROOT, get_paths
from morocco_elections.quality import baseline as base


DEFAULT_METADATA = PROJECT_ROOT / "metadata" / "v11_quality_baseline.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "research" / "V11_QUALITY_BASELINE.txt"
V10_BASELINE = PROJECT_ROOT / "metadata" / "v10_quality_baseline.json"
V11_RELEASE_REPORT = PROJECT_ROOT / "metadata" / "v11_release_report.json"


def _universe(universe_id: str, label: str, period: str, source: str) -> dict[str, Any]:
    return {
        "universe_id": universe_id,
        "label": label,
        "grain": "commune/arrondissement × recensement",
        "period": period,
        "expected_count": 1_538,
        "denominator_defined": True,
        "evidence": [source, "metadata/v10qa3_hcp_indicators.json"],
        "status": "COMPLET",
        "note": "Univers national validé par V10-QA-3 et ingéré sans interpolation.",
    }


def _coverage(coverage_id: str, universe_id: str) -> dict[str, Any]:
    return {
        "coverage_id": coverage_id,
        "universe_id": universe_id,
        "tables": ["FACT_OBSERVATION"],
        "expected_count": 1_538,
        "observed_count": 1_538,
        "usable_count": 1_538,
        "reconciled_count": 1_538,
        "denominator_defined": True,
        "coverage_percent": 100.0,
        "status": "COMPLET",
        "gap": "",
    }


def build_baseline(workbook_path: Path, as_of: str) -> dict[str, Any]:
    data = copy.deepcopy(json.loads(V10_BASELINE.read_text(encoding="utf-8")))
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=False)
    try:
        row_counts = {sheet: base._count_rows(workbook, sheet) for sheet in workbook.sheetnames}
    finally:
        workbook.close()

    data.update(
        phase="V11-QA",
        baseline_release="V11",
        as_of=as_of,
        source_workbook="data/exports/excel/v11/Morocco_Electoral_Data_Warehouse_V11.xlsx",
        source_workbook_sha256=base._sha256(workbook_path),
    )
    data["universes"].extend(
        [
            _universe("U_HCP_POPULATION_LEGAL_2014", "Population légale communale RGPH 2014", "2014", "SRC_HCP_RGPH2014_INDIVIDUALS_V11"),
            _universe("U_HCP_POPULATION_MUNICIPAL_2024", "Population municipale communale RGPH 2024", "2024", "SRC_HCP_RGPH2024_INDICATORS_V11"),
        ]
    )
    data["coverage"].extend(
        [
            _coverage("COV_HCP_POPULATION_LEGAL_2014", "U_HCP_POPULATION_LEGAL_2014"),
            _coverage("COV_HCP_POPULATION_MUNICIPAL_2024", "U_HCP_POPULATION_MUNICIPAL_2024"),
        ]
    )
    for anomaly in data["anomalies"]:
        if anomaly["anomaly_id"] == "BASELINE_HCP_COMMUNAL_INDICATORS":
            anomaly.update(
                origin="V11-QA",
                severity="medium",
                status="PARTIEL",
                description="Deux apports nets HCP nationaux sont intégrés; 25 décisions indicateur-millésime restent NO_GO.",
                evidence=["metadata/v10qa3_hcp_indicators.json", "FACT_OBSERVATION", "metadata/v11_release_report.json"],
                required_action="Ne qualifier et ingérer les autres indicateurs qu'après une nouvelle preuve nationale complète.",
                restricts_analyses=["ANA_HCP_OTHER_INDICATORS"],
            )
    for table in data["table_status"]:
        if table["table"] == "WORKBOOK_AUDIT_V10":
            table["table"] = "WORKBOOK_AUDIT_V11"
            table["reason"] = "Inventaire physique des 67 onglets V11."
        table["physical_rows"] = row_counts[table["table"]]
        if table["table"] == "FACT_OBSERVATION":
            table.update(
                status="PARTIEL",
                reason="Deux univers HCP complets sont intégrés; les autres métriques gardent leurs limites propres.",
                next_gap="25 décisions HCP NO_GO restent exclues",
            )
    data["analysis_permissions"].extend(
        [
            {
                "analysis_id": "ANA_HCP_2014_FOR_ELECTION_2015",
                "label": "Population légale RGPH 2014 comme référence de l'élection 2015",
                "status": "CONDITIONNELLE",
                "tables": ["FACT_OBSERVATION"],
                "limits": "Afficher observation_year=2014 et temporal_distance=-1; ne pas appeler la valeur « population 2015 ».",
            },
            {
                "analysis_id": "ANA_HCP_2024_FOR_ELECTION_2015",
                "label": "Indicateurs RGPH 2024 comme description de l'élection 2015",
                "status": "INTERDITE",
                "tables": ["FACT_OBSERVATION", "POPULATION"],
                "limits": "Décalage de neuf ans; aucune interprétation contemporaine autorisée.",
            },
            {
                "analysis_id": "ANA_HCP_FOR_ELECTION_2021",
                "label": "Indicateurs RGPH 2014 ou 2024 comme références de l'élection 2021",
                "status": "CONDITIONNELLE",
                "tables": ["FACT_OBSERVATION", "POPULATION"],
                "limits": "Afficher le millésime réel et la distance −7 ou +3 ans; aucune valeur ne devient une observation 2021.",
            },
            {
                "analysis_id": "ANA_HCP_OTHER_INDICATORS",
                "label": "Autres indicateurs socio-économiques communaux HCP",
                "status": "INTERDITE",
                "tables": [],
                "limits": "Les 25 décisions NO_GO de V10-QA-3 ne sont pas intégrées et ne doivent pas être reconstruites.",
            },
        ]
    )
    data["source_hierarchy"][0]["examples"] = [
        "SRC_HCP_RGPH2014_INDIVIDUALS_V11",
        "SRC_HCP_RGPH2024_INDICATORS_V11",
    ]
    data["priorities"] = [
        "inscrits et dénominateurs électoraux",
        "présidences et contrôle communal",
        "résolution externe des conseils 2015 et de SMIIG",
        "questions parlementaires",
        "PostgreSQL",
    ]
    errors = base.validate_baseline(data)
    if errors:
        raise ValueError("Baseline V11-QA invalide: " + "; ".join(errors))
    return data


def render_report(data: dict[str, Any]) -> str:
    report = base.render_report(data)
    report = report.replace("V10-QA — BASELINE", "V11-QA — BASELINE", 1)
    report = report.replace("audit transversal sans ingestion ni modification de V10", "audit transversal de V11; V10 demeure immuable")
    report = report.replace(
        "Ce rapport est généré intégralement depuis metadata/v10_quality_baseline.json.",
        "Ce rapport est généré intégralement depuis metadata/v11_quality_baseline.json.",
    )
    return report


def generate(
    data_dir: str | Path | None = None,
    as_of: str | None = None,
    metadata_output: str | Path | None = None,
    report_output: str | Path | None = None,
) -> int:
    selected_date = as_of or date.today().isoformat()
    date.fromisoformat(selected_date)
    paths = get_paths(data_dir)
    if not paths.v11_workbook.is_file():
        print(f"QUALITY_BASELINE_FAILED fichier V11 absent: {paths.v11_workbook}")
        return 1
    release = json.loads(V11_RELEASE_REPORT.read_text(encoding="utf-8"))
    actual_hash = base._sha256(paths.v11_workbook)
    if actual_hash != release["workbooks"]["V11"]:
        print(f"QUALITY_BASELINE_FAILED SHA-256 V11 attendu {release['workbooks']['V11']}, obtenu {actual_hash}")
        return 1
    metadata_path = Path(metadata_output) if metadata_output else DEFAULT_METADATA
    report_path = Path(report_output) if report_output else DEFAULT_REPORT
    baseline = build_baseline(paths.v11_workbook, selected_date)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(baseline), encoding="utf-8")
    print(f"QUALITY_BASELINE_OK release=V11 tables={len(baseline['table_status'])} anomalies={len(baseline['anomalies'])}")
    return 0
