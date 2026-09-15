"""Calendar-policy-aware facade over normalized timetable queries."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from ntu_room_checker.calendar import CalendarPolicyEngine, CalendarResolver, default_resolver
from ntu_room_checker.calendar.models import DateResolution
from ntu_room_checker.calendar.policy import ApplicabilityStatus, DatePolicyResult, TimetableAuthority
from ntu_room_checker.normalization.venue import normalize_venue
from ntu_room_checker.queries.models import (
    EvaluatedMeeting, FreeRoom, OccupiedInterval, RoomMeeting, UncertainRoom,
)
from ntu_room_checker.queries.service import TimetableQueries, overlaps


class AvailabilityStatus(StrEnum):
    FREE = "free"
    OCCUPIED = "occupied"
    UNCERTAIN = "uncertain"
    TIMETABLE_NOT_APPLICABLE = "regular_timetable_not_applicable"
    TIMETABLE_NOT_AUTHORITATIVE = "regular_timetable_not_authoritative"
    TIMETABLE_UNAVAILABLE = "regular_timetable_unavailable"
    NORMALIZED_TIMETABLE_UNAVAILABLE = "normalized_timetable_unavailable"
    UNKNOWN_ROOM = "unknown_room"


@dataclass(frozen=True, slots=True)
class DateScheduleResult:
    calendar: DateResolution
    status: str
    reason: str
    meetings: tuple[RoomMeeting, ...]
    evaluated_meetings: tuple[EvaluatedMeeting, ...] = ()


@dataclass(frozen=True, slots=True)
class DateFreeRoomsResult:
    calendar: DateResolution
    status: str
    reason: str
    requested_start: int
    requested_end: int
    rooms: tuple[FreeRoom, ...]
    uncertain_rooms: tuple[UncertainRoom, ...] = ()


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
    occupied_intervals: tuple[OccupiedInterval, ...] = ()
    uncertainty_reason_codes: tuple[str, ...] = ()
    uncertainty_reasons: tuple[str, ...] = ()
    evaluated_meetings: tuple[EvaluatedMeeting, ...] = ()


class CalendarTimetableService:
    def __init__(self, db_path: Path, resolver: CalendarResolver | None = None,
                 policy: CalendarPolicyEngine | None = None) -> None:
        self.queries = TimetableQueries(db_path)
        self.resolver = resolver or default_resolver()
        self.policy = policy or CalendarPolicyEngine()

    def close(self) -> None:
        self.queries.close()

    def __enter__(self) -> "CalendarTimetableService":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _status_for_date_policy(policy: DatePolicyResult) -> AvailabilityStatus:
        return {
            TimetableAuthority.NOT_APPLICABLE: AvailabilityStatus.TIMETABLE_NOT_APPLICABLE,
            TimetableAuthority.NOT_AUTHORITATIVE: AvailabilityStatus.TIMETABLE_NOT_AUTHORITATIVE,
            TimetableAuthority.UNAVAILABLE: AvailabilityStatus.TIMETABLE_UNAVAILABLE,
        }.get(policy.authority, AvailabilityStatus.FREE)

    def get_room_schedule_for_date(self, room: str, value: date | str) -> DateScheduleResult:
        resolution = self.resolver.resolve(value)
        date_policy = self.policy.evaluate_date(resolution)
        if not resolution.regular_timetable_applicable:
            return DateScheduleResult(
                resolution, self._status_for_date_policy(date_policy), date_policy.reason, (), ()
            )
        try:
            meetings = self.queries.get_room_schedule(
                room, resolution.academic_year, resolution.semester,
                resolution.day_of_week, teaching_week=resolution.teaching_week,
            )
        except ValueError as error:
            return DateScheduleResult(
                resolution, AvailabilityStatus.NORMALIZED_TIMETABLE_UNAVAILABLE,
                str(error), (), (),
            )
        evaluated = tuple(
            EvaluatedMeeting(meeting, self.policy.evaluate_meeting(
                resolution, meeting.start_minute, meeting.end_minute
            ))
            for meeting in meetings
        )
        if any(item.applicability.status == ApplicabilityStatus.UNCERTAIN for item in evaluated):
            return DateScheduleResult(
                resolution, AvailabilityStatus.UNCERTAIN,
                "One or more meetings have uncertain calendar-exception applicability.",
                tuple(meetings), evaluated,
            )
        if any(item.applicability.applied_exceptions for item in evaluated):
            return DateScheduleResult(
                resolution, "ok_with_adjustments",
                "One or more effective meeting intervals were adjusted by calendar policy.",
                tuple(meetings), evaluated,
            )
        return DateScheduleResult(resolution, "ok", "", tuple(meetings), evaluated)

    def find_free_rooms_for_datetime(
        self, value: datetime | str, duration_minutes: int, *, include_uncertain: bool = False
    ) -> DateFreeRoomsResult:
        _, resolution, start, end = self._request_context(value, duration_minutes)
        date_policy = self.policy.evaluate_date(resolution)
        if date_policy.authority != TimetableAuthority.AUTHORITATIVE:
            uncertain: tuple[UncertainRoom, ...] = ()
            if include_uncertain and resolution.academic_year is not None and resolution.semester:
                try:
                    uncertain = tuple(
                        UncertainRoom(room, (date_policy.reason_code,), (date_policy.reason,))
                        for room in self.queries.physical_rooms(
                            resolution.academic_year, resolution.semester
                        )
                    )
                except ValueError:
                    pass
            return DateFreeRoomsResult(
                resolution, self._status_for_date_policy(date_policy), date_policy.reason,
                start, end, (), uncertain,
            )
        try:
            rooms = self.queries.physical_rooms(resolution.academic_year, resolution.semester)
            unparsed = self.queries.rooms_with_unparsed_meetings(
                resolution.academic_year, resolution.semester,
                teaching_week=resolution.teaching_week,
            )
        except ValueError as error:
            return DateFreeRoomsResult(
                resolution, AvailabilityStatus.NORMALIZED_TIMETABLE_UNAVAILABLE,
                str(error), start, end, (), (),
            )
        free: list[FreeRoom] = []
        uncertain_rooms: list[UncertainRoom] = []
        for room in rooms:
            if room in unparsed:
                if include_uncertain:
                    uncertain_rooms.append(UncertainRoom(
                        room, ("unparsed_timetable_meeting",),
                        ("The room has a meeting with an unparsed day or time.",),
                    ))
                continue
            availability = self._evaluate_room(room, resolution, start, end)
            if availability.status == AvailabilityStatus.FREE:
                free.append(FreeRoom(room, start, end, availability.free_until))
            elif availability.status == AvailabilityStatus.UNCERTAIN and include_uncertain:
                uncertain_rooms.append(UncertainRoom(
                    room, availability.uncertainty_reason_codes,
                    availability.uncertainty_reasons,
                ))
        return DateFreeRoomsResult(
            resolution, "ok", "", start, end, tuple(free), tuple(uncertain_rooms)
        )

    def get_room_availability_for_datetime(
        self, room: str, value: datetime | str, duration_minutes: int
    ) -> RoomAvailabilityResult:
        _, resolution, start, end = self._request_context(value, duration_minutes)
        normalized = normalize_venue(room).normalized
        date_policy = self.policy.evaluate_date(resolution)
        if date_policy.authority != TimetableAuthority.AUTHORITATIVE:
            return RoomAvailabilityResult(
                resolution, self._status_for_date_policy(date_policy), date_policy.reason,
                normalized, start, end, None, None,
                uncertainty_reason_codes=(date_policy.reason_code,),
                uncertainty_reasons=(date_policy.reason,),
            )
        try:
            exists = self.queries.physical_room_exists(
                normalized, resolution.academic_year, resolution.semester
            )
        except ValueError as error:
            return RoomAvailabilityResult(
                resolution, AvailabilityStatus.NORMALIZED_TIMETABLE_UNAVAILABLE,
                str(error), normalized, start, end, None, None,
            )
        if not exists:
            return RoomAvailabilityResult(
                resolution, AvailabilityStatus.UNKNOWN_ROOM,
                "The normalized timetable does not contain this physical room.",
                normalized, start, end, None, None,
            )
        unparsed = self.queries.rooms_with_unparsed_meetings(
            resolution.academic_year, resolution.semester,
            teaching_week=resolution.teaching_week,
        )
        if normalized in unparsed:
            reason = "The room has a meeting with an unparsed day or time."
            return RoomAvailabilityResult(
                resolution, AvailabilityStatus.UNCERTAIN, reason,
                normalized, start, end, None, None,
                uncertainty_reason_codes=("unparsed_timetable_meeting",),
                uncertainty_reasons=(reason,),
            )
        return self._evaluate_room(normalized, resolution, start, end)

    def _evaluate_room(
        self, room: str, resolution: DateResolution, start: int, end: int
    ) -> RoomAvailabilityResult:
        meetings = self.queries.get_room_schedule(
            room, resolution.academic_year, resolution.semester,
            resolution.day_of_week, teaching_week=resolution.teaching_week,
        )
        evaluated = tuple(
            EvaluatedMeeting(meeting, self.policy.evaluate_meeting(
                resolution, meeting.start_minute, meeting.end_minute
            ))
            for meeting in meetings
        )
        occupied: list[OccupiedInterval] = []
        uncertainties: list[EvaluatedMeeting] = []
        future_boundaries: list[int] = []
        for item in evaluated:
            result = item.applicability
            if result.status == ApplicabilityStatus.UNCERTAIN:
                confirmed_overlap = tuple(
                    interval for interval in result.confirmed_intervals
                    if overlaps(*interval, start, end)
                )
                if confirmed_overlap:
                    occupied.extend(
                        OccupiedInterval(a, b, (item.meeting.meeting_id,))
                        for a, b in confirmed_overlap
                    )
                    continue
                if any(overlaps(*interval, start, end) for interval in result.uncertain_intervals):
                    uncertainties.append(item)
                future_boundaries.extend(
                    interval[0] for interval in result.confirmed_intervals + result.uncertain_intervals
                    if interval[0] >= end
                )
                continue
            if result.status != ApplicabilityStatus.APPLICABLE:
                continue
            assert result.effective_start is not None and result.effective_end is not None
            if overlaps(result.effective_start, result.effective_end, start, end):
                occupied.append(OccupiedInterval(
                    result.effective_start, result.effective_end, (item.meeting.meeting_id,)
                ))
            elif result.effective_start >= end:
                future_boundaries.append(result.effective_start)
        if occupied:
            return RoomAvailabilityResult(
                resolution, AvailabilityStatus.OCCUPIED,
                "At least one applicable timetable meeting overlaps the request.",
                room, start, end, False, None, tuple(occupied),
                evaluated_meetings=evaluated,
            )
        if uncertainties:
            codes = tuple(dict.fromkeys(item.applicability.reason_code for item in uncertainties))
            reasons = tuple(dict.fromkeys(item.applicability.reason for item in uncertainties))
            return RoomAvailabilityResult(
                resolution, AvailabilityStatus.UNCERTAIN,
                "Meeting applicability is uncertain; the room is not classified as free.",
                room, start, end, None, None,
                uncertainty_reason_codes=codes, uncertainty_reasons=reasons,
                evaluated_meetings=evaluated,
            )
        return RoomAvailabilityResult(
            resolution, AvailabilityStatus.FREE,
            "No applicable or uncertain timetable meeting overlaps the request.",
            room, start, end, True,
            min(future_boundaries) if future_boundaries else None,
            evaluated_meetings=evaluated,
        )

    def _request_context(
        self, value: datetime | str, duration_minutes: int
    ) -> tuple[datetime, DateResolution, int, int]:
        instant = datetime.fromisoformat(value) if isinstance(value, str) else value
        start = instant.hour * 60 + instant.minute
        end = start + duration_minutes
        if duration_minutes <= 0 or end > 24 * 60:
            raise ValueError("requested interval must be positive and remain within one day")
        return instant, self.resolver.resolve(instant.date()), start, end
