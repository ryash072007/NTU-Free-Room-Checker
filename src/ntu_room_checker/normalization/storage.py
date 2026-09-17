"""Derived canonical timetable schema and idempotent persistence."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def fingerprint(*values: object) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat()


class NormalizationStorage:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "NormalizationStorage":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS normalization_runs (
                id INTEGER PRIMARY KEY,
                source_scrape_run_id INTEGER NOT NULL REFERENCES scrape_runs(id),
                schema_version INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL CHECK (status IN ('running','completed','failed')),
                error_message TEXT,
                UNIQUE (source_scrape_run_id, schema_version)
            );
            CREATE TABLE IF NOT EXISTS canonical_classes (
                id INTEGER PRIMARY KEY,
                normalization_run_id INTEGER NOT NULL REFERENCES normalization_runs(id) ON DELETE CASCADE,
                academic_year TEXT NOT NULL,
                semester TEXT NOT NULL,
                course_code TEXT NOT NULL,
                course_title TEXT NOT NULL,
                academic_units TEXT NOT NULL,
                course_remark TEXT NOT NULL,
                index_number TEXT NOT NULL,
                class_type TEXT NOT NULL,
                group_name TEXT NOT NULL,
                canonical_fingerprint TEXT NOT NULL,
                UNIQUE (normalization_run_id, canonical_fingerprint)
            );
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY,
                normalization_run_id INTEGER NOT NULL REFERENCES normalization_runs(id) ON DELETE CASCADE,
                venue_normalized TEXT NOT NULL,
                venue_display TEXT NOT NULL,
                venue_type TEXT NOT NULL,
                venue_raw_examples TEXT NOT NULL,
                UNIQUE (normalization_run_id, venue_normalized)
            );
            CREATE TABLE IF NOT EXISTS class_meetings (
                id INTEGER PRIMARY KEY,
                canonical_class_id INTEGER NOT NULL REFERENCES canonical_classes(id) ON DELETE CASCADE,
                room_id INTEGER REFERENCES rooms(id),
                day_raw TEXT NOT NULL,
                day_of_week INTEGER,
                day_parse_status TEXT NOT NULL,
                time_raw TEXT NOT NULL,
                start_minute INTEGER,
                end_minute INTEGER,
                time_parse_status TEXT NOT NULL,
                venue_raw TEXT NOT NULL,
                venue_normalized TEXT NOT NULL,
                venue_type TEXT NOT NULL,
                remark_raw TEXT NOT NULL,
                week_expression_raw TEXT NOT NULL,
                week_parse_status TEXT NOT NULL,
                canonical_fingerprint TEXT NOT NULL,
                UNIQUE (canonical_class_id, canonical_fingerprint)
            );
            CREATE TABLE IF NOT EXISTS meeting_weeks (
                meeting_id INTEGER NOT NULL REFERENCES class_meetings(id) ON DELETE CASCADE,
                teaching_week INTEGER NOT NULL CHECK (teaching_week BETWEEN 1 AND 13),
                PRIMARY KEY (meeting_id, teaching_week)
            );
            CREATE TABLE IF NOT EXISTS meeting_source_entries (
                meeting_id INTEGER NOT NULL REFERENCES class_meetings(id) ON DELETE CASCADE,
                raw_schedule_entry_id INTEGER NOT NULL REFERENCES schedule_entries(id),
                PRIMARY KEY (meeting_id, raw_schedule_entry_id)
            );
            CREATE INDEX IF NOT EXISTS idx_classes_term
                ON canonical_classes (normalization_run_id, academic_year, semester);
            CREATE INDEX IF NOT EXISTS idx_meetings_room_day_time
                ON class_meetings (room_id, day_of_week, start_minute, end_minute);
            CREATE INDEX IF NOT EXISTS idx_meetings_venue_day_time
                ON class_meetings (venue_normalized, day_of_week, start_minute, end_minute);
            CREATE INDEX IF NOT EXISTS idx_meeting_weeks_week
                ON meeting_weeks (teaching_week, meeting_id);
            CREATE INDEX IF NOT EXISTS idx_sources_raw
                ON meeting_source_entries (raw_schedule_entry_id);
            """
        )
        self._ensure_room_facility_columns()

    def _ensure_room_facility_columns(self) -> None:
        # Added alongside the facility-list capacity join; a plain
        # CREATE TABLE IF NOT EXISTS above would not add these to a rooms
        # table created before this change, so migrate it explicitly.
        existing = {row["name"] for row in self.connection.execute("PRAGMA table_info(rooms)")}
        additions = ("capacity", "bookable_by_staff", "bookable_by_student_orgs")
        for column in additions:
            if column not in existing:
                self.connection.execute(f"ALTER TABLE rooms ADD COLUMN {column} INTEGER")
        self.connection.commit()

    def begin(self, source_run_id: int, *, rebuild: bool) -> tuple[int, bool]:
        existing = self.connection.execute(
            "SELECT id, status FROM normalization_runs WHERE source_scrape_run_id=? AND schema_version=?",
            (source_run_id, self.SCHEMA_VERSION),
        ).fetchone()
        if existing and existing["status"] == "completed" and not rebuild:
            return int(existing["id"]), False
        with self.connection:
            if existing:
                self.connection.execute("DELETE FROM normalization_runs WHERE id=?", (existing["id"],))
            cursor = self.connection.execute(
                """INSERT INTO normalization_runs
                   (source_scrape_run_id,schema_version,started_at,status)
                   VALUES (?,?,?,'running')""",
                (source_run_id, self.SCHEMA_VERSION, now()),
            )
        return int(cursor.lastrowid), True

    def complete(self, run_id: int) -> None:
        self.connection.execute(
            "UPDATE normalization_runs SET status='completed',completed_at=?,error_message=NULL WHERE id=?",
            (now(), run_id),
        )
        self.connection.commit()

    def fail(self, run_id: int, error: str) -> None:
        self.connection.execute(
            "UPDATE normalization_runs SET status='failed',completed_at=?,error_message=? WHERE id=?",
            (now(), error[:4000], run_id),
        )
        self.connection.commit()
