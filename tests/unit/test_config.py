from pathlib import Path

from morocco_elections.config import PROJECT_ROOT, get_paths, resolve_manifest_path


def test_default_layout() -> None:
    paths = get_paths()
    assert paths.data_root == (PROJECT_ROOT / "data").resolve()
    assert paths.documentation_v9 == PROJECT_ROOT / "docs" / "v9" / "ontology"
    assert paths.v9_workbook == paths.data_root / "exports" / "excel" / "v9" / "Morocco_Electoral_Data_Warehouse_V9.xlsx"


def test_explicit_data_dir_has_priority(monkeypatch, tmp_path: Path) -> None:
    environment_root = tmp_path / "from-environment"
    explicit_root = tmp_path / "from-argument"
    monkeypatch.setenv("ELECTIONS_DATA_DIR", str(environment_root))
    assert get_paths(explicit_root).data_root == explicit_root.resolve()


def test_environment_data_dir(monkeypatch, tmp_path: Path) -> None:
    environment_root = tmp_path / "warehouse-data"
    monkeypatch.setenv("ELECTIONS_DATA_DIR", str(environment_root))
    assert get_paths().data_root == environment_root.resolve()
    resolved = resolve_manifest_path("data/raw/example.xlsx")
    assert resolved == environment_root / "raw" / "example.xlsx"

