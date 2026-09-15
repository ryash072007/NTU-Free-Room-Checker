from datetime import date

from fastapi import APIRouter

from ntu_room_checker.api.schemas.calendar import CalendarResponse
from ntu_room_checker.api.serialization import calendar_response
from ntu_room_checker.calendar import default_resolver

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/{value}", response_model=CalendarResponse, summary="Resolve an NTU calendar date")
def resolve_calendar_date(value: date) -> CalendarResponse:
    return calendar_response(default_resolver().resolve(value))

