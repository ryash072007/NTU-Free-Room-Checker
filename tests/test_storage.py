import sqlite3
from pathlib import Path

from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption, ScheduleEntry
from ntu_room_checker.scraper.storage import ScheduleStorage


def test_saves_deduplicated_entries_and_resumes_run(tmp_path: Path) -> None:
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    programme = ProgrammeOption("CSC;;1;F", "Computer Science Year 1")
    entry = ScheduleEntry(
        "SC1001", "INTRODUCTION", "3.0 AU", "", "10001", "LEC", "LE1",
        "MON", "0830-0920", "LT1", "Teaching Wk1-13", {"INDEX": "10001"},
    )
    db_path = tmp_path / "schedule.db"

    with ScheduleStorage(db_path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [programme])
        selection = storage.remaining_programmes(run_id)[0]
        assert storage.save_entries(run_id, selection["id"], [entry, entry]) == 1
        assert storage.finish_run(run_id) == "completed"

        new_run_id = storage.start_run("https://example.test", term, resume=True)
        assert new_run_id != run_id  # completed snapshots are never silently reused

    connection = sqlite3.connect(db_path)
    assert connection.execute("SELECT COUNT(*) FROM schedule_entries").fetchone()[0] == 1
