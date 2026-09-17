import json
from pathlib import Path

import pytest

from ntu_room_checker.normalization.runner import normalize_database
from ntu_room_checker.queries import CalendarTimetableService, TimetableQueries
from ntu_room_checker.queries.models import RoomFacility
from ntu_room_checker.scraper.facility_list import FacilityListEntry, FacilityListStorage
from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption, ScheduleEntry
from ntu_room_checker.scraper.storage import ScheduleStorage
from ntu_room_checker.web_export.exporter import export_web_data
from ntu_room_checker.web_export.payloads import room_payload, schedule_payload


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
            oracle = schedule_payload(room, service.get_room_schedule_for_date(room, date))
            assert day["rooms"].get(room, {}).get("schedule", []) == oracle["meetings"]


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


def test_room_payload_omits_unset_fields() -> None:
    bare = room_payload("TR+99", None, None, [], None)
    assert bare == {"id": "TR+99", "name": "TR+99"}

    full = room_payload(
        "LHN-TR+17", "the-arc", "The Arc", ["TUT", "LEC/STUDIO"],
        RoomFacility(capacity=48, bookable_by_staff=True, bookable_by_student_orgs=False),
    )
    assert full == {
        "id": "LHN-TR+17", "name": "LHN-TR+17", "location_id": "the-arc", "location_name": "The Arc",
        "class_types": ["TUT", "LEC/STUDIO"], "capacity": 48,
        "bookable_by_staff": True, "bookable_by_student_orgs": False,
    }


def _typed_entry(code: str, index: str, venue: str, day: str, class_type: str) -> ScheduleEntry:
    return ScheduleEntry(
        code, f"{code} TITLE", "3.0 AU", "", index, class_type, "G1", day,
        "1000-1100", venue, "Teaching Wk1-13", {},
    )


def _class_type_db(tmp_path: Path) -> Path:
    path = tmp_path / "class-types.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "MON", "TUE", "WED", "THU"]
    entries = [
        _typed_entry(f"MX{i:03d}", str(i), "TR+50", days[i], "TUT" if i < 9 else "LEC/STUDIO")
        for i in range(10)
    ] + [_typed_entry("SOLO001", "500", "TR+60", "MON", "LEC/STUDIO")]
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme 1")])
        selection = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, selection["id"], entries)
        storage.finish_run(run_id)
    normalize_database(path)
    return path


def test_class_types_keep_dominant_type_and_drop_a_stray_minority_type(tmp_path: Path) -> None:
    with TimetableQueries(_class_type_db(tmp_path)) as queries:
        class_types = queries.class_types_by_room(2026, 1)
    # 9/10 meetings are TUT; the single LEC/STUDIO meeting is below the 20% floor.
    assert class_types["TR+50"] == ["TUT"]
    assert class_types["TR+60"] == ["LEC/STUDIO"]


def test_class_types_expose_a_genuinely_mixed_use_room(tmp_path: Path) -> None:
    path = tmp_path / "mixed.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    entries = [
        _typed_entry("MX1", "1", "TR+70", "MON", "TUT"),
        _typed_entry("MX2", "2", "TR+70", "TUE", "TUT"),
        _typed_entry("MX3", "3", "TR+70", "WED", "TUT"),
        _typed_entry("MX4", "4", "TR+70", "THU", "LEC/STUDIO"),
    ]
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme 1")])
        selection = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, selection["id"], entries)
        storage.finish_run(run_id)
    normalize_database(path)
    with TimetableQueries(path) as queries:
        class_types = queries.class_types_by_room(2026, 1)
    # LEC/STUDIO is exactly 25% (1/4), above the 20% floor, so both are kept.
    assert class_types["TR+70"] == ["TUT", "LEC/STUDIO"]


def test_export_web_data_wires_class_types_and_facility_capacity(tmp_path: Path) -> None:
    path = _class_type_db(tmp_path)
    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [
            FacilityListEntry(
                spine="NORTH SPINE", facility_name_raw="TR+50", facility_code="TR+50",
                location="NS1-01-01", capacity_raw="48", capacity=48,
                bookable_by_staff_raw="YES", bookable_by_staff=True,
                bookable_by_student_orgs_raw="NO", bookable_by_student_orgs=False,
            ),
        ])
    normalize_database(path, rebuild=True)  # _class_type_db already normalized before the facility scrape

    output = tmp_path / "out"
    export_web_data(path, output)
    rooms = {item["id"]: item for item in json.loads((output / "rooms.json").read_text())["rooms"]}

    assert rooms["TR+50"]["class_types"] == ["TUT"]
    assert rooms["TR+50"]["capacity"] == 48
    assert rooms["TR+50"]["bookable_by_staff"] is True
    assert rooms["TR+50"]["bookable_by_student_orgs"] is False

    # TR+60 has no facility-list row: capacity fields are omitted, never guessed.
    assert rooms["TR+60"]["class_types"] == ["LEC/STUDIO"]
    assert "capacity" not in rooms["TR+60"]
    assert "bookable_by_staff" not in rooms["TR+60"]
