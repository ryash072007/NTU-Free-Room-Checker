"""Reproducible profiling of raw NTU schedule data."""

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProfileSummary:
    raw_rows: int
    distinct_courses: int
    programme_selections: int
    distinct_venues: int
    distinct_days: int
    distinct_times: int
    distinct_remarks: int
    blank_days: int
    blank_times: int
    blank_venues: int
    blank_remarks: int
    tentative_canonical_classes: int
    tentative_canonical_meetings: int
    meetings_without_remark_in_key: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def profile_database(path: Path) -> ProfileSummary:
    connection = sqlite3.connect(path)
    try:
        scalar = lambda query: int(connection.execute(query).fetchone()[0])
        class_group = """
            SELECT 1 FROM schedule_entries e
            JOIN scrape_runs r ON r.id = e.scrape_run_id
            GROUP BY r.academic_year, r.semester, e.course_code,
                     e.index_number, e.class_type, e.group_name
        """
        meeting_group = class_group.replace(
            "e.group_name", "e.group_name, e.day, e.time, e.venue, e.remark"
        )
        meeting_without_remark = class_group.replace(
            "e.group_name", "e.group_name, e.day, e.time, e.venue"
        )
        return ProfileSummary(
            raw_rows=scalar("SELECT COUNT(*) FROM schedule_entries"),
            distinct_courses=scalar("SELECT COUNT(DISTINCT course_code) FROM schedule_entries"),
            programme_selections=scalar("SELECT COUNT(*) FROM programme_selections"),
            distinct_venues=scalar("SELECT COUNT(DISTINCT venue) FROM schedule_entries"),
            distinct_days=scalar("SELECT COUNT(DISTINCT day) FROM schedule_entries"),
            distinct_times=scalar("SELECT COUNT(DISTINCT time) FROM schedule_entries"),
            distinct_remarks=scalar("SELECT COUNT(DISTINCT remark) FROM schedule_entries"),
            blank_days=scalar("SELECT COUNT(*) FROM schedule_entries WHERE trim(day) = ''"),
            blank_times=scalar("SELECT COUNT(*) FROM schedule_entries WHERE trim(time) = ''"),
            blank_venues=scalar("SELECT COUNT(*) FROM schedule_entries WHERE trim(venue) = ''"),
            blank_remarks=scalar("SELECT COUNT(*) FROM schedule_entries WHERE trim(remark) = ''"),
            tentative_canonical_classes=scalar(f"SELECT COUNT(*) FROM ({class_group})"),
            tentative_canonical_meetings=scalar(f"SELECT COUNT(*) FROM ({meeting_group})"),
            meetings_without_remark_in_key=scalar(
                f"SELECT COUNT(*) FROM ({meeting_without_remark})"
            ),
        )
    finally:
        connection.close()


def top_values(path: Path, column: str, limit: int = 20) -> list[tuple[str, int]]:
    allowed = {"day", "time", "venue", "remark"}
    if column not in allowed:
        raise ValueError(f"Unsupported profile column: {column}")
    connection = sqlite3.connect(path)
    try:
        return [
            (str(value), int(count))
            for value, count in connection.execute(
                f"SELECT {column}, COUNT(*) FROM schedule_entries "
                f"GROUP BY {column} ORDER BY COUNT(*) DESC, {column} LIMIT ?",
                (limit,),
            )
        ]
    finally:
        connection.close()
