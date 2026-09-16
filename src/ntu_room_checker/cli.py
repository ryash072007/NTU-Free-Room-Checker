"""Command-line entry point."""

import argparse
import json
import logging
from dataclasses import replace
from pathlib import Path

from ntu_room_checker.scraper.browser import browser_page
from ntu_room_checker.normalization.profiling import profile_database, top_values
from ntu_room_checker.normalization.runner import normalize_database
from ntu_room_checker.normalization.statistics import normalization_statistics
from ntu_room_checker.queries import TimetableQueries
from ntu_room_checker.calendar import CalendarPolicyEngine, default_resolver
from ntu_room_checker.queries import CalendarTimetableService
from ntu_room_checker.normalization.time_parser import parse_clock
from ntu_room_checker.scraper.runner import ScrapeConfig, run_scrape
from ntu_room_checker.scraper.schedule_page import ScheduleLandingPage
from ntu_room_checker.api.config import ApiSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ntu-room-checker")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the versioned HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=_positive_int, default=8000)
    serve.add_argument("--db", type=Path)
    serve.add_argument("--static-dir", type=Path, help="Directory containing built static frontend")
    scrape = commands.add_parser(
        "scrape", help="Scrape NTU public class schedules"
    )
    scrape.add_argument("--db", type=Path, default=Path("data/ntu_schedule.db"))
    mode = scrape.add_mutually_exclusive_group()
    mode.add_argument("--headless", action="store_true", default=True)
    mode.add_argument("--headed", action="store_false", dest="headless")
    scrape.add_argument("--programme", help="Exact option value or displayed label")
    scrape.add_argument("--limit", type=_positive_int)
    scrape.add_argument("--resume", action="store_true")
    scrape.add_argument(
        "--academic-term", metavar="YEAR;SEM", help="Page option value, e.g. 2026;1"
    )
    scrape.add_argument("--delay", type=_nonnegative_float, default=1.0)
    scrape.add_argument("--retries", type=_positive_int, default=3)
    scrape.add_argument("--timeout", type=_positive_int, default=60_000, metavar="MS")
    scrape.add_argument("--debug-dir", type=Path)
    scrape.add_argument(
        "--list-programmes", action="store_true", help="Discover options and exit"
    )
    profile = commands.add_parser("profile", help="Profile immutable raw schedule data")
    profile.add_argument("--db", type=Path, default=Path("data/ntu_schedule.db"))
    profile.add_argument("--top", type=_positive_int, default=20)
    normalize = commands.add_parser("normalize", help="Build canonical timetable tables")
    normalize.add_argument("--db", type=Path, default=Path("data/ntu_schedule.db"))
    normalize.add_argument("--source-run", type=_positive_int)
    normalize.add_argument("--rebuild", action="store_true")
    normalize.add_argument("--stats", action="store_true", help="Print resulting counts")
    calendar_date = commands.add_parser("calendar-date", help="Resolve an ISO date")
    calendar_date.add_argument("date")
    calendar_date.add_argument("--verbose", action="store_true", help="Include policy decision")
    room = commands.add_parser("room-schedule", help="Print a normalized room schedule")
    room.add_argument("room")
    _add_query_term_arguments(room)
    room.add_argument("--day")
    room.add_argument("--week", type=_positive_int)
    free = commands.add_parser("free-rooms", help="Find physical rooms free for an interval")
    _add_query_term_arguments(free)
    free.add_argument("--day")
    free.add_argument("--time", required=True, help="HHMM or HH:MM")
    free.add_argument("--duration", required=True, type=_positive_int)
    free.add_argument("--week", type=_positive_int)
    free.add_argument("--limit", type=_positive_int, default=50)
    free.add_argument(
        "--include-uncertain", action="store_true",
        help="Return uncertain rooms separately from confidently free rooms",
    )
    availability = commands.add_parser(
        "room-availability", help="Check one room for a calendar date/time"
    )
    availability.add_argument("room")
    availability.add_argument("--db", type=Path, default=Path("data/ntu_schedule.db"))
    availability.add_argument("--date", required=True)
    availability.add_argument("--time", required=True, help="HHMM or HH:MM")
    availability.add_argument("--duration", required=True, type=_positive_int)
    availability.add_argument(
        "--explain", action="store_true", help="Include per-meeting policy decisions"
    )
    export = commands.add_parser("export-web-data", help="Compile static frontend timetable data")
    export.add_argument("--db", type=Path, default=Path("data/ntu_schedule.db"))
    export.add_argument("--output", type=Path, default=Path("web/public/data"))
    return parser


def _add_query_term_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=Path("data/ntu_schedule.db"))
    parser.add_argument("--date", help="ISO calendar date; replaces AY/semester/day/week")
    parser.add_argument("--academic-year")
    parser.add_argument("--semester")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def _json_result(value: object) -> dict[str, object]:
    from dataclasses import asdict

    return asdict(value)  # type: ignore[arg-type]


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, default=str))


def _require_legacy_query_args(args: argparse.Namespace) -> None:
    missing = [name for name in ("academic_year", "semester", "day") if not getattr(args, name)]
    if missing:
        flags = ", ".join("--" + name.replace("_", "-") for name in missing)
        raise SystemExit(f"Without --date, the following arguments are required: {flags}")


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "serve":
        import uvicorn

        from ntu_room_checker.api.app import create_app

        settings = ApiSettings.from_environment()
        if args.db is not None:
            settings = replace(settings, database_path=args.db)
        if args.static_dir is not None:
            settings = replace(settings, static_dir=args.static_dir)
        uvicorn.run(create_app(settings), host=args.host, port=args.port)
        return
    if args.command == "profile":
        payload = profile_database(args.db).to_dict()
        payload["top_venues"] = top_values(args.db, "venue", args.top)
        payload["top_remarks"] = top_values(args.db, "remark", args.top)
        payload["day_values"] = top_values(args.db, "day", 20)
        payload["time_values"] = top_values(args.db, "time", args.top)
        print(json.dumps(payload, indent=2))
        return
    if args.command == "normalize":
        summary = normalize_database(
            args.db, source_scrape_run_id=args.source_run, rebuild=args.rebuild
        )
        if args.stats:
            from dataclasses import asdict

            payload = asdict(summary)
            payload.update(normalization_statistics(args.db, summary.normalization_run_id))
            print(json.dumps(payload, indent=2))
        return
    if args.command == "calendar-date":
        resolution = default_resolver().resolve(args.date)
        payload = _json_result(resolution)
        if args.verbose:
            payload["policy"] = _json_result(CalendarPolicyEngine().evaluate_date(resolution))
        _print_json(payload)
        return
    if args.command == "room-schedule":
        if args.date:
            with CalendarTimetableService(args.db) as service:
                result = service.get_room_schedule_for_date(args.room, args.date)
            _print_json(_json_result(result))
            return
        _require_legacy_query_args(args)
        with TimetableQueries(args.db) as queries:
            rows = queries.get_room_schedule(
                args.room, args.academic_year, args.semester, args.day,
                teaching_week=args.week,
            )
        print(json.dumps([_json_result(row) for row in rows], indent=2))
        return
    if args.command == "free-rooms":
        if args.date:
            minute = parse_clock(args.time)
            instant = f"{args.date}T{minute // 60:02d}:{minute % 60:02d}"
            with CalendarTimetableService(args.db) as service:
                result = service.find_free_rooms_for_datetime(
                    instant, args.duration, include_uncertain=args.include_uncertain
                )
            payload = _json_result(result)
            payload["rooms"] = list(payload["rooms"])[: args.limit]  # type: ignore[arg-type]
            payload["uncertain_rooms"] = list(payload["uncertain_rooms"])[: args.limit]  # type: ignore[arg-type]
            _print_json(payload)
            return
        _require_legacy_query_args(args)
        with TimetableQueries(args.db) as queries:
            rows = queries.find_free_rooms(
                args.academic_year, args.semester, args.day, args.time, args.duration,
                teaching_week=args.week,
            )[: args.limit]
        print(json.dumps([_json_result(row) for row in rows], indent=2))
        return
    if args.command == "room-availability":
        minute = parse_clock(args.time)
        instant = f"{args.date}T{minute // 60:02d}:{minute % 60:02d}"
        with CalendarTimetableService(args.db) as service:
            result = service.get_room_availability_for_datetime(
                args.room, instant, args.duration
            )
        payload = _json_result(result)
        if not args.explain:
            payload.pop("evaluated_meetings", None)
        _print_json(payload)
        return
    if args.command == "export-web-data":
        from ntu_room_checker.web_export import export_web_data

        _print_json(export_web_data(args.db, args.output))
        return
    if args.list_programmes:
        with browser_page(headless=args.headless) as page:
            landing = ScheduleLandingPage(page, args.timeout)
            landing.load(args.academic_term)
            print(f"# {landing.current_term().label}")
            for programme in landing.programmes():
                print(f"{programme.value}\t{programme.label}")
        return
    run_id, status = run_scrape(
        ScrapeConfig(
            db_path=args.db,
            headless=args.headless,
            programme=args.programme,
            limit=args.limit,
            resume=args.resume,
            academic_term=args.academic_term,
            delay_seconds=args.delay,
            retries=args.retries,
            timeout_ms=args.timeout,
            debug_dir=args.debug_dir,
        )
    )
    print(f"Scrape run {run_id} finished with status: {status}")


if __name__ == "__main__":
    main()
