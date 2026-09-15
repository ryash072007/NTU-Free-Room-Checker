from datetime import date

from pydantic import BaseModel, Field

from ntu_room_checker.api.schemas.calendar import CalendarResponse
from ntu_room_checker.api.schemas.common import TimeIntervalResponse


class RoomItemResponse(BaseModel):
    id: str
    name: str


class RoomListResponse(BaseModel):
    rooms: list[RoomItemResponse]
    count: int


class MeetingResponse(BaseModel):
    course_code: str
    course_title: str
    index_number: str
    class_type: str
    group: str
    scheduled_start: str
    scheduled_end: str
    effective_start: str | None
    effective_end: str | None
    applicability: str
    remark: str
    teaching_weeks: list[int]
    confirmed_intervals: list[TimeIntervalResponse] = Field(default_factory=list)
    uncertain_intervals: list[TimeIntervalResponse] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class RoomScheduleResponse(BaseModel):
    room: str
    date: date
    calendar: CalendarResponse
    status: str
    reason: str
    meetings: list[MeetingResponse]

