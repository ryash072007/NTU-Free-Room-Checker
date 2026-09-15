from datetime import date

from pydantic import BaseModel, Field

from ntu_room_checker.api.schemas.calendar import CalendarResponse
from ntu_room_checker.api.schemas.common import TimeIntervalResponse


class RoomAvailabilityResponse(BaseModel):
    room: str
    date: date
    requested_start: str
    requested_end: str
    duration_minutes: int
    status: str = Field(description="Free, occupied, uncertain, or a timetable availability state.")
    is_free: bool | None = Field(description="Null whenever availability is not confidently known.")
    free_until: str | None
    free_duration_minutes: int | None
    occupied_intervals: list[TimeIntervalResponse]
    uncertain_intervals: list[TimeIntervalResponse]
    reason_codes: list[str]
    reasons: list[str]
    calendar: CalendarResponse


class FreeRoomItemResponse(BaseModel):
    room: str
    free_until: str | None
    free_duration_minutes: int | None


class UncertainRoomResponse(BaseModel):
    room: str
    reason_codes: list[str]
    reasons: list[str]


class FreeRoomsResponse(BaseModel):
    date: date
    requested_start: str
    requested_end: str
    duration_minutes: int
    status: str
    reason: str
    calendar: CalendarResponse
    rooms: list[FreeRoomItemResponse]
    uncertain_rooms: list[UncertainRoomResponse]

