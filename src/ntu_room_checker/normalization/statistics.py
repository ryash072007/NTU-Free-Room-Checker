"""Coverage statistics for a completed normalization run."""

import sqlite3
from pathlib import Path


def normalization_statistics(path: Path, run_id: int) -> dict[str, object]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        scalar = lambda query, args=(): int(connection.execute(query, args).fetchone()[0])
        meeting_scope = """FROM class_meetings m JOIN canonical_classes c
                           ON c.id=m.canonical_class_id WHERE c.normalization_run_id=?"""

        def grouped(column: str) -> dict[str, int]:
            return {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    f"SELECT m.{column},COUNT(*) {meeting_scope} GROUP BY m.{column}",
                    (run_id,),
                )
            }

        raw_rows = scalar(
            """SELECT COUNT(*) FROM schedule_entries e JOIN normalization_runs n
               ON n.source_scrape_run_id=e.scrape_run_id WHERE n.id=?""",
            (run_id,),
        )
        meetings = scalar(f"SELECT COUNT(*) {meeting_scope}", (run_id,))
        return {
            "raw_rows": raw_rows,
            "canonical_classes": scalar(
                "SELECT COUNT(*) FROM canonical_classes WHERE normalization_run_id=?", (run_id,)
            ),
            "canonical_meetings": meetings,
            "rows_removed_by_provenance_dedup": raw_rows - meetings,
            "dedup_reduction_percent": round((raw_rows - meetings) * 100 / raw_rows, 3),
            "provenance_links": scalar(
                f"SELECT COUNT(*) FROM meeting_source_entries s JOIN class_meetings m ON m.id=s.meeting_id JOIN canonical_classes c ON c.id=m.canonical_class_id WHERE c.normalization_run_id=?",
                (run_id,),
            ),
            "meetings_with_multiple_sources": scalar(
                f"SELECT COUNT(*) FROM (SELECT m.id {meeting_scope} GROUP BY m.id HAVING (SELECT COUNT(*) FROM meeting_source_entries s WHERE s.meeting_id=m.id)>1)",
                (run_id,),
            ),
            "physical_rooms": scalar(
                "SELECT COUNT(*) FROM rooms WHERE normalization_run_id=? AND venue_type='physical_room'",
                (run_id,),
            ),
            "time_parse_status": grouped("time_parse_status"),
            "day_parse_status": grouped("day_parse_status"),
            "venue_types": grouped("venue_type"),
            "week_parse_status": grouped("week_parse_status"),
        }
    finally:
        connection.close()
