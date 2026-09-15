"""Calendar-aware facade over the existing normalized timetable queries."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ntu_room_checker.calendar import CalendarResolver, default_resolver
from ntu_room_checker.calendar.models import DateResolution
from ntu_room_checker.normalization.venue import normalize_venue
from ntu_room_checker.queries.models import FreeRoom, RoomMeeting
from ntu_room_checker.queries.service import TimetableQueries


@dataclass(frozen=True, slots=True)
class DateScheduleResult:
    calendar: DateResolution
    status: str
    reason: str
    meetings: tuple[RoomMeeting, ...]


@dataclass(frozen=True, slots=True)
class DateFreeRoomsResult:
    calendar: DateResolution
    status: str
    reason: str
    requested_start: int
    requested_end: int
    rooms: tuple[FreeRoom, ...]


@dataclass(frozen=True, slots=True)
class RoomAvailabilityResult:
    calendar: DateResolution
    status: str
    reason: str
    room: str
    requested_start: int
    requested_end: int
    is_free: bool | None
    free_until: int | None


class CalendarTimetableService:
    def __init__(self, db_path: Path, resolver: CalendarResolver | None = None) -> None:
        self.queries = TimetableQueries(db_path)
        self.resolver = resolver or default_resolver()

    def close(self) -> None:
        self.queries.close()

    def __enter__(self) -> "CalendarTimetableService":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _unavailable_reason(resolution: DateResolution) -> str:
        return (
            f"Regular timetable applicability is not established for "
            f"{resolution.period_type.value}; room availability is unknown."
        )

    def get_room_schedule_for_date(self, room: str, value: date | str) -> DateScheduleResult:
        resolution = self.resolver.resolve(value)
        if not resolution.regular_timetable_applicable:
            return DateScheduleResult(
                resolution, "regular_timetable_not_applicable",
                self._unavailable_reason(resolution), (),
            )
        try:
            meetings = self.queries.get_room_schedule(
                room, resolution.academic_year, resolution.semester,
                resolution.day_of_week, teaching_week=resolution.teaching_week,
            )
        except ValueError as error:
            return DateScheduleResult(
                resolution, "normalized_timetable_unavailable", str(error), (),
            )
        if resolution.exceptions:
            return DateScheduleResult(
                resolution,
                "ok_with_calendar_exception",
                "The date has a scoped calendar exception that is not automatically applied to timetable rows.",
                tuple(meetings),
            )
        return DateScheduleResult(resolution, "ok", "", tuple(meetings))

    def find_free_rooms_for_datetime(
        self, value: datetime | str, duration_minutes: int
    ) -> DateFreeRoomsResult:
        instant = datetime.fromisoformat(value) if isinstance(value, str) else value
        resolution = self.resolver.resolve(instant.date())
        start = instant.hour * 60 + instant.minute
        end = start + duration_minutes
        if duration_minutes <= 0 or end > 24 * 60:
            raise ValueError("requested interval must be positive and remain within one day")
        if not resolution.regular_timetable_applicable:
            return DateFreeRoomsResult(
                resolution, "regular_timetable_not_applicable",
                self._unavailable_reason(resolution), start, end, (),
            )
        overlapping_exceptions = tuple(
            item
            for item in resolution.exceptions
            if item.start_minute < end and item.end_minute > start
        )
        if overlapping_exceptions:
            populations = ", ".join(
                sorted({item.affected_population for item in overlapping_exceptions})
            )
            return DateFreeRoomsResult(
                resolution,
                "calendar_exception_unapplied",
                "A calendar no-class exception overlaps the request but cannot be safely "
                f"matched to timetable rows ({populations}); room availability is unknown.",
                start,
                end,
                (),
            )
        try:
            rooms = self.queries.find_free_rooms(
                resolution.academic_year, resolution.semester, resolution.day_of_week,
                start, duration_minutes, teaching_week=resolution.teaching_week,
            )
        except ValueError as error:
            return DateFreeRoomsResult(
                resolution, "normalized_timetable_unavailable", str(error), start, end, (),
            )
        return DateFreeRoomsResult(resolution, "ok", "", start, end, tuple(rooms))

    def get_room_availability_for_datetime(
        self, room: str, value: datetime | str, duration_minutes: int
    ) -> RoomAvailabilityResult:
        free_result = self.find_free_rooms_for_datetime(value, duration_minutes)
        normalized = normalize_venue(room).normalized
        if free_result.status != "ok":
            return RoomAvailabilityResult(
                free_result.calendar, free_result.status, free_result.reason, normalized,
                free_result.requested_start, free_result.requested_end, None, None,
            )
        if not self.queries.physical_room_exists(
            normalized, free_result.calendar.academic_year, free_result.calendar.semester
        ):
            return RoomAvailabilityResult(
                free_result.calendar, "unknown_room",
                "The normalized timetable does not contain this physical room.", normalized,
                free_result.requested_start, free_result.requested_end, None, None,
            )
        match = next(
            (item for item in free_result.rooms if normalize_venue(item.room).normalized == normalized),
            None,
        )
        return RoomAvailabilityResult(
            free_result.calendar, "ok", "", normalized, free_result.requested_start,
            free_result.requested_end, match is not None,
            match.free_until if match else None,
        )
