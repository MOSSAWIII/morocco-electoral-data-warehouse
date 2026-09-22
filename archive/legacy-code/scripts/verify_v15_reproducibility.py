from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from morocco_elections.provenance import sha256_file


FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def verify(first: Path, second: Path, first_zip: Path, second_zip: Path) -> None:
    manifests = [json.loads((root / "manifest.json").read_text(encoding="utf-8")) for root in (first, second)]
    if manifests[0]["logical_digests"] != manifests[1]["logical_digests"]:
        raise RuntimeError("Les empreintes logiques diffèrent entre les deux builds")
    for record in manifests[0]["files"]:
        if record["reproducibility"] != "BINARY":
            continue
        relative = record["path"]
        if sha256_file(first / relative) != sha256_file(second / relative):
            raise RuntimeError(f"Fichier déclaré reproductible différent: {relative}")
    for archive in (first_zip, second_zip):
        with zipfile.ZipFile(archive) as bundle:
            infos = bundle.infolist()
            names = [info.filename for info in infos]
            if names != sorted(names) or len(names) != len(set(names)):
                raise RuntimeError(f"Ordre ZIP non déterministe: {archive}")
            if any(info.date_time != FIXED_ZIP_TIMESTAMP for info in infos):
                raise RuntimeError(f"Horodatage ZIP non déterministe: {archive}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("first_zip", type=Path)
    parser.add_argument("second_zip", type=Path)
    args = parser.parse_args()
    verify(args.first, args.second, args.first_zip, args.second_zip)
    print("V15_REPRODUCIBILITY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
