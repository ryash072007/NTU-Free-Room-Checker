"""SQLite persistence for scrape provenance and raw schedule entries."""

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption, ScheduleEntry


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ScheduleStorage:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "ScheduleStorage":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id INTEGER PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                source_url TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                semester TEXT NOT NULL,
                academic_term_value TEXT NOT NULL,
                academic_term_label TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'partial', 'failed'))
            );
            CREATE TABLE IF NOT EXISTS programme_selections (
                id INTEGER PRIMARY KEY,
                scrape_run_id INTEGER NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
                option_value TEXT NOT NULL,
                option_label TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
                attempts INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                entry_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE (scrape_run_id, option_value)
            );
            CREATE TABLE IF NOT EXISTS schedule_entries (
                id INTEGER PRIMARY KEY,
                scrape_run_id INTEGER NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
                programme_selection_id INTEGER NOT NULL REFERENCES programme_selections(id) ON DELETE CASCADE,
                fingerprint TEXT NOT NULL,
                course_code TEXT NOT NULL,
                course_title TEXT NOT NULL,
                academic_units TEXT NOT NULL,
                course_remark TEXT NOT NULL,
                index_number TEXT NOT NULL,
                class_type TEXT NOT NULL,
                group_name TEXT NOT NULL,
                day TEXT NOT NULL,
                time TEXT NOT NULL,
                venue TEXT NOT NULL,
                remark TEXT NOT NULL,
                raw_data TEXT NOT NULL,
                UNIQUE (scrape_run_id, programme_selection_id, fingerprint)
            );
            CREATE INDEX IF NOT EXISTS idx_schedule_room_lookup
                ON schedule_entries (venue, day, time);
            CREATE INDEX IF NOT EXISTS idx_schedule_course
                ON schedule_entries (course_code);
            """
        )

    def start_run(self, source_url: str, term: AcademicTerm, *, resume: bool) -> int:
        if resume:
            row = self.connection.execute(
                """SELECT id FROM scrape_runs
                   WHERE source_url = ? AND academic_term_value = ?
                     AND status IN ('running', 'partial', 'failed')
                   ORDER BY id DESC LIMIT 1""",
                (source_url, term.value),
            ).fetchone()
            if row:
                self.connection.execute(
                    "UPDATE scrape_runs SET status = 'running', completed_at = NULL WHERE id = ?",
                    (row["id"],),
                )
                self.connection.commit()
                return int(row["id"])
        cursor = self.connection.execute(
            """INSERT INTO scrape_runs
               (started_at, source_url, academic_year, semester,
                academic_term_value, academic_term_label, status)
               VALUES (?, ?, ?, ?, ?, ?, 'running')""",
            (_now(), source_url, term.academic_year, term.semester, term.value, term.label),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def register_programmes(self, run_id: int, programmes: Iterable[ProgrammeOption]) -> None:
        self.connection.executemany(
            """INSERT INTO programme_selections
               (scrape_run_id, option_value, option_label) VALUES (?, ?, ?)
               ON CONFLICT (scrape_run_id, option_value)
               DO UPDATE SET option_label = excluded.option_label""",
            ((run_id, item.value, item.label) for item in programmes),
        )
        self.connection.commit()

    def remaining_programmes(self, run_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """SELECT * FROM programme_selections
                   WHERE scrape_run_id = ? AND status != 'completed' ORDER BY id""",
                (run_id,),
            )
        )

    def mark_selection_running(self, selection_id: int) -> None:
        self.connection.execute(
            """UPDATE programme_selections SET status = 'running', attempts = attempts + 1,
               started_at = COALESCE(started_at, ?), error_message = NULL WHERE id = ?""",
            (_now(), selection_id),
        )
        self.connection.commit()

    @staticmethod
    def fingerprint(entry: ScheduleEntry) -> str:
        values = {
            key: value
            for key, value in vars_for_entry(entry).items()
            if key != "raw_fields"
        }
        encoded = json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def save_entries(
        self, run_id: int, selection_id: int, entries: Iterable[ScheduleEntry]
    ) -> int:
        rows = list(entries)
        with self.connection:
            self.connection.execute(
                "DELETE FROM schedule_entries WHERE programme_selection_id = ?",
                (selection_id,),
            )
            self.connection.executemany(
                """INSERT OR IGNORE INTO schedule_entries
                   (scrape_run_id, programme_selection_id, fingerprint, course_code,
                    course_title, academic_units, course_remark, index_number, class_type,
                    group_name, day, time, venue, remark, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        run_id, selection_id, self.fingerprint(entry), entry.course_code,
                        entry.course_title, entry.academic_units, entry.course_remark,
                        entry.index_number, entry.class_type, entry.group_name, entry.day,
                        entry.time, entry.venue, entry.remark,
                        json.dumps(entry.raw_fields, ensure_ascii=False, sort_keys=True),
                    )
                    for entry in rows
                ),
            )
            count = self.connection.execute(
                "SELECT COUNT(*) FROM schedule_entries WHERE programme_selection_id = ?",
                (selection_id,),
            ).fetchone()[0]
            self.connection.execute(
                """UPDATE programme_selections SET status = 'completed', completed_at = ?,
                   error_message = NULL, entry_count = ? WHERE id = ?""",
                (_now(), count, selection_id),
            )
        return int(count)

    def mark_selection_failed(self, selection_id: int, error: str) -> None:
        self.connection.execute(
            """UPDATE programme_selections SET status = 'failed', completed_at = ?,
               error_message = ? WHERE id = ?""",
            (_now(), error[:4000], selection_id),
        )
        self.connection.commit()

    def finish_run(self, run_id: int) -> str:
        failed = self.connection.execute(
            """SELECT COUNT(*) FROM programme_selections
               WHERE scrape_run_id = ? AND status != 'completed'""",
            (run_id,),
        ).fetchone()[0]
        completed = self.connection.execute(
            """SELECT COUNT(*) FROM programme_selections
               WHERE scrape_run_id = ? AND status = 'completed'""",
            (run_id,),
        ).fetchone()[0]
        status = "completed" if failed == 0 else ("partial" if completed else "failed")
        self.connection.execute(
            "UPDATE scrape_runs SET status = ?, completed_at = ? WHERE id = ?",
            (status, _now(), run_id),
        )
        self.connection.commit()
        return status


def vars_for_entry(entry: ScheduleEntry) -> dict[str, object]:
    return {field: getattr(entry, field) for field in entry.__dataclass_fields__}
