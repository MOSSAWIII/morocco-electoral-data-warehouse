from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from morocco_elections.legacy.v9.build import main as build_v9  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Point d’entrée compatible du constructeur V9.")
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    build_v9(data_dir=args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

