from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    data_root: Path
    documentation_v9: Path
    documentation_v10: Path
    source_manifest: Path
    github_backlog: Path
    v8_workbook: Path
    v9_workbook: Path
    v10_workbook: Path
    comm2015: Path
    comm2021: Path
    council2021: Path
    parliamentary_members: Path
    hcp_population_2024: Path


def _resolved_data_root(data_dir: str | Path | None = None) -> Path:
    selected = data_dir or os.environ.get("ELECTIONS_DATA_DIR")
    path = Path(selected) if selected else PROJECT_ROOT / "data"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def get_paths(data_dir: str | Path | None = None) -> ProjectPaths:
    data_root = _resolved_data_root(data_dir)
    return ProjectPaths(
        project_root=PROJECT_ROOT,
        data_root=data_root,
        documentation_v9=PROJECT_ROOT / "docs" / "v9" / "ontology",
        documentation_v10=PROJECT_ROOT / "docs" / "v10" / "ontology",
        source_manifest=PROJECT_ROOT / "metadata" / "source_manifest.json",
        github_backlog=PROJECT_ROOT / "metadata" / "github_backlog.json",
        v8_workbook=data_root / "legacy" / "excel" / "v8" / "Morocco_Electoral_Data_Warehouse_V8.xlsx",
        v9_workbook=data_root / "exports" / "excel" / "v9" / "Morocco_Electoral_Data_Warehouse_V9.xlsx",
        v10_workbook=data_root / "exports" / "excel" / "v10" / "Morocco_Electoral_Data_Warehouse_V10.xlsx",
        comm2015=data_root / "raw" / "tafra" / "communal_results" / "2015" / "communes-elections-2015-1-0.xlsx",
        comm2021=data_root / "raw" / "tafra" / "communal_results" / "2021" / "communes-elections-2021-1-0.xlsx",
        council2021=data_root / "raw" / "tafra" / "local_councils" / "2021" / "communes-elus-2021-1-1.xlsx",
        parliamentary_members=data_root / "raw" / "tafra" / "parliament" / "members" / "parlement-elus-tafra-1-6-0.xlsx",
        hcp_population_2024=data_root / "raw" / "hcp" / "rgph" / "2024" / "hcp_population_legale_rgph2024.xlsx",
    )


def resolve_manifest_path(local_path: str, data_dir: str | Path | None = None) -> Path:
    """Resolve a repository-relative manifest path, honoring ELECTIONS_DATA_DIR."""
    relative = Path(local_path)
    paths = get_paths(data_dir)
    if relative.parts and relative.parts[0] == "data":
        return paths.data_root.joinpath(*relative.parts[1:])
    return paths.project_root / relative
