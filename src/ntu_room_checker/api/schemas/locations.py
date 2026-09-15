from datetime import date

from pydantic import BaseModel, Field

from .calendar import CalendarResponse


class LocationResponse(BaseModel):
    id: str
    name: str
    official_name: str | None
    short_name: str
    aliases: list[str] = Field(default_factory=list)
    room_count: int


class LocationListResponse(BaseModel):
    locations: list[LocationResponse]


class LocationRoomResponse(BaseModel):
    room: str
    status: str
    is_free: bool | None
    free_until: str | None
    free_duration_minutes: int | None
    available_from: str | None
    reason_codes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class LocationRoomsResponse(BaseModel):
    location: LocationResponse
    date: date
    requested_time: str
    duration_minutes: int
    status: str
    reason: str
    calendar: CalendarResponse
    rooms: list[LocationRoomResponse]
