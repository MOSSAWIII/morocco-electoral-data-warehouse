from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from morocco_elections.legacy.v9.documentation import main as generate_docs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Point d’entrée compatible du générateur documentaire V9.")
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    generate_docs(data_dir=args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

