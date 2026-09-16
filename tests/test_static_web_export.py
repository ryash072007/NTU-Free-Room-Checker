import json
from pathlib import Path

import pytest

from ntu_room_checker.queries import CalendarTimetableService


ROOT = Path(__file__).parents[1]
DB = ROOT / "data" / "ntu_schedule.db"
STATIC = ROOT / "web" / "public" / "data"


def _static_status(day: dict, room: str, minute: int, duration: int) -> tuple[str, int | None]:
    if day["status"] != "ok":
        return day["status"], None
    if room in day["unparsed_rooms"]:
        return "uncertain", None
    value = day["rooms"].get(room, {"occupied_blocks": [], "uncertain_blocks": []})
    end = minute + duration
    if any(start < end and finish > minute for start, finish, *_ in value["occupied_blocks"]):
        return "occupied", None
    if any(start < end and finish > minute for start, finish, *_ in value["uncertain_blocks"]):
        return "uncertain", None
    future = [start for start, *_ in value["occupied_blocks"] + value["uncertain_blocks"] if start >= end]
    return "free", min(future) if future else None


@pytest.mark.skipif(not DB.exists(), reason="repository timetable database is not present")
def test_generated_catalog_and_location_counts_match_oracle():
    rooms = json.loads((STATIC / "rooms.json").read_text())["rooms"]
    locations = json.loads((STATIC / "locations.json").read_text())["locations"]
    assert len(rooms) == 532
    assert {item["id"]: item["room_count"] for item in locations} == {
        "the-arc": 43, "north-spine": 52, "the-hive": 37, "south-spine": 53,
    }
    assert next(item for item in rooms if item["id"] == "LHN-TR+17")["location_id"] == "the-arc"
    assert next(item for item in rooms if item["id"] == "TR+17")["location_id"] == "north-spine"


@pytest.mark.skipif(not DB.exists(), reason="repository timetable database is not present")
def test_static_availability_matches_python_oracle_matrix():
    dates = ["2026-08-10", "2026-09-04", "2026-09-15", "2026-09-16", "2026-09-29", "2026-11-18"]
    times = [8 * 60, 10 * 60 + 30, 12 * 60 + 25, 14 * 60 + 25, 15 * 60, 18 * 60]
    durations = [1, 5, 30, 120]
    catalog = json.loads((STATIC / "rooms.json").read_text())["rooms"]
    sample = [item["id"] for item in catalog[::53]][:10] + ["LHN-TR+15", "LHN-TR+17", "TR+17"]
    cases = 0
    with CalendarTimetableService(DB) as service:
        for date in dates:
            day = json.loads((STATIC / "days" / f"{date}.json").read_text())
            for room in sample:
                for minute in times:
                    for duration in durations:
                        if minute + duration > 1440:
                            continue
                        expected = service.get_room_availability_for_datetime(
                            room, f"{date}T{minute // 60:02d}:{minute % 60:02d}", duration
                        )
                        actual_status, actual_until = _static_status(day, room, minute, duration)
                        assert actual_status == expected.status
                        assert actual_until == expected.free_until
                        cases += 1
    assert cases == 1872


def test_known_transition_and_calendar_exception_artifacts():
    teaching = json.loads((STATIC / "days" / "2026-09-15.json").read_text())
    assert _static_status(teaching, "LHN-TR+15", 12 * 60 + 25, 5)[0] == "occupied"
    assert _static_status(teaching, "LHN-TR+15", 15 * 60, 30)[0] == "occupied"
    su_day = json.loads((STATIC / "days" / "2026-09-04.json").read_text())
    assert _static_status(su_day, "LHN-TR+15", 11 * 60, 1)[0] != "free"
    assert json.loads((STATIC / "days" / "2026-09-29.json").read_text())["status"] == "regular_timetable_not_applicable"
    assert json.loads((STATIC / "days" / "2026-11-18.json").read_text())["status"] == "regular_timetable_not_authoritative"
