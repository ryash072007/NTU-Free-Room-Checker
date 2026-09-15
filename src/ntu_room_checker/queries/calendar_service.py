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
    ROOM_TRANSITION_MINUTES,
    EvaluatedMeeting,
    FreeRoom,
    OccupiedInterval,
    RoomMeeting,
    UncertainRoom,
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
    uncertain_intervals: tuple[tuple[int, int], ...] = ()


def coalesce_evaluated_blocks(
    confirmed_intervals: list[tuple[int, int, int]],
    uncertain_intervals: list[tuple[int, int, EvaluatedMeeting]],
    transition_minutes: int = ROOM_TRANSITION_MINUTES,
) -> tuple[list[tuple[int, int, tuple[int, ...]]], list[tuple[int, int, tuple[EvaluatedMeeting, ...]]]]:
    endpoints: set[int] = set()
    for s, e, _ in confirmed_intervals:
        endpoints.add(s)
        endpoints.add(e)
    for s, e, _ in uncertain_intervals:
        endpoints.add(s)
        endpoints.add(e)
    if not endpoints:
        return [], []

    sorted_pts = sorted(endpoints)
    segments: list[dict[str, object]] = []
    for i in range(len(sorted_pts) - 1):
        s = sorted_pts[i]
        e = sorted_pts[i + 1]
        c_matches = [m_id for cs, ce, m_id in confirmed_intervals if cs < e and ce > s]
        u_matches = [item for us, ue, item in uncertain_intervals if us < e and ue > s]
        if c_matches:
            segments.append({
                "start": s, "end": e, "type": "confirmed",
                "meeting_ids": tuple(c_matches), "uncertain_items": (),
            })
        elif u_matches:
            segments.append({
                "start": s, "end": e, "type": "uncertain",
                "meeting_ids": (), "uncertain_items": tuple(u_matches),
            })
        else:
            segments.append({
                "start": s, "end": e, "type": "gap",
                "meeting_ids": (), "uncertain_items": (),
            })

    merged_segments: list[dict[str, object]] = []
    for seg in segments:
        if merged_segments and merged_segments[-1]["type"] == seg["type"]:
            prev = merged_segments[-1]
            prev["end"] = seg["end"]
            prev["meeting_ids"] = tuple(dict.fromkeys(tuple(prev["meeting_ids"]) + tuple(seg["meeting_ids"])))  # type: ignore[arg-type]
            prev["uncertain_items"] = tuple(dict.fromkeys(tuple(prev["uncertain_items"]) + tuple(seg["uncertain_items"])))  # type: ignore[arg-type]
        else:
            merged_segments.append(dict(seg))

    for i, seg in enumerate(merged_segments):
        if seg["type"] == "gap":
            gap_len = int(seg["end"]) - int(seg["start"])  # type: ignore[arg-type]
            if gap_len <= transition_minutes:
                left = merged_segments[i - 1] if i > 0 else None
                right = merged_segments[i + 1] if i + 1 < len(merged_segments) else None
                if left and right:
                    if left["type"] == "confirmed" and right["type"] == "confirmed":
                        seg["type"] = "confirmed"
                        seg["meeting_ids"] = tuple(dict.fromkeys(tuple(left["meeting_ids"]) + tuple(right["meeting_ids"])))  # type: ignore[arg-type]
                    else:
                        seg["type"] = "uncertain"
                        u_items = tuple(left.get("uncertain_items", ())) + tuple(right.get("uncertain_items", ()))  # type: ignore[arg-type]
                        seg["uncertain_items"] = tuple(dict.fromkeys(u_items))

    final_segments: list[dict[str, object]] = []
    for seg in merged_segments:
        if final_segments and final_segments[-1]["type"] == seg["type"]:
            prev = final_segments[-1]
            prev["end"] = seg["end"]
            prev["meeting_ids"] = tuple(dict.fromkeys(tuple(prev["meeting_ids"]) + tuple(seg["meeting_ids"])))  # type: ignore[arg-type]
            prev["uncertain_items"] = tuple(dict.fromkeys(tuple(prev["uncertain_items"]) + tuple(seg["uncertain_items"])))  # type: ignore[arg-type]
        else:
            final_segments.append(dict(seg))

    confirmed_out = [
        (int(seg["start"]), int(seg["end"]), tuple(seg["meeting_ids"]))  # type: ignore[arg-type]
        for seg in final_segments if seg["type"] == "confirmed"
    ]
    uncertain_out = [
        (int(seg["start"]), int(seg["end"]), tuple(seg["uncertain_items"]))  # type: ignore[arg-type]
        for seg in final_segments if seg["type"] == "uncertain"
    ]
    return confirmed_out, uncertain_out


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

    def physical_room_exists_for_date(self, room: str, value: date | str) -> bool | None:
        resolution = self.resolver.resolve(value)
        if resolution.academic_year is None or resolution.semester is None:
            return None
        try:
            return self.queries.physical_room_exists(
                room, resolution.academic_year, resolution.semester
            )
        except ValueError:
            return None

    def physical_room_exists(self, room: str) -> bool:
        return self.queries.physical_room_exists_any(room)

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
            schedules = self.queries.get_room_schedules(
                resolution.academic_year, resolution.semester,
                resolution.day_of_week, teaching_week=resolution.teaching_week,
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
            availability = self._evaluate_room(
                room, resolution, start, end, meetings=schedules.get(room, ())
            )
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
        self, room: str, resolution: DateResolution, start: int, end: int,
        *, meetings: tuple[RoomMeeting, ...] | list[RoomMeeting] | None = None,
    ) -> RoomAvailabilityResult:
        if meetings is None:
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
        raw_confirmed: list[tuple[int, int, int]] = []
        raw_uncertain: list[tuple[int, int, EvaluatedMeeting]] = []
        raw_meeting_intervals: list[tuple[int, int]] = []

        for item in evaluated:
            result = item.applicability
            if result.status == ApplicabilityStatus.APPLICABLE:
                assert result.effective_start is not None and result.effective_end is not None
                raw_confirmed.append((result.effective_start, result.effective_end, item.meeting.meeting_id))
                raw_meeting_intervals.append((result.effective_start, result.effective_end))
            elif result.status == ApplicabilityStatus.UNCERTAIN:
                for c_start, c_end in result.confirmed_intervals:
                    raw_confirmed.append((c_start, c_end, item.meeting.meeting_id))
                    raw_meeting_intervals.append((c_start, c_end))
                for u_start, u_end in result.uncertain_intervals:
                    raw_uncertain.append((u_start, u_end, item))

        coalesced_confirmed, coalesced_uncertain = coalesce_evaluated_blocks(
            raw_confirmed, raw_uncertain, ROOM_TRANSITION_MINUTES
        )

        matching_confirmed = [
            OccupiedInterval(b[0], b[1], b[2])
            for b in coalesced_confirmed
            if overlaps(b[0], b[1], start, end)
        ]

        if matching_confirmed:
            overlaps_class = any(overlaps(ms, me, start, end) for ms, me in raw_meeting_intervals)
            if overlaps_class:
                reason = "At least one applicable timetable meeting overlaps the request."
                codes: tuple[str, ...] = ()
                reasons: tuple[str, ...] = ()
            else:
                reason = "The room is in transition between consecutive classes."
                codes = ("room_transition_buffer",)
                reasons = ("The room is in transition between consecutive classes.",)
            return RoomAvailabilityResult(
                resolution, AvailabilityStatus.OCCUPIED,
                reason,
                room, start, end, False, None, tuple(matching_confirmed),
                uncertainty_reason_codes=codes,
                uncertainty_reasons=reasons,
                evaluated_meetings=evaluated,
            )

        matching_uncertain = [
            b for b in coalesced_uncertain
            if overlaps(b[0], b[1], start, end)
        ]

        if matching_uncertain:
            all_u_items = [u for b in matching_uncertain for u in b[2]]
            codes = tuple(dict.fromkeys(item.applicability.reason_code for item in all_u_items))
            reasons = tuple(dict.fromkeys(item.applicability.reason for item in all_u_items))
            uncertain_intervals = tuple((b[0], b[1]) for b in matching_uncertain)
            return RoomAvailabilityResult(
                resolution, AvailabilityStatus.UNCERTAIN,
                "Meeting applicability is uncertain; the room is not classified as free.",
                room, start, end, None, None,
                uncertainty_reason_codes=codes or ("calendar_exception_uncertain",),
                uncertainty_reasons=reasons or ("Meeting applicability is uncertain; the room is not classified as free.",),
                evaluated_meetings=evaluated,
                uncertain_intervals=uncertain_intervals,
            )

        future_boundaries = [
            b[0] for b in (coalesced_confirmed + coalesced_uncertain)
            if b[0] >= end
        ]
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
