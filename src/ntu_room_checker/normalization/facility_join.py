"""Join NTU's public facility list against canonical timetable rooms.

Uses the same conservative normalization pass already applied to canonical
room identifiers (:func:`ntu_room_checker.normalization.venue.normalize_venue`),
plus one narrow, evidence-based extra step: the facility list zero-pads the
numeric suffix of some room codes (``LHN-TR+01``) while the timetable's own
venue strings do not (``LHN-TR+1``). Both sides are compared with leading
zeros stripped from a trailing ``+<digits>`` suffix only -- never a fuzzy or
substring match -- so this recognizes "1" and "01" as the same number without
risking an unrelated coincidental match.

A facility-list row is matched only when its normalized (and zero-suffix
-stripped) facility code equals exactly one canonical room's normalized (and
zero-suffix-stripped) identifier for the run. Anything else -- no canonical
room with that identifier, an incomplete row (capacity or a bookable flag
failed to parse), or an ambiguous many-to-one collision (including one this
stripping step would create, e.g. if a run somehow had both "TR+1" and
"TR+01" as distinct canonical rooms) -- is left unjoined and reported, never
force-matched or guessed.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from ntu_room_checker.normalization.venue import normalize_venue

_ZERO_PADDED_SUFFIX = re.compile(r"\+0*(\d+)$")


def _strip_zero_padding(normalized: str) -> str:
    """Strip leading zeros from a trailing ``+<digits>`` suffix, if present.

    Idempotent and a no-op on already-unpadded identifiers (e.g. every
    canonical room), so applying it to both sides of the join never changes
    an existing exact match -- it only lets a zero-padded facility-list code
    reach the same key as its unpadded canonical room.
    """
    return _ZERO_PADDED_SUFFIX.sub(lambda match: f"+{match.group(1)}", normalized)


@dataclass(frozen=True, slots=True)
class RoomFacilityMatch:
    room: str
    capacity: int
    bookable_by_staff: bool
    bookable_by_student_orgs: bool


@dataclass(frozen=True, slots=True)
class UnmatchedFacilityRow:
    facility_code: str
    facility_name_raw: str
    reason: str


@dataclass(frozen=True, slots=True)
class FacilityJoinResult:
    matched: tuple[RoomFacilityMatch, ...]
    unmatched: tuple[UnmatchedFacilityRow, ...]


def join_facility_list(
    connection: sqlite3.Connection, normalization_run_id: int, facility_list_run_id: int,
) -> FacilityJoinResult:
    room_rows = connection.execute(
        """SELECT venue_display, venue_normalized FROM rooms
           WHERE normalization_run_id = ? AND venue_type = 'physical_room'""",
        (normalization_run_id,),
    ).fetchall()
    rooms_by_normalized: dict[str, list[str]] = {}
    for display, normalized in room_rows:
        rooms_by_normalized.setdefault(_strip_zero_padding(normalized), []).append(display)

    facility_rows = connection.execute(
        """SELECT facility_code, facility_name_raw, capacity, bookable_by_staff,
                  bookable_by_student_orgs
           FROM facility_list_entries WHERE run_id = ?""",
        (facility_list_run_id,),
    ).fetchall()

    unmatched: list[UnmatchedFacilityRow] = []
    candidates_by_room: dict[str, list[sqlite3.Row]] = {}
    for row in facility_rows:
        if (
            row["capacity"] is None
            or row["bookable_by_staff"] is None
            or row["bookable_by_student_orgs"] is None
        ):
            unmatched.append(UnmatchedFacilityRow(row["facility_code"], row["facility_name_raw"], "incomplete_row"))
            continue
        normalized = _strip_zero_padding(normalize_venue(row["facility_code"]).normalized)
        displays = rooms_by_normalized.get(normalized)
        if not displays:
            unmatched.append(UnmatchedFacilityRow(row["facility_code"], row["facility_name_raw"], "no_canonical_room"))
            continue
        if len(displays) > 1:
            unmatched.append(UnmatchedFacilityRow(row["facility_code"], row["facility_name_raw"], "ambiguous_canonical_room"))
            continue
        candidates_by_room.setdefault(displays[0], []).append(row)

    matched: list[RoomFacilityMatch] = []
    for room, candidates in candidates_by_room.items():
        if len(candidates) > 1:
            unmatched.extend(
                UnmatchedFacilityRow(row["facility_code"], row["facility_name_raw"], "multiple_facility_rows_for_room")
                for row in candidates
            )
            continue
        row = candidates[0]
        matched.append(RoomFacilityMatch(
            room=room,
            capacity=int(row["capacity"]),
            bookable_by_staff=bool(row["bookable_by_staff"]),
            bookable_by_student_orgs=bool(row["bookable_by_student_orgs"]),
        ))
    return FacilityJoinResult(tuple(matched), tuple(unmatched))
