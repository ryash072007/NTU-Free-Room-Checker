from pathlib import Path

from ntu_room_checker.normalization.runner import normalize_database
from ntu_room_checker.queries import TimetableQueries
from ntu_room_checker.queries.service import overlaps
from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption, ScheduleEntry
from ntu_room_checker.scraper.storage import ScheduleStorage


def entry(
    code: str, index: str, venue: str, time: str, *, remark: str = "Teaching Wk1-13"
) -> ScheduleEntry:
    return ScheduleEntry(
        code, f"{code} TITLE", "3.0 AU", "", index, "TUT", "G1", "MON",
        time, venue, remark, {"fixture": True},
    )


def canonical_db(tmp_path: Path) -> Path:
    path = tmp_path / "canonical.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    shared = entry("AB1001", "10001", "TR+15", "1000-1100")
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        programmes = [ProgrammeOption("P1", "Programme 1"), ProgrammeOption("P2", "Programme 2")]
        storage.register_programmes(run_id, programmes)
        selections = storage.remaining_programmes(run_id)
        storage.save_entries(
            run_id, selections[0]["id"],
            [shared, entry("AB1002", "10002", "TR+15", "1300-1400", remark="")],
        )
        storage.save_entries(
            run_id, selections[1]["id"],
            [shared, entry("AB1003", "10003", "TR+16", "1100-1200"),
             entry("AB1004", "10004", "TR+17", "unknown")],
        )
        storage.finish_run(run_id)
    normalize_database(path)
    return path


def test_canonical_deduplication_and_provenance(tmp_path: Path) -> None:
    path = canonical_db(tmp_path)
    summary = normalize_database(path)  # idempotent without --rebuild
    assert summary.raw_rows == 5
    assert summary.canonical_classes == 4
    assert summary.canonical_meetings == 4
    assert summary.provenance_links == 5
    with TimetableQueries(path) as queries:
        meeting = queries.get_room_schedule("tr+15", 2026, 1, "MON", teaching_week=2)[0]
    assert meeting.course_code == "AB1001"
    assert meeting.source_count == 2


def test_room_schedule_order_and_conservative_blank_remark(tmp_path: Path) -> None:
    with TimetableQueries(canonical_db(tmp_path)) as queries:
        rows = queries.get_room_schedule("TR+15", 2026, 1, "MON", teaching_week=12)
        intervals = queries.occupied_intervals(
            "TR+15", 2026, 1, "MON", teaching_week=12
        )
    assert [row.start_minute for row in rows] == [600, 780]
    assert rows[1].week_parse_status == "unspecified_conservative"
    assert [(item.start_minute, item.end_minute) for item in intervals] == [
        (600, 660), (780, 840)
    ]


def test_free_rooms_overlap_boundaries_and_free_until(tmp_path: Path) -> None:
    assert not overlaps(600, 660, 660, 720)
    assert overlaps(600, 660, 659, 720)
    with TimetableQueries(canonical_db(tmp_path)) as queries:
        free = queries.find_free_rooms(2026, 1, "MON", "1100", 60, teaching_week=2)
    by_room = {row.room: row for row in free}
    assert by_room["TR+15"].free_until == 780
    assert by_room["TR+15"].free_duration_minutes == 120
    assert "TR+16" not in by_room
    assert "TR+17" not in by_room  # unknown time is conservatively unavailable


def test_balanced_quote_is_only_a_normalized_alias() -> None:
    from ntu_room_checker.normalization.venue import normalize_venue

    result = normalize_venue('"LT1A"')
    assert result.raw == '"LT1A"'
    assert result.normalized == "LT1A"
