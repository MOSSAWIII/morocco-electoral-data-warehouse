"""Official result universes extracted directly from pinned institutional bytes."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


CHAMBER_2021_SOURCE_ID = "SRC_CHAMBER_2021"
CHAMBER_2021_UNIVERSE_ID = "LEG2021:OFFICIAL:NATIONAL_PARTY_SEATS"
EXPECTED_PARTIES = frozenset({"RNI", "PAM", "PI", "USFP", "MP", "PPS", "UC", "PJD", "MDS", "FFD", "CNI", "PSU"})


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def load_chamber_2021_seat_universe(
    path: Path, *, source_url: str, acquired_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract the national party/seat vector published by the House."""
    parser = _TableParser()
    parser.feed(path.read_text(encoding="utf-8"))
    table = next(
        (rows for rows in parser.tables if rows and rows[0] == ["Political affiliation", "Number of seats"]),
        None,
    )
    if table is None:
        raise ValueError("official Chamber party-seat table is absent")
    allocations: dict[str, int] = {}
    for row in table[1:]:
        if len(row) != 2:
            raise ValueError("official Chamber party-seat row has an unexpected grain")
        match = re.search(r"\(([A-Z0-9]+)\)\s*$", row[0])
        if match is None or not row[1].isdigit():
            raise ValueError("official Chamber party or seat identifier is not parseable")
        party_id = match.group(1)
        if party_id in allocations:
            raise ValueError("official Chamber party identifier is duplicated")
        allocations[party_id] = int(row[1])
    if set(allocations) != EXPECTED_PARTIES or sum(allocations.values()) != 395:
        raise ValueError("official Chamber national allocation is incomplete or changed")
    universe = {
        "universe_id": CHAMBER_2021_UNIVERSE_ID,
        "election_id": "LEG2021",
        "coverage_dimension": "OFFICIAL",
        "universe_type": "OFFICIAL_SEAT_ALLOCATIONS",
        "denominator": len(allocations),
        "source_id": CHAMBER_2021_SOURCE_ID,
        "source_url": source_url,
        "acquired_at": acquired_at,
        "verification_status": "VERIFIED",
        "is_external": True,
        "member_extraction_method": "CHAMBER_2021_NATIONAL_SEATS",
    }
    members = [
        {
            "universe_id": CHAMBER_2021_UNIVERSE_ID,
            "expected_id": party_id,
            "source_id": CHAMBER_2021_SOURCE_ID,
            "member_type": "PARTY_SEAT_ALLOCATION",
            "expected_value": seats,
            "unit": "seats",
        }
        for party_id, seats in sorted(allocations.items())
    ]
    return universe, members
