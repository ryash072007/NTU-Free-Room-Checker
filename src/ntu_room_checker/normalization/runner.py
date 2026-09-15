"""Build canonical classes, meetings, rooms, weeks, and provenance."""

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ntu_room_checker.normalization.day_parser import parse_day
from ntu_room_checker.normalization.storage import NormalizationStorage, fingerprint
from ntu_room_checker.normalization.time_parser import parse_time
from ntu_room_checker.normalization.venue import normalize_venue
from ntu_room_checker.normalization.weeks import parse_weeks

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NormalizationSummary:
    normalization_run_id: int
    source_scrape_run_id: int
    raw_rows: int
    canonical_classes: int
    canonical_meetings: int
    provenance_links: int
    physical_rooms: int


CLASS_COLUMNS = (
    "academic_year", "semester", "course_code", "course_title", "academic_units",
    "course_remark", "index_number", "class_type", "group_name",
)
CLASS_KEY_COLUMNS = ("academic_year", "semester", "course_code", "index_number", "class_type", "group_name")
MEETING_KEY_COLUMNS = CLASS_KEY_COLUMNS + ("day", "time", "venue", "remark")


def _source_run(connection: sqlite3.Connection, requested: int | None) -> int:
    if requested is not None:
        row = connection.execute(
            "SELECT id FROM scrape_runs WHERE id=? AND status='completed'", (requested,)
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT id FROM scrape_runs WHERE status='completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise ValueError("No completed source scrape run was found")
    return int(row[0])


def normalize_database(
    path: Path, *, source_scrape_run_id: int | None = None, rebuild: bool = False
) -> NormalizationSummary:
    with NormalizationStorage(path) as storage:
        c = storage.connection
        source_run_id = _source_run(c, source_scrape_run_id)
        normalization_run_id, should_build = storage.begin(source_run_id, rebuild=rebuild)
        if not should_build:
            return _summary(c, normalization_run_id, source_run_id)
        try:
            LOGGER.info("Normalizing source scrape run %d", source_run_id)
            class_rows = c.execute(
                """SELECT r.academic_year,r.semester,e.course_code,e.course_title,
                          e.academic_units,e.course_remark,e.index_number,e.class_type,e.group_name
                   FROM schedule_entries e JOIN scrape_runs r ON r.id=e.scrape_run_id
                   WHERE e.scrape_run_id=? GROUP BY r.academic_year,r.semester,e.course_code,
                         e.index_number,e.class_type,e.group_name""",
                (source_run_id,),
            ).fetchall()
            class_ids: dict[tuple[str, ...], int] = {}
            with c:
                for row in class_rows:
                    values = tuple(str(row[column]) for column in CLASS_COLUMNS)
                    key = tuple(str(row[column]) for column in CLASS_KEY_COLUMNS)
                    class_fp = fingerprint(*key)
                    cursor = c.execute(
                        """INSERT INTO canonical_classes
                           (normalization_run_id,academic_year,semester,course_code,course_title,
                            academic_units,course_remark,index_number,class_type,group_name,
                            canonical_fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (normalization_run_id, *values, class_fp),
                    )
                    class_ids[key] = int(cursor.lastrowid)
            LOGGER.info("  %d canonical classes", len(class_ids))

            raw_rows = c.execute(
                """SELECT e.id,r.academic_year,r.semester,e.course_code,e.index_number,
                          e.class_type,e.group_name,e.day,e.time,e.venue,e.remark
                   FROM schedule_entries e JOIN scrape_runs r ON r.id=e.scrape_run_id
                   WHERE e.scrape_run_id=? ORDER BY e.id""",
                (source_run_id,),
            )
            meeting_ids: dict[tuple[str, ...], int] = {}
            provenance: list[tuple[int, int]] = []
            weeks_to_insert: list[tuple[int, int]] = []
            with c:
                for row in raw_rows:
                    key = tuple(str(row[column]) for column in MEETING_KEY_COLUMNS)
                    meeting_id = meeting_ids.get(key)
                    if meeting_id is None:
                        class_key = key[: len(CLASS_KEY_COLUMNS)]
                        day = parse_day(str(row["day"]))
                        time = parse_time(str(row["time"]))
                        venue = normalize_venue(str(row["venue"]))
                        week = parse_weeks(str(row["remark"]))
                        meeting_fp = fingerprint(*key)
                        cursor = c.execute(
                            """INSERT INTO class_meetings
                               (canonical_class_id,day_raw,day_of_week,day_parse_status,
                                time_raw,start_minute,end_minute,time_parse_status,venue_raw,
                                venue_normalized,venue_type,remark_raw,week_expression_raw,
                                week_parse_status,canonical_fingerprint)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                class_ids[class_key], day.raw, day.day_of_week, day.status,
                                time.raw, time.start_minute, time.end_minute, time.status,
                                venue.raw, venue.normalized, venue.venue_type, str(row["remark"]),
                                week.raw, week.status, meeting_fp,
                            ),
                        )
                        meeting_id = int(cursor.lastrowid)
                        meeting_ids[key] = meeting_id
                        weeks_to_insert.extend((meeting_id, number) for number in week.weeks)
                    provenance.append((meeting_id, int(row["id"])))
                    if len(provenance) >= 20_000:
                        c.executemany(
                            "INSERT INTO meeting_source_entries VALUES (?,?)", provenance
                        )
                        provenance.clear()
                if provenance:
                    c.executemany("INSERT INTO meeting_source_entries VALUES (?,?)", provenance)
                c.executemany("INSERT INTO meeting_weeks VALUES (?,?)", weeks_to_insert)

                room_rows = c.execute(
                    """SELECT venue_normalized,MIN(venue_raw),venue_type,
                              json_group_array(DISTINCT venue_raw)
                       FROM class_meetings m JOIN canonical_classes cc ON cc.id=m.canonical_class_id
                       WHERE cc.normalization_run_id=? AND venue_type='physical_room'
                       GROUP BY venue_normalized,venue_type""",
                    (normalization_run_id,),
                ).fetchall()
                for normalized, _raw_display, venue_type, examples in room_rows:
                    cursor = c.execute(
                        """INSERT INTO rooms
                           (normalization_run_id,venue_normalized,venue_display,venue_type,venue_raw_examples)
                           VALUES (?,?,?,?,?)""",
                        (normalization_run_id, normalized, normalized, venue_type, examples),
                    )
                    c.execute(
                        """UPDATE class_meetings SET room_id=? WHERE venue_normalized=?
                           AND id IN (SELECT m.id FROM class_meetings m JOIN canonical_classes cc
                                      ON cc.id=m.canonical_class_id WHERE cc.normalization_run_id=?)""",
                        (cursor.lastrowid, normalized, normalization_run_id),
                    )
            storage.complete(normalization_run_id)
            summary = _summary(c, normalization_run_id, source_run_id)
            LOGGER.info(
                "raw rows %d -> canonical classes %d -> canonical meetings %d -> physical rooms %d",
                summary.raw_rows, summary.canonical_classes, summary.canonical_meetings,
                summary.physical_rooms,
            )
            return summary
        except Exception as error:
            storage.fail(normalization_run_id, repr(error))
            raise


def _summary(c: sqlite3.Connection, run_id: int, source_run_id: int) -> NormalizationSummary:
    scalar = lambda query, args=(): int(c.execute(query, args).fetchone()[0])
    return NormalizationSummary(
        normalization_run_id=run_id,
        source_scrape_run_id=source_run_id,
        raw_rows=scalar("SELECT COUNT(*) FROM schedule_entries WHERE scrape_run_id=?", (source_run_id,)),
        canonical_classes=scalar("SELECT COUNT(*) FROM canonical_classes WHERE normalization_run_id=?", (run_id,)),
        canonical_meetings=scalar("SELECT COUNT(*) FROM class_meetings m JOIN canonical_classes c ON c.id=m.canonical_class_id WHERE c.normalization_run_id=?", (run_id,)),
        provenance_links=scalar("SELECT COUNT(*) FROM meeting_source_entries s JOIN class_meetings m ON m.id=s.meeting_id JOIN canonical_classes c ON c.id=m.canonical_class_id WHERE c.normalization_run_id=?", (run_id,)),
        physical_rooms=scalar("SELECT COUNT(*) FROM rooms WHERE normalization_run_id=?", (run_id,)),
    )
