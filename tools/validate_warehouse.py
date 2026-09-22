"""Temporary compatibility wrapper; use ``morocco-elections validate``."""

from morocco_elections.warehouse.validator import main


if __name__ == "__main__":
    raise SystemExit(main())
