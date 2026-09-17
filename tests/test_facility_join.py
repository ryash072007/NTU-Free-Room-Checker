import sqlite3
from pathlib import Path

from ntu_room_checker.normalization.facility_join import join_facility_list
from ntu_room_checker.normalization.runner import normalize_database
from ntu_room_checker.queries import TimetableQueries
from ntu_room_checker.scraper.facility_list import FacilityListEntry, FacilityListStorage
from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption, ScheduleEntry
from ntu_room_checker.scraper.storage import ScheduleStorage


def entry(code: str, index: str, venue: str) -> ScheduleEntry:
    return ScheduleEntry(
        code, f"{code} TITLE", "3.0 AU", "", index, "TUT", "G1", "MON",
        "1000-1100", venue, "Teaching Wk1-13", {},
    )


def facility_row(
    code: str, capacity: int | None = 40, staff: bool | None = True, student: bool | None = True,
) -> FacilityListEntry:
    return FacilityListEntry(
        spine="NORTH SPINE", facility_name_raw=code, facility_code=code, location="NS1-01-01",
        capacity_raw=str(capacity) if capacity is not None else "", capacity=capacity,
        bookable_by_staff_raw="YES" if staff else ("NO" if staff is False else "MAYBE"),
        bookable_by_staff=staff,
        bookable_by_student_orgs_raw="YES" if student else ("NO" if student is False else "MAYBE"),
        bookable_by_student_orgs=student,
    )


def build_db(tmp_path: Path) -> Path:
    path = tmp_path / "join.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme 1")])
        selection = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, selection["id"], [
            entry("AB1001", "10001", "TR+15"),
            entry("AB1002", "10002", "TR+16"),
        ])
        storage.finish_run(run_id)
    return path


def test_exact_match_and_missing_room_are_unmatched(tmp_path: Path) -> None:
    path = build_db(tmp_path)
    normalize_database(path)
    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [
            facility_row("TR+15", capacity=48),          # exact match
            facility_row("TR+404", capacity=99),          # no canonical room at all
        ])

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    run_id = connection.execute(
        "SELECT id FROM normalization_runs WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    result = join_facility_list(connection, run_id, facility_run_id)

    assert [m.room for m in result.matched] == ["TR+15"]
    assert result.matched[0].capacity == 48
    assert result.matched[0].bookable_by_staff is True
    assert result.matched[0].bookable_by_student_orgs is True
    unmatched_codes = {(row.facility_code, row.reason) for row in result.unmatched}
    assert ("TR+404", "no_canonical_room") in unmatched_codes


def test_zero_padded_facility_codes_match_unpadded_canonical_rooms(tmp_path: Path) -> None:
    """LHN-TR+01..09 (facility list) and LHN-TR+1..9 (timetable) are the same rooms."""
    path = tmp_path / "arc-join.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    unpadded = [f"LHN-TR+{n}" for n in range(1, 10)]
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme 1")])
        selection = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, selection["id"], [
            entry(f"AB{n}", str(n), room) for n, room in enumerate(unpadded, start=1)
        ])
        storage.finish_run(run_id)
    normalize_database(path)

    padded = [f"LHN-TR+0{n}" for n in range(1, 10)]
    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [facility_row(code, capacity=30) for code in padded])

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    run_id = connection.execute(
        "SELECT id FROM normalization_runs WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    result = join_facility_list(connection, run_id, facility_run_id)

    assert sorted(m.room for m in result.matched) == sorted(unpadded)
    assert result.unmatched == ()
    assert all(m.capacity == 30 for m in result.matched)


def test_zero_stripping_does_not_invent_a_match_where_none_exists(tmp_path: Path) -> None:
    path = build_db(tmp_path)  # canonical rooms are TR+15 and TR+16 only
    normalize_database(path)
    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [facility_row("TR+099", capacity=30)])

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    run_id = connection.execute(
        "SELECT id FROM normalization_runs WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    result = join_facility_list(connection, run_id, facility_run_id)

    assert result.matched == ()
    assert result.unmatched[0].reason == "no_canonical_room"


def test_zero_stripping_collision_between_distinct_canonical_rooms_is_ambiguous(tmp_path: Path) -> None:
    """A pathological run with both "TR+1" and "TR+01" as distinct canonical rooms
    must not have zero-stripping silently pick one; it must be reported ambiguous."""
    path = tmp_path / "collision.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme 1")])
        selection = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, selection["id"], [
            entry("AB1", "1", "TR+1"),
            entry("AB2", "2", "TR+01"),
        ])
        storage.finish_run(run_id)
    normalize_database(path)

    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [facility_row("TR+01", capacity=30)])

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    run_id = connection.execute(
        "SELECT id FROM normalization_runs WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    result = join_facility_list(connection, run_id, facility_run_id)

    assert result.matched == ()
    assert result.unmatched[0].reason == "ambiguous_canonical_room"


def test_incomplete_row_is_never_guessed(tmp_path: Path) -> None:
    path = build_db(tmp_path)
    normalize_database(path)
    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [
            facility_row("TR+15", capacity=None),           # blank capacity
            facility_row("TR+16", staff=None),               # unparsed bookable flag
        ])

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    run_id = connection.execute(
        "SELECT id FROM normalization_runs WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    result = join_facility_list(connection, run_id, facility_run_id)

    assert result.matched == ()
    reasons = {row.reason for row in result.unmatched}
    assert reasons == {"incomplete_row"}


def test_ambiguous_many_to_one_rows_are_left_unjoined(tmp_path: Path) -> None:
    path = build_db(tmp_path)
    normalize_database(path)
    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [
            facility_row("TR+15", capacity=40),
            facility_row("tr+15", capacity=45),  # normalizes to the same canonical room
        ])

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    run_id = connection.execute(
        "SELECT id FROM normalization_runs WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    result = join_facility_list(connection, run_id, facility_run_id)

    assert result.matched == ()
    assert all(row.reason == "multiple_facility_rows_for_room" for row in result.unmatched)
    assert len(result.unmatched) == 2


def test_normalize_database_applies_join_and_reports_rooms_with_capacity(tmp_path: Path) -> None:
    path = build_db(tmp_path)
    with FacilityListStorage(path) as facility_storage:
        facility_run_id = facility_storage.start_run("https://example.test/facility")
        facility_storage.save_entries(facility_run_id, [facility_row("TR+15", capacity=48)])

    summary = normalize_database(path)
    assert summary.physical_rooms == 2
    assert summary.rooms_with_capacity == 1

    with TimetableQueries(path) as queries:
        facilities = queries.room_facilities_by_room(2026, 1)
    assert facilities["TR+15"].capacity == 48
    assert "TR+16" not in facilities


def test_normalize_database_without_any_facility_scrape_leaves_capacity_unset(tmp_path: Path) -> None:
    path = build_db(tmp_path)
    summary = normalize_database(path)
    assert summary.rooms_with_capacity == 0
    with TimetableQueries(path) as queries:
        assert queries.room_facilities_by_room(2026, 1) == {}
