"""Explicit adapters from domain dataclasses to public Pydantic schemas."""

from ntu_room_checker.api.schemas.availability import (
    FreeRoomItemResponse, FreeRoomsResponse, RoomAvailabilityResponse, UncertainRoomResponse,
)
from ntu_room_checker.api.schemas.calendar import CalendarExceptionResponse, CalendarResponse
from ntu_room_checker.api.schemas.common import TimeIntervalResponse
from ntu_room_checker.api.schemas.rooms import MeetingResponse, RoomScheduleResponse
from ntu_room_checker.api.time import minute_to_clock
from ntu_room_checker.calendar.models import DateResolution
from ntu_room_checker.calendar.policy import ApplicabilityStatus
from ntu_room_checker.normalization.venue import normalize_venue
from ntu_room_checker.queries.calendar_service import (
    DateFreeRoomsResult, DateScheduleResult, RoomAvailabilityResult,
)
from ntu_room_checker.queries.service import overlaps


def calendar_response(value: DateResolution) -> CalendarResponse:
    return CalendarResponse(
        date=value.date,
        weekday=value.weekday,
        academic_year=value.academic_year_label,
        academic_year_start=value.academic_year,
        semester=value.semester,
        period_type=value.period_type.value,
        teaching_week=value.teaching_week,
        regular_timetable_applicable=value.regular_timetable_applicable,
        is_public_holiday=value.is_public_holiday,
        holiday=value.holiday_name,
        holiday_observed=value.holiday_observed,
        exceptions=[
            CalendarExceptionResponse(
                id=item.exception_id,
                effect=item.effect.value,
                date=item.date,
                start=minute_to_clock(item.start_minute),
                end=minute_to_clock(item.end_minute),
                cutoff=minute_to_clock(item.cutoff_minute),
                affected_population=item.affected_population.value,
                description=item.description,
                source_note=item.source_note,
            )
            for item in value.exceptions
        ],
    )


def _interval(value: tuple[int, int]) -> TimeIntervalResponse:
    return TimeIntervalResponse(start=minute_to_clock(value[0]), end=minute_to_clock(value[1]))  # type: ignore[arg-type]


def schedule_response(room: str, result: DateScheduleResult) -> RoomScheduleResponse:
    meetings: list[MeetingResponse] = []
    for item in result.evaluated_meetings:
        meeting = item.meeting
        decision = item.applicability
        meetings.append(MeetingResponse(
            course_code=meeting.course_code,
            course_title=meeting.course_title,
            index_number=meeting.index_number,
            class_type=meeting.class_type,
            group=meeting.group_name,
            scheduled_start=minute_to_clock(decision.scheduled_start),  # type: ignore[arg-type]
            scheduled_end=minute_to_clock(decision.scheduled_end),  # type: ignore[arg-type]
            effective_start=minute_to_clock(decision.effective_start),
            effective_end=minute_to_clock(decision.effective_end),
            applicability=decision.status.value,
            remark=meeting.remark,
            teaching_weeks=list(meeting.teaching_weeks),
            confirmed_intervals=[_interval(value) for value in decision.confirmed_intervals],
            uncertain_intervals=[_interval(value) for value in decision.uncertain_intervals],
            reason_codes=[] if decision.reason_code == "regular_timetable_meeting" else [decision.reason_code],
            reasons=[] if decision.reason_code == "regular_timetable_meeting" else [decision.reason],
        ))
    return RoomScheduleResponse(
        room=normalize_venue(room).normalized,
        date=result.calendar.date,
        calendar=calendar_response(result.calendar),
        status=result.status,
        reason=result.reason,
        meetings=meetings,
    )


def availability_response(result: RoomAvailabilityResult) -> RoomAvailabilityResponse:
    uncertain_intervals = [
        interval
        for item in result.evaluated_meetings
        if item.applicability.status == ApplicabilityStatus.UNCERTAIN
        for interval in item.applicability.uncertain_intervals
        if overlaps(*interval, result.requested_start, result.requested_end)
    ]
    return RoomAvailabilityResponse(
        room=result.room,
        date=result.calendar.date,
        requested_start=minute_to_clock(result.requested_start),  # type: ignore[arg-type]
        requested_end=minute_to_clock(result.requested_end),  # type: ignore[arg-type]
        duration_minutes=result.requested_end - result.requested_start,
        status=result.status,
        is_free=result.is_free,
        free_until=minute_to_clock(result.free_until),
        free_duration_minutes=(
            result.free_until - result.requested_start if result.free_until is not None else None
        ),
        occupied_intervals=[
            _interval((item.start_minute, item.end_minute)) for item in result.occupied_intervals
        ],
        uncertain_intervals=[_interval(value) for value in uncertain_intervals],
        reason_codes=list(result.uncertainty_reason_codes),
        reasons=list(result.uncertainty_reasons) or ([result.reason] if result.reason else []),
        calendar=calendar_response(result.calendar),
    )


def free_rooms_response(result: DateFreeRoomsResult, limit: int) -> FreeRoomsResponse:
    return FreeRoomsResponse(
        date=result.calendar.date,
        requested_start=minute_to_clock(result.requested_start),  # type: ignore[arg-type]
        requested_end=minute_to_clock(result.requested_end),  # type: ignore[arg-type]
        duration_minutes=result.requested_end - result.requested_start,
        status=result.status,
        reason=result.reason,
        calendar=calendar_response(result.calendar),
        rooms=[
            FreeRoomItemResponse(
                room=item.room,
                free_until=minute_to_clock(item.free_until),
                free_duration_minutes=item.free_duration_minutes,
            )
            for item in result.rooms[:limit]
        ],
        uncertain_rooms=[
            UncertainRoomResponse(
                room=item.room, reason_codes=list(item.reason_codes), reasons=list(item.reasons)
            )
            for item in result.uncertain_rooms[:limit]
        ],
    )
