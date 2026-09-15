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


def test_queries_cross_thread_and_read_only_support(tmp_path: Path) -> None:
    import concurrent.futures

    path = canonical_db(tmp_path)
    queries = TimetableQueries(path)
    try:
        # Cross-thread query execution (AnyIO threadpool pattern)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(queries.search_rooms, "TR+", 5)
            results = future.result()
            assert len(results) >= 2
    finally:
        queries.close()

    assert TimetableQueries.database_available(path) is True


def test_interval_coalescing_rules() -> None:
    from ntu_room_checker.queries.models import ROOM_TRANSITION_MINUTES, RoomMeeting
    from ntu_room_checker.queries.service import coalesce_occupied_intervals

    assert ROOM_TRANSITION_MINUTES == 10

    def make_meeting(mid: int, start: int, end: int) -> RoomMeeting:
        return RoomMeeting(
            meeting_id=mid,
            course_code="TEST",
            course_title="Title",
            index_number="12345",
            class_type="LEC",
            group_name="G1",
            day_of_week=1,
            start_minute=start,
            end_minute=end,
            venue="TR+15",
            remark="",
            teaching_weeks=(1, 2, 3),
            week_parse_status="parsed",
            source_count=1,
        )

    # 1. adjacent classes: 10:00–11:00, 11:00–12:00 -> continuous occupied [600, 720]
    m1 = make_meeting(1, 600, 660)
    m2 = make_meeting(2, 660, 720)
    res = coalesce_occupied_intervals([m1, m2])
    assert len(res) == 1
    assert (res[0].start_minute, res[0].end_minute) == (600, 720)
    assert res[0].meeting_ids == (1, 2)

    # 2. 5-minute gap: 10:00–11:00, 11:05–12:00 -> continuous occupied [600, 720]
    m2_5 = make_meeting(2, 665, 720)
    res_5 = coalesce_occupied_intervals([m1, m2_5])
    assert len(res_5) == 1
    assert (res_5[0].start_minute, res_5[0].end_minute) == (600, 720)

    # 3. exactly 10-minute gap: 10:00–11:00, 11:10–12:00 -> continuous occupied [600, 720]
    m2_10 = make_meeting(2, 670, 720)
    res_10 = coalesce_occupied_intervals([m1, m2_10])
    assert len(res_10) == 1
    assert (res_10[0].start_minute, res_10[0].end_minute) == (600, 720)

    # 4. 11-minute gap: 10:00–11:00, 11:11–12:00 -> separate intervals
    m2_11 = make_meeting(2, 671, 720)
    res_11 = coalesce_occupied_intervals([m1, m2_11])
    assert len(res_11) == 2
    assert (res_11[0].start_minute, res_11[0].end_minute) == (600, 660)
    assert (res_11[1].start_minute, res_11[1].end_minute) == (671, 720)

    # 5. multiple chained 10-minute gaps: 10:00–11:00, 11:10–12:00, 12:10–13:00 -> continuous [600, 780]
    m3 = make_meeting(3, 730, 780)
    res_chain = coalesce_occupied_intervals([m1, m2_10, m3])
    assert len(res_chain) == 1
    assert (res_chain[0].start_minute, res_chain[0].end_minute) == (600, 780)
    assert res_chain[0].meeting_ids == (1, 2, 3)


def test_canonical_free_rooms_transition_exclusion(tmp_path: Path) -> None:
    path = tmp_path / "trans.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    e1 = entry("AB1", "1", "TR+10", "1000-1100")
    e2 = entry("AB2", "2", "TR+10", "1110-1200")
    e3 = entry("AB3", "3", "TR+20", "1000-1100")
    e4 = entry("AB4", "4", "TR+20", "1115-1200")
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme")])
        sel = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, sel["id"], [e1, e2, e3, e4])
        storage.finish_run(run_id)
    normalize_database(path)

    with TimetableQueries(path) as queries:
        free = queries.find_free_rooms(2026, 1, "MON", "1105", 5, teaching_week=1)
        by_room = {r.room: r for r in free}
        assert "TR+10" not in by_room
        assert "TR+20" in by_room
        assert by_room["TR+20"].free_until == 675


