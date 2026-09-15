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
        ScheduleEntry("AB1004", "UG UNKNOWN", "3.0 AU", "", "10004", "TUT", "G4", "FRI", "1000-1200", "TR+15", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1005", "CUTOFF CROSS", "3.0 AU", "", "10005", "TUT", "G5", "SAT", "1330-1520", "TR+15", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1006", "AFTER CUTOFF", "3.0 AU", "", "10006", "TUT", "G6", "SAT", "1530-1720", "TR+16", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1007", "UNPARSED", "3.0 AU", "", "10007", "TUT", "G7", "", "unknown", "TR+17", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1008", "HOLIDAY", "3.0 AU", "", "10008", "TUT", "G8", "MON", "1000-1100", "TR+15", "Teaching Wk1-13", {}),
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
    assert "does not apply" in result.reason


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
        result = service.find_free_rooms_for_datetime(
            "2026-09-04T11:00", 60, include_uncertain=True
        )
    assert result.status == "ok"
    assert {room.room for room in result.rooms} == {"TR+16"}
    assert result.uncertain_rooms[0].room == "TR+15"
    assert result.uncertain_rooms[0].reason_codes == ("population_scope_unknown",)


def test_students_union_uncertain_room_is_excluded_by_default(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.find_free_rooms_for_datetime("2026-09-04T11:00", 60)
    assert "TR+15" not in {room.room for room in result.rooms}
    assert result.uncertain_rooms == ()


def test_students_union_exception_does_not_block_outside_window(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.find_free_rooms_for_datetime("2026-09-04T15:00", 60)
    assert result.status == "ok"


def test_schedule_surfaces_students_union_exception(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.get_room_schedule_for_date("TR+15", "2026-09-04")
    assert result.status == "uncertain"
    assert result.calendar.exceptions[0].affected_population == "undergraduate_programmes"
    assert result.evaluated_meetings[0].applicability.reason_code == "population_scope_unknown"


def test_students_union_direct_room_boundary_semantics(tmp_path: Path) -> None:
    path = date_query_db(tmp_path)
    with CalendarTimetableService(path) as service:
        before = service.get_room_availability_for_datetime("TR+15", "2026-09-04T09:00", 60)
        ending_at = service.get_room_availability_for_datetime("TR+15", "2026-09-04T09:30", 60)
        crossing_start = service.get_room_availability_for_datetime("TR+15", "2026-09-04T10:00", 60)
        inside = service.get_room_availability_for_datetime("TR+15", "2026-09-04T11:00", 30)
        crossing_end = service.get_room_availability_for_datetime("TR+15", "2026-09-04T14:00", 60)
        at_end = service.get_room_availability_for_datetime("TR+15", "2026-09-04T14:30", 30)
        after = service.get_room_availability_for_datetime("TR+15", "2026-09-04T15:00", 60)
    assert before.status == "free"
    assert ending_at.status == "occupied"
    assert crossing_start.status == "occupied"  # confirmed 10:00-10:30 portion
    assert inside.status == "uncertain"
    assert crossing_end.status == "free"
    assert at_end.status == "free"
    assert after.status == "free"


def test_holiday_eve_effective_intervals_drive_availability_and_free_until(
    tmp_path: Path,
) -> None:
    path = date_query_db(tmp_path)
    with CalendarTimetableService(path) as service:
        before = service.get_room_availability_for_datetime("TR+15", "2026-11-07T12:00", 60)
        crossing = service.get_room_availability_for_datetime("TR+15", "2026-11-07T14:00", 30)
        after = service.get_room_availability_for_datetime("TR+15", "2026-11-07T14:30", 60)
        removed = service.get_room_availability_for_datetime("TR+16", "2026-11-07T15:30", 60)
    assert before.status == "free"
    assert before.free_until == 13 * 60 + 30
    assert crossing.status == "occupied"
    assert crossing.occupied_intervals[0].end_minute == 14 * 60 + 30
    assert after.status == "free"
    assert removed.status == "free"


def test_public_holiday_and_replacement_are_uncertain_not_free(tmp_path: Path) -> None:
    path = date_query_db(tmp_path)
    with CalendarTimetableService(path) as service:
        actual = service.get_room_availability_for_datetime("TR+15", "2026-08-09T11:00", 60)
        replacement = service.get_room_availability_for_datetime("TR+15", "2026-08-10T11:00", 60)
    assert actual.status == "regular_timetable_not_authoritative"
    assert replacement.status == "regular_timetable_not_authoritative"
    assert actual.is_free is None
    assert replacement.is_free is None


def test_public_holiday_schedule_retains_rows_as_uncertain(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.get_room_schedule_for_date("TR+15", "2026-08-10")
    assert result.status == "uncertain"
    assert result.meetings
    assert all(
        item.applicability.reason_code == "public_holiday_timetable_uncertain"
        for item in result.evaluated_meetings
    )


def test_unparsed_meeting_keeps_direct_room_availability_uncertain(tmp_path: Path) -> None:
    with CalendarTimetableService(date_query_db(tmp_path)) as service:
        result = service.get_room_availability_for_datetime(
            "TR+17", "2026-09-15T15:00", 60
        )
    assert result.status == "uncertain"
    assert result.uncertainty_reason_codes == ("unparsed_timetable_meeting",)


def test_transition_buffer_availability_and_uncertainty_semantics(tmp_path: Path) -> None:
    import pytest
    path = tmp_path / "trans_cal.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    entries = [
        ScheduleEntry("AB1", "1", "3.0 AU", "", "1", "TUT", "G1", "TUE", "1000-1100", "TR+10", "Teaching Wk1-13", {}),
        ScheduleEntry("AB2", "2", "3.0 AU", "", "2", "TUT", "G2", "TUE", "1110-1200", "TR+10", "Teaching Wk1-13", {}),
        ScheduleEntry("AB3", "3", "3.0 AU", "", "3", "TUT", "G3", "TUE", "1210-1300", "TR+10", "Teaching Wk1-13", {}),
        ScheduleEntry("AB4", "4", "3.0 AU", "", "4", "TUT", "G4", "TUE", "1000-1100", "TR+20", "Teaching Wk1-13", {}),
        ScheduleEntry("AB5", "5", "3.0 AU", "", "5", "TUT", "G5", "TUE", "1115-1200", "TR+20", "Teaching Wk1-13", {}),
        ScheduleEntry("AB6", "6", "3.0 AU", "", "6", "TUT", "G6", "FRI", "0930-1030", "TR+30", "Teaching Wk1-13", {}),
        ScheduleEntry("AB7", "7", "3.0 AU", "", "7", "TUT", "G7", "FRI", "1040-1200", "TR+30", "Teaching Wk1-13", {}),
        ScheduleEntry("AB8", "8", "3.0 AU", "", "8", "TUT", "G8", "FRI", "1300-1430", "TR+40", "Teaching Wk1-13", {}),
        ScheduleEntry("AB9", "9", "3.0 AU", "", "9", "TUT", "G9", "FRI", "1440-1600", "TR+40", "Teaching Wk1-13", {}),
    ]
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme")])
        sel = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, sel["id"], entries)
        storage.finish_run(run_id)
    normalize_database(path)

    with CalendarTimetableService(path) as service:
        # 6. free-room search during transition gap -> room excluded
        free_rooms = service.find_free_rooms_for_datetime("2026-09-15T11:05", 5)
        room_names = {r.room for r in free_rooms.rooms}
        assert "TR+10" not in room_names
        assert "TR+20" in room_names

        # 7. room availability during transition gap -> occupied, reason room_transition_buffer
        avail = service.get_room_availability_for_datetime("TR+10", "2026-09-15T11:05", 5)
        assert avail.status == "occupied"
        assert avail.is_free is False
        assert avail.uncertainty_reason_codes == ("room_transition_buffer",)
        assert "transition between consecutive classes" in avail.reason

        # 8. free-until with chained classes -> stops at beginning of continuous occupied block
        before = service.get_room_availability_for_datetime("TR+10", "2026-09-15T09:00", 30)
        assert before.status == "free"
        assert before.is_free is True
        assert before.free_until == 600  # 10:00

        # Also verify 15-minute gap allows free interval:
        gap_avail = service.get_room_availability_for_datetime("TR+20", "2026-09-15T11:02", 5)
        assert gap_avail.status == "free"
        assert gap_avail.is_free is True
        assert gap_avail.free_until == 675  # 11:15

        # 9. uncertainty beside a <=10-minute transition:
        # TR+30: confirmed ends 10:30. Uncertain meeting starts 10:40.
        # Query at 10:35 (5 min) is in the 10:30-10:40 transition gap adjacent to uncertain meeting:
        trans_u1 = service.get_room_availability_for_datetime("TR+30", "2026-09-04T10:35", 5)
        assert trans_u1.status == "uncertain"
        assert trans_u1.is_free is None

        # TR+40: uncertain meeting ends 14:30. Confirmed meeting starts 14:40.
        # Query at 14:35 (5 min) is in the 14:30-14:40 transition gap adjacent to uncertain meeting:
        trans_u2 = service.get_room_availability_for_datetime("TR+40", "2026-09-04T14:35", 5)
        assert trans_u2.status == "uncertain"
        assert trans_u2.is_free is None


def test_real_dataset_transition_and_gap_verification() -> None:
    import pytest
    db_path = Path("data/ntu_schedule.db")
    if not db_path.is_file():
        pytest.skip("Production database data/ntu_schedule.db not found")

    with CalendarTimetableService(db_path) as service:
        for check_time in ["12:25", "14:25", "16:25"]:
            avail = service.get_room_availability_for_datetime(
                "LHN-TR+15", f"2026-09-15T{check_time}", 5
            )
            assert avail.status == "occupied"
            assert avail.is_free is False
            assert avail.uncertainty_reason_codes == ("room_transition_buffer",)

            free = service.find_free_rooms_for_datetime(f"2026-09-15T{check_time}", 5)
            assert not any(r.room == "LHN-TR+15" for r in free.rooms)

        morning = service.get_room_availability_for_datetime(
            "LHN-TR+15", "2026-09-15T10:00", 15
        )
        assert morning.status == "free"
        assert morning.is_free is True
        assert morning.free_until == 630  # 10:30

        cskl_avail = service.get_room_availability_for_datetime(
            "CSKL10B", "2026-09-15T14:00", 15
        )
        assert cskl_avail.status == "free"
        assert cskl_avail.is_free is True
        assert cskl_avail.free_until == 870  # 14:30
        cskl_free = service.find_free_rooms_for_datetime("2026-09-15T14:00", 15)
        assert any(r.room == "CSKL10B" for r in cskl_free.rooms)

