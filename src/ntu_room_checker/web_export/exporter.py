"""Compile normalized timetable data and calendar policy into static JSON."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ntu_room_checker.calendar.policy import TimetableAuthority
from ntu_room_checker.locations import LOCATIONS, classify_room, rooms_by_location
from ntu_room_checker.queries import CalendarTimetableService
from ntu_room_checker.queries.calendar_service import DateScheduleResult
from ntu_room_checker.web_export.payloads import calendar_payload, schedule_payload

SCHEMA_VERSION = 1


def _compact_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def _latest_run(db: Path) -> dict[str, Any]:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """SELECT nr.id,nr.source_scrape_run_id,nr.completed_at,
                      sr.academic_year,sr.semester
               FROM normalization_runs nr JOIN scrape_runs sr
                 ON sr.id=nr.source_scrape_run_id
               WHERE nr.status='completed' ORDER BY nr.id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            raise ValueError("No completed normalization snapshot is available")
        result = dict(row)
        result["canonical_meeting_count"] = connection.execute(
            """SELECT count(*) FROM class_meetings m JOIN canonical_classes cc
                 ON cc.id=m.canonical_class_id WHERE cc.normalization_run_id=?""",
            (result["id"],),
        ).fetchone()[0]
        return result
    finally:
        connection.close()


def _fingerprint(db: Path, run: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(f"{db.stat().st_size}:{run['id']}:{run['completed_at']}".encode())
    with db.open("rb") as handle:
        digest.update(handle.read(1024 * 1024))
    return digest.hexdigest()


def _date_range(year: int, semester: str) -> tuple[date, date]:
    if semester == "1":
        return date(year, 8, 10), date(year, 12, 4)
    if semester == "2":
        return date(year + 1, 1, 11), date(year + 1, 5, 7)
    raise ValueError(f"Static export currently supports semesters 1 and 2, not {semester!r}")


def _validate(root: Path, rooms: set[str], dates: list[str]) -> None:
    for day in dates:
        payload = json.loads((root / "days" / f"{day}.json").read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Invalid schema version in {day}")
        day_rooms = payload.get("rooms", {})
        if len(day_rooms) != len(set(day_rooms)) or not set(day_rooms) <= rooms:
            raise ValueError(f"Invalid room references in {day}")
        if not set(payload.get("unparsed_rooms", [])) <= rooms:
            raise ValueError(f"Invalid unparsed room references in {day}")
        for room, value in day_rooms.items():
            for key in ("occupied_blocks", "uncertain_blocks"):
                previous = -1
                for block in value.get(key, []):
                    start, end = block[0], block[1]
                    if not (0 <= start < end <= 1440) or start < previous:
                        raise ValueError(f"Invalid {key} for {room} on {day}")
                    previous = start


def export_web_data(db: Path, output: Path) -> dict[str, Any]:
    """Generate and atomically install a validated static dataset."""
    db = db.resolve()
    output = output.resolve()
    if not db.is_file():
        raise FileNotFoundError(db)
    run = _latest_run(db)
    academic_year = int(run["academic_year"])
    semester = str(run["semester"])
    first, last = _date_range(academic_year, semester)
    generated_at = datetime.now(timezone.utc).isoformat()
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=parent))
    dates: list[str] = []
    meeting_count = 0
    try:
        with CalendarTimetableService(db) as service:
            rooms = service.queries.physical_rooms(academic_year, semester)
            grouped = rooms_by_location(rooms)
            room_items = []
            for room in rooms:
                location = classify_room(room)
                room_items.append({
                    "id": room, "name": room,
                    **({"location_id": location.id, "location_name": location.name} if location else {}),
                })
            _compact_write(temp / "rooms.json", {
                "schema_version": SCHEMA_VERSION, "rooms": room_items,
            })
            _compact_write(temp / "locations.json", {
                "schema_version": SCHEMA_VERSION,
                "locations": [{
                    "id": item.id, "name": item.name, "official_name": item.official_name,
                    "short_name": item.short_name, "aliases": list(item.aliases),
                    "room_count": len(grouped.get(item.id, [])),
                    "rooms": grouped.get(item.id, []),
                } for item in LOCATIONS],
            })

            current = first
            while current <= last:
                resolution = service.resolver.resolve(current)
                policy = service.policy.evaluate_date(resolution)
                day_rooms: dict[str, Any] = {}
                unparsed: list[str] = []
                if policy.authority == TimetableAuthority.AUTHORITATIVE:
                    schedules = service.queries.get_room_schedules(
                        academic_year, semester, resolution.day_of_week,
                        teaching_week=resolution.teaching_week,
                    )
                    unparsed = sorted(service.queries.rooms_with_unparsed_meetings(
                        academic_year, semester, teaching_week=resolution.teaching_week,
                    ))
                    for room, meetings in schedules.items():
                        evaluated = service._evaluate_room(room, resolution, 0, 1, meetings=meetings).evaluated_meetings
                        has_uncertain = any(item.applicability.status.value == "uncertain" for item in evaluated)
                        has_adjustments = any(item.applicability.applied_exceptions for item in evaluated)
                        schedule_status = "uncertain" if has_uncertain else "ok_with_adjustments" if has_adjustments else "ok"
                        schedule_reason = "One or more meetings have uncertain calendar-exception applicability." if has_uncertain else "One or more effective meeting intervals were adjusted by calendar policy." if has_adjustments else ""
                        schedule = schedule_payload(room, DateScheduleResult(
                            resolution, schedule_status, schedule_reason, tuple(meetings), evaluated,
                        ))
                        # _evaluate_room exposes coalesced blocks only for matching requests;
                        # compile all blocks by probing their boundaries conservatively.
                        occupied_blocks: list[list[int]] = []
                        uncertain_blocks: list[list[Any]] = []
                        from ntu_room_checker.queries.calendar_service import coalesce_evaluated_blocks
                        raw_c, raw_u = [], []
                        for evaluated_item in evaluated:
                            decision = evaluated_item.applicability
                            if decision.status.value == "applicable":
                                raw_c.append((decision.effective_start, decision.effective_end, evaluated_item.meeting.meeting_id))
                            elif decision.status.value == "uncertain":
                                raw_c.extend((s, e, evaluated_item.meeting.meeting_id) for s, e in decision.confirmed_intervals)
                                raw_u.extend((s, e, evaluated_item) for s, e in decision.uncertain_intervals)
                        coalesced_c, coalesced_u = coalesce_evaluated_blocks(raw_c, raw_u)
                        occupied_blocks = [[s, e, list(ids)] for s, e, ids in coalesced_c]
                        uncertain_blocks = [[s, e,
                            list(dict.fromkeys(x.applicability.reason_code for x in items)),
                            list(dict.fromkeys(x.applicability.reason for x in items))]
                            for s, e, items in coalesced_u]
                        day_rooms[room] = {
                            "status": schedule_status, "reason": schedule_reason,
                            "schedule": schedule["meetings"],
                            "occupied_blocks": occupied_blocks,
                            "uncertain_blocks": uncertain_blocks,
                        }
                        meeting_count += len(meetings)
                day_status = service._status_for_date_policy(policy) if policy.authority != TimetableAuthority.AUTHORITATIVE else "ok"
                day = current.isoformat()
                dates.append(day)
                _compact_write(temp / "days" / f"{day}.json", {
                    "schema_version": SCHEMA_VERSION, "date": day,
                    "status": day_status, "reason": policy.reason if day_status != "ok" else "",
                    "reason_code": policy.reason_code if day_status != "ok" else "",
                    "calendar": calendar_payload(resolution), "rooms": day_rooms,
                    "unparsed_rooms": unparsed,
                })
                current += timedelta(days=1)

        manifest = {
            "schema_version": SCHEMA_VERSION, "data_format_version": "1",
            "academic_year": f"AY{academic_year}-{str(academic_year + 1)[-2:]}",
            "academic_year_start": academic_year, "semester": semester,
            "generated_at": generated_at, "source_db_fingerprint": _fingerprint(db, run),
            "normalization_run_id": run["id"], "first_supported_date": dates[0],
            "last_supported_date": dates[-1], "supported_dates": dates,
            "room_count": len(rooms), "canonical_meeting_count": run["canonical_meeting_count"],
        }
        _compact_write(temp / "manifest.json", manifest)
        _validate(temp, set(rooms), dates)
        backup = output.with_name(f".{output.name}-previous")
        if backup.exists():
            shutil.rmtree(backup)
        if output.exists():
            output.replace(backup)
        try:
            temp.replace(output)
        except Exception:
            if backup.exists() and not output.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        sizes = [path.stat().st_size for path in (output / "days").glob("*.json")]
        return {**manifest, "generated_file_count": len(sizes) + 3,
                "raw_bytes": sum(p.stat().st_size for p in output.rglob("*.json")),
                "median_daily_bytes": sorted(sizes)[len(sizes) // 2],
                "largest_daily_bytes": max(sizes)}
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
