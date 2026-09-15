from pathlib import Path

from ntu_room_checker.normalization.runner import normalize_database
from ntu_room_checker.queries import CalendarTimetableService
from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption, ScheduleEntry
from ntu_room_checker.scraper.storage import ScheduleStorage


def date_query_db(tmp_path: Path) -> Path:
    path = tmp_path / "calendar-query.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    entries = [
        ScheduleEntry("AB1001", "FIRST", "3.0 AU", "", "10001", "TUT", "G1", "TUE", "1430-1530", "TR+15", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1002", "NEXT", "3.0 AU", "", "10002", "TUT", "G2", "TUE", "1700-1800", "TR+15", "", {}),
        ScheduleEntry("AB1003", "OTHER", "3.0 AU", "", "10003", "TUT", "G3", "TUE", "1000-1100", "TR+16", "Teaching Wk1-13", {}),
    ]
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme")])
        selection = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, selection["id"], entries)
        storage.finish_run(run_id)
    normalize_database(path)
    return path


def test_date_aware_room_schedule_uses_resolved_weekday_and_week(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.get_room_schedule_for_date("TR+15", "2026-09-15")
    assert result.status == "ok"
    assert result.calendar.teaching_week == 6
    assert [meeting.course_code for meeting in result.meetings] == ["AB1001", "AB1002"]


def test_date_aware_free_rooms_and_room_availability(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        rooms = service.find_free_rooms_for_datetime("2026-09-15T15:30", 60)
        room = service.get_room_availability_for_datetime("TR+15", "2026-09-15T15:30", 60)
    assert rooms.status == "ok"
    assert {item.room for item in rooms.rooms} == {"TR+15", "TR+16"}
    assert room.is_free is True
    assert room.free_until == 17 * 60


def test_non_teaching_period_refuses_to_claim_rooms_are_free(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.find_free_rooms_for_datetime("2026-09-28T14:30", 120)
    assert result.status == "regular_timetable_not_applicable"
    assert result.rooms == ()
    assert "unknown" in result.reason


def test_missing_semester_dataset_is_reported_not_assumed_free(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.find_free_rooms_for_datetime("2027-01-12T14:30", 120)
    assert result.status == "normalized_timetable_unavailable"
    assert result.rooms == ()


def test_unknown_room_is_not_reported_as_occupied_or_free(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.get_room_availability_for_datetime(
            "NOT-A-ROOM", "2026-09-15T15:30", 60
        )
    assert result.status == "unknown_room"
    assert result.is_free is None


def test_students_union_window_blocks_confident_availability(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.find_free_rooms_for_datetime("2026-09-04T11:00", 60)
    assert result.status == "calendar_exception_unapplied"
    assert result.rooms == ()
    assert "undergraduate_programmes" in result.reason


def test_students_union_exception_does_not_block_outside_window(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.find_free_rooms_for_datetime("2026-09-04T15:00", 60)
    assert result.status == "ok"


def test_schedule_surfaces_students_union_exception(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.get_room_schedule_for_date("TR+15", "2026-09-04")
    assert result.status == "ok_with_calendar_exception"
    assert result.calendar.exceptions[0].affected_population == "undergraduate_programmes"
