"""Fast canonical-table queries with conservative uncertainty semantics."""

import sqlite3
from pathlib import Path

from ntu_room_checker.normalization.day_parser import day_number
from ntu_room_checker.normalization.time_parser import parse_clock
from ntu_room_checker.normalization.venue import normalize_venue
from ntu_room_checker.queries.models import FreeRoom, OccupiedInterval, RoomMeeting


def overlaps(start: int, end: int, requested_start: int, requested_end: int) -> bool:
    return start < requested_end and end > requested_start


class TimetableQueries:
    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "TimetableQueries":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _normalization_run(self, academic_year: str | int, semester: str | int) -> int:
        row = self.connection.execute(
            """SELECT nr.id FROM normalization_runs nr
               JOIN scrape_runs sr ON sr.id=nr.source_scrape_run_id
               WHERE nr.status='completed' AND sr.academic_year=? AND sr.semester=?
               ORDER BY nr.id DESC LIMIT 1""",
            (str(academic_year), str(semester)),
        ).fetchone()
        if row is None:
            raise ValueError(f"No normalized data for AY {academic_year} semester {semester}")
        return int(row[0])

    def physical_room_exists(
        self, room: str, academic_year: str | int, semester: str | int
    ) -> bool:
        run_id = self._normalization_run(academic_year, semester)
        normalized = normalize_venue(room).normalized
        return self.connection.execute(
            """SELECT 1 FROM rooms WHERE normalization_run_id=?
               AND venue_normalized=? AND venue_type='physical_room'""",
            (run_id, normalized),
        ).fetchone() is not None

    def physical_rooms(
        self, academic_year: str | int, semester: str | int
    ) -> list[str]:
        run_id = self._normalization_run(academic_year, semester)
        return [
            str(row[0])
            for row in self.connection.execute(
                """SELECT venue_display FROM rooms
                   WHERE normalization_run_id=? AND venue_type='physical_room'
                   ORDER BY venue_display""",
                (run_id,),
            )
        ]

    def rooms_with_unparsed_meetings(
        self, academic_year: str | int, semester: str | int,
        *, teaching_week: int | None = None,
    ) -> set[str]:
        run_id = self._normalization_run(academic_year, semester)
        week_sql, week_args = self._week_sql(teaching_week)
        return {
            str(row[0])
            for row in self.connection.execute(
                f"""SELECT DISTINCT r.venue_display FROM rooms r
                    JOIN class_meetings m ON m.room_id=r.id
                    JOIN canonical_classes cc ON cc.id=m.canonical_class_id
                    WHERE r.normalization_run_id=? AND r.venue_type='physical_room'
                      AND cc.normalization_run_id=?
                      AND (m.day_parse_status!='parsed' OR m.time_parse_status!='parsed')
                      AND {week_sql}""",
                (run_id, run_id, *week_args),
            )
        }

    @staticmethod
    def _week_sql(teaching_week: int | None, alias: str = "m") -> tuple[str, tuple[int, ...]]:
        if teaching_week is None:
            return "1=1", ()
        if not 1 <= teaching_week <= 13:
            raise ValueError("teaching_week must be between 1 and 13")
        # Unknown applicability blocks availability conservatively. Only explicit
        # not-during-teaching-weeks records are excluded from teaching-week queries.
        return (
            f"({alias}.week_parse_status NOT IN ('parsed','not_during_teaching_weeks') "
            f"OR EXISTS (SELECT 1 FROM meeting_weeks mw WHERE mw.meeting_id={alias}.id "
            f"AND mw.teaching_week=?))",
            (teaching_week,),
        )

    def get_room_schedule(
        self,
        room: str,
        academic_year: str | int,
        semester: str | int,
        day_of_week: str | int,
        *,
        teaching_week: int | None = None,
    ) -> list[RoomMeeting]:
        run_id = self._normalization_run(academic_year, semester)
        normalized = normalize_venue(room).normalized
        day = day_number(day_of_week)
        week_sql, week_args = self._week_sql(teaching_week)
        rows = self.connection.execute(
            f"""SELECT m.id,cc.course_code,cc.course_title,cc.index_number,cc.class_type,
                       cc.group_name,m.day_of_week,m.start_minute,m.end_minute,
                       m.venue_normalized,m.remark_raw,m.week_parse_status,
                       (SELECT group_concat(teaching_week, ',') FROM
                          (SELECT teaching_week FROM meeting_weeks
                           WHERE meeting_id=m.id ORDER BY teaching_week)) week_numbers,
                       (SELECT COUNT(*) FROM meeting_source_entries WHERE meeting_id=m.id) source_count
                FROM class_meetings m JOIN canonical_classes cc ON cc.id=m.canonical_class_id
                WHERE cc.normalization_run_id=? AND m.venue_normalized=?
                  AND m.day_of_week=? AND m.time_parse_status='parsed' AND {week_sql}
                ORDER BY m.start_minute,m.end_minute,cc.course_code,cc.index_number,m.id""",
            (run_id, normalized, day, *week_args),
        ).fetchall()
        return [self._meeting(row) for row in rows]

    @staticmethod
    def _meeting(row: sqlite3.Row) -> RoomMeeting:
        weeks = tuple(int(value) for value in (row["week_numbers"] or "").split(",") if value)
        return RoomMeeting(
            int(row["id"]), row["course_code"], row["course_title"], row["index_number"],
            row["class_type"], row["group_name"], int(row["day_of_week"]),
            int(row["start_minute"]), int(row["end_minute"]), row["venue_normalized"],
            row["remark_raw"], weeks, row["week_parse_status"], int(row["source_count"]),
        )

    def occupied_intervals(self, *args: object, **kwargs: object) -> list[OccupiedInterval]:
        meetings = self.get_room_schedule(*args, **kwargs)
        merged: list[OccupiedInterval] = []
        for meeting in meetings:
            if merged and meeting.start_minute < merged[-1].end_minute:
                previous = merged[-1]
                merged[-1] = OccupiedInterval(
                    previous.start_minute,
                    max(previous.end_minute, meeting.end_minute),
                    previous.meeting_ids + (meeting.meeting_id,),
                )
            else:
                merged.append(
                    OccupiedInterval(meeting.start_minute, meeting.end_minute, (meeting.meeting_id,))
                )
        return merged

    def find_free_rooms(
        self,
        academic_year: str | int,
        semester: str | int,
        day_of_week: str | int,
        start_time: str | int,
        duration_minutes: int,
        *,
        teaching_week: int | None = None,
    ) -> list[FreeRoom]:
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        start = parse_clock(start_time) if isinstance(start_time, str) else start_time
        end = start + duration_minutes
        if not 0 <= start < end <= 24 * 60:
            raise ValueError("requested interval must fall within one day")
        run_id = self._normalization_run(academic_year, semester)
        day = day_number(day_of_week)
        week_sql, week_args = self._week_sql(teaching_week, "m")
        # Any physical meeting with an unknown day or time disqualifies its room.
        # This errs toward false occupancy, never false availability.
        rows = self.connection.execute(
            f"""SELECT r.id,r.venue_display FROM rooms r
                WHERE r.normalization_run_id=? AND r.venue_type='physical_room'
                  AND NOT EXISTS (
                    SELECT 1 FROM class_meetings m JOIN canonical_classes cc
                      ON cc.id=m.canonical_class_id
                    WHERE m.room_id=r.id AND cc.normalization_run_id=?
                      AND (m.day_parse_status!='parsed' OR m.time_parse_status!='parsed')
                      AND {week_sql}
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM class_meetings m JOIN canonical_classes cc
                      ON cc.id=m.canonical_class_id
                    WHERE m.room_id=r.id AND cc.normalization_run_id=?
                      AND m.day_of_week=? AND m.start_minute<? AND m.end_minute>?
                      AND {week_sql}
                  )
                ORDER BY r.venue_display""",
            (run_id, run_id, *week_args, run_id, day, end, start, *week_args),
        ).fetchall()
        results: list[FreeRoom] = []
        for row in rows:
            next_start = self.connection.execute(
                f"""SELECT MIN(m.start_minute) FROM class_meetings m
                    JOIN canonical_classes cc ON cc.id=m.canonical_class_id
                    WHERE m.room_id=? AND cc.normalization_run_id=? AND m.day_of_week=?
                      AND m.time_parse_status='parsed' AND m.start_minute>=? AND {week_sql}""",
                (row["id"], run_id, day, end, *week_args),
            ).fetchone()[0]
            results.append(FreeRoom(row["venue_display"], start, end, next_start))
        return results
