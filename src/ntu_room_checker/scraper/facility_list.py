"""Fetch, parse, and store NTU's public Facility Location and Capacity list.

This is a second, independent public source from the class-schedule scraper:
https://wis.ntu.edu.sg/pls/webexe88/FBSDOCU.FBSLOCATN lists SPINES, FACILITY,
CAPACITY, LOCATION, and both "Bookable by ..." columns for North Spine, Sci
Building, South Spine, and The Arc. The page itself states it only lists LTs
and TRs, so most other room families are legitimately absent, not missed.

Raw provenance is stored the same way the schedule scraper does (see
scraper/storage.py): every parsed row is kept, including ones with a blank or
non-numeric capacity or a non-YES/NO bookable cell, so a page-layout change or
a bad parse is visible in the stored data rather than silently dropped.
"""

from __future__ import annotations

import re
import sqlite3
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

FACILITY_LIST_URL = "https://wis.ntu.edu.sg/pls/webexe88/FBSDOCU.FBSLOCATN"
_CODE_TOKEN = re.compile(r"^[A-Z0-9+\-./]+$")


@dataclass(frozen=True, slots=True)
class FacilityListEntry:
    spine: str
    facility_name_raw: str
    facility_code: str
    location: str
    capacity_raw: str
    capacity: int | None
    bookable_by_staff_raw: str
    bookable_by_staff: bool | None
    bookable_by_student_orgs_raw: str
    bookable_by_student_orgs: bool | None


def fetch_facility_list_html(url: str = FACILITY_LIST_URL, *, timeout: float = 30.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (fixed, public NTU URL)
        return response.read().decode("utf-8", errors="replace")


def _extract_code(facility_name: str) -> str:
    """Split the leading facility-code tokens off a descriptive facility name.

    Facility codes are always upper-case with digits/+/-/./ characters
    (``LT1``, ``TCT-LT``, ``LHN-TR+17``); descriptions are free text that
    always contains a lower-case word ("Tan Chin Tuan Lecture Theatre",
    "dedicated to students' use"). Consuming only the leading all-code tokens
    keeps the split conservative: a name with no description at all (e.g.
    "S3.2 ESR4") is kept whole rather than guessed at.
    """
    tokens = facility_name.split()
    code_tokens: list[str] = []
    for token in tokens:
        if _CODE_TOKEN.fullmatch(token):
            code_tokens.append(token)
        else:
            break
    return " ".join(code_tokens) if code_tokens else facility_name.strip()


def _parse_bool(value: str) -> bool | None:
    upper = value.strip().upper()
    if upper == "YES":
        return True
    if upper == "NO":
        return False
    return None


def _parse_capacity(value: str) -> int | None:
    stripped = value.strip()
    return int(stripped) if stripped.isdigit() else None


def parse_facility_list_html(html: str) -> list[FacilityListEntry]:
    """Parse every data row of the four spine/building sections.

    Rows are recognized purely by having exactly six direct ``<td>`` cells
    (SPINES/FACILITY/CAPACITY/LOCATION/staff/student-orgs); the header row is
    excluded by its literal "SPINES" label. A layout change that removes this
    shape yields an empty (or short) result rather than misaligned columns.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: list[FacilityListEntry] = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 6:
            continue
        spine, facility_name, capacity_raw, location, staff_raw, student_raw = (
            " ".join(cell.stripped_strings) for cell in cells
        )
        if spine.strip().upper() == "SPINES":
            continue
        facility_name = facility_name.strip()
        if not facility_name:
            continue
        entries.append(FacilityListEntry(
            spine=spine.strip(),
            facility_name_raw=facility_name,
            facility_code=_extract_code(facility_name),
            location=location.strip(),
            capacity_raw=capacity_raw.strip(),
            capacity=_parse_capacity(capacity_raw),
            bookable_by_staff_raw=staff_raw.strip(),
            bookable_by_staff=_parse_bool(staff_raw),
            bookable_by_student_orgs_raw=student_raw.strip(),
            bookable_by_student_orgs=_parse_bool(student_raw),
        ))
    return entries


def _now() -> str:
    return datetime.now(UTC).isoformat()


class FacilityListStorage:
    """Raw provenance storage for facility-list scrape runs, in the same db file."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "FacilityListStorage":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS facility_list_runs (
                id INTEGER PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                source_url TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS facility_list_entries (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES facility_list_runs(id) ON DELETE CASCADE,
                row_index INTEGER NOT NULL,
                spine TEXT NOT NULL,
                facility_name_raw TEXT NOT NULL,
                facility_code TEXT NOT NULL,
                location TEXT NOT NULL,
                capacity_raw TEXT NOT NULL,
                capacity INTEGER,
                bookable_by_staff_raw TEXT NOT NULL,
                bookable_by_staff INTEGER,
                bookable_by_student_orgs_raw TEXT NOT NULL,
                bookable_by_student_orgs INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_facility_entries_run
                ON facility_list_entries (run_id, facility_code);
            """
        )

    def start_run(self, source_url: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO facility_list_runs (started_at, source_url, status) VALUES (?, ?, 'running')",
            (_now(), source_url),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def save_entries(self, run_id: int, entries: Iterable[FacilityListEntry]) -> int:
        rows = list(entries)
        with self.connection:
            self.connection.executemany(
                """INSERT INTO facility_list_entries
                   (run_id, row_index, spine, facility_name_raw, facility_code, location,
                    capacity_raw, capacity, bookable_by_staff_raw, bookable_by_staff,
                    bookable_by_student_orgs_raw, bookable_by_student_orgs)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        run_id, index, item.spine, item.facility_name_raw, item.facility_code,
                        item.location, item.capacity_raw, item.capacity, item.bookable_by_staff_raw,
                        None if item.bookable_by_staff is None else int(item.bookable_by_staff),
                        item.bookable_by_student_orgs_raw,
                        None if item.bookable_by_student_orgs is None else int(item.bookable_by_student_orgs),
                    )
                    for index, item in enumerate(rows)
                ),
            )
            self.connection.execute(
                "UPDATE facility_list_runs SET status = 'completed', completed_at = ? WHERE id = ?",
                (_now(), run_id),
            )
        return len(rows)

    def fail_run(self, run_id: int, error: str) -> None:
        self.connection.execute(
            "UPDATE facility_list_runs SET status = 'failed', completed_at = ?, error_message = ? WHERE id = ?",
            (_now(), error[:4000], run_id),
        )
        self.connection.commit()

    def latest_completed_run(self) -> int | None:
        row = self.connection.execute(
            "SELECT id FROM facility_list_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return int(row[0]) if row is not None else None


def run_facility_list_scrape(db_path: Path, *, url: str = FACILITY_LIST_URL) -> tuple[int, int]:
    """Fetch, parse, and store one facility-list snapshot. Returns (run_id, row_count)."""
    with FacilityListStorage(db_path) as storage:
        run_id = storage.start_run(url)
        try:
            html = fetch_facility_list_html(url)
            entries = parse_facility_list_html(html)
            if not entries:
                raise ValueError("Parsed zero facility rows; the page layout may have changed")
            return run_id, storage.save_entries(run_id, entries)
        except Exception as error:
            storage.fail_run(run_id, repr(error))
            raise
