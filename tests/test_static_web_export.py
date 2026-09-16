import json
from pathlib import Path

import pytest

from ntu_room_checker.queries import CalendarTimetableService
from ntu_room_checker.api.serialization import schedule_response


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


@pytest.mark.skipif(not DB.exists(), reason="repository timetable database is not present")
def test_room_search_and_schedule_match_python_oracle():
    catalog = json.loads((STATIC / "rooms.json").read_text())["rooms"]
    ids = [item["id"] for item in catalog]
    with CalendarTimetableService(DB) as service:
        for query in ("LHN", "TR+17", "LT", "ABS-SR", "NIE"):
            needle = query.upper()
            static = sorted(
                (room for room in ids if needle in room),
                key=lambda room: (0 if room == needle else 1 if room.startswith(needle) else 2, len(room), room),
            )[:20]
            oracle = [item.id for item in service.queries.search_rooms(query, 20)]
            assert static == oracle
        for date, room in (("2026-09-15", "LHN-TR+15"), ("2026-09-04", "LHN-TR+17"), ("2026-09-16", "TR+17")):
            day = json.loads((STATIC / "days" / f"{date}.json").read_text())
            oracle = schedule_response(room, service.get_room_schedule_for_date(room, date))
            assert day["rooms"].get(room, {}).get("schedule", []) == oracle.model_dump(mode="json")["meetings"]


@pytest.mark.skipif(not DB.exists(), reason="repository timetable database is not present")
def test_named_location_status_and_order_match_python_oracle():
    day = json.loads((STATIC / "days" / "2026-09-16.json").read_text())
    locations = json.loads((STATIC / "locations.json").read_text())["locations"]
    minute, duration = 14 * 60 + 25, 1
    with CalendarTimetableService(DB) as service:
        for location in locations:
            static = []
            for room in location["rooms"]:
                status, free_until = _static_status(day, room, minute, duration)
                value = day["rooms"].get(room, {"occupied_blocks": []})
                occupied = [b for b in value["occupied_blocks"] if b[0] < minute + duration and b[1] > minute]
                available_from = max((b[1] for b in occupied), default=None)
                static.append((room, status, free_until, available_from))
            static.sort(key=lambda item: (
                0 if item[1] == "free" else 1 if item[1] == "occupied" else 2,
                -(1441 if item[2] is None else item[2] - minute) if item[1] == "free" else
                (item[3] or 1441) if item[1] == "occupied" else 0,
                item[0],
            ))
            oracle = service.get_location_rooms_for_datetime(location["id"], "2026-09-16T14:25", 1)
            assert [(x.room, x.status, x.free_until, x.available_from) for x in oracle.rooms] == static
