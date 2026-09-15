"""Query result values."""

from dataclasses import dataclass

from ntu_room_checker.calendar.policy import MeetingApplicabilityResult

ROOM_TRANSITION_MINUTES: int = 10


@dataclass(frozen=True, slots=True)
class RoomMeeting:
    meeting_id: int
    course_code: str
    course_title: str
    index_number: str
    class_type: str
    group_name: str
    day_of_week: int
    start_minute: int
    end_minute: int
    venue: str
    remark: str
    teaching_weeks: tuple[int, ...]
    week_parse_status: str
    source_count: int


@dataclass(frozen=True, slots=True)
class OccupiedInterval:
    start_minute: int
    end_minute: int
    meeting_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FreeRoom:
    room: str
    requested_start: int
    requested_end: int
    free_until: int | None

    @property
    def free_duration_minutes(self) -> int | None:
        if self.free_until is None:
            return None
        return self.free_until - self.requested_start


@dataclass(frozen=True, slots=True)
class EvaluatedMeeting:
    meeting: RoomMeeting
    applicability: MeetingApplicabilityResult


@dataclass(frozen=True, slots=True)
class UncertainRoom:
    room: str
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoomSummary:
    id: str
    name: str
