from __future__ import annotations

import sys
from pathlib import Path

from conftest import canonical_database


def main() -> None:
    destination = Path(sys.argv[1]).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    generated = canonical_database.__wrapped__(destination.parent)
    if generated != destination:
        generated.replace(destination)


if __name__ == "__main__":
    main()
