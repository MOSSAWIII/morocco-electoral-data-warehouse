"""Temporary compatibility wrapper; use ``morocco-elections audit``."""

from morocco_elections.warehouse.auditor import main


if __name__ == "__main__":
    raise SystemExit(main())
