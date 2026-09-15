from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from ntu_room_checker.api.dependencies import CalendarServiceDependency, QueriesDependency
from ntu_room_checker.api.schemas.availability import FreeRoomsResponse, RoomAvailabilityResponse
from ntu_room_checker.api.schemas.common import ErrorResponse
from ntu_room_checker.api.schemas.rooms import RoomItemResponse, RoomListResponse, RoomScheduleResponse
from ntu_room_checker.api.serialization import availability_response, free_rooms_response, schedule_response
from ntu_room_checker.api.validation import local_datetime, parse_api_clock

router = APIRouter(
    prefix="/rooms", tags=["rooms"],
    responses={
        404: {"model": ErrorResponse, "description": "Room or route not found"},
        422: {"model": ErrorResponse, "description": "Invalid request parameters"},
        503: {"model": ErrorResponse, "description": "Timetable database unavailable"},
    },
)
RoomPath = Annotated[str, Path(min_length=1, max_length=100)]


@router.get("", response_model=RoomListResponse, summary="Search normalized physical rooms")
def rooms(
    queries: QueriesDependency,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RoomListResponse:
    matches = queries.search_rooms(q, limit)
    items = [RoomItemResponse(id=item.id, name=item.name) for item in matches]
    return RoomListResponse(rooms=items, count=len(items))


# Static route is intentionally registered before room path parameters.
@router.get("/free", response_model=FreeRoomsResponse, summary="Find confidently free rooms")
def free_rooms(
    service: CalendarServiceDependency,
    date_value: Annotated[date, Query(alias="date")],
    time: Annotated[str, Query(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")],
    duration: Annotated[int, Query(gt=0, le=1440)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 20,
    include_uncertain: bool = False,
) -> FreeRoomsResponse:
    minute = parse_api_clock(time)
    if minute + duration > 24 * 60:
        raise HTTPException(422, detail={
            "code": "validation_error", "message": "requested interval must remain within one day"
        })
    result = service.find_free_rooms_for_datetime(
        local_datetime(date_value, minute), duration, include_uncertain=include_uncertain
    )
    return free_rooms_response(result, limit)


@router.get("/{room}/schedule", response_model=RoomScheduleResponse, summary="Get a room schedule for a date")
def room_schedule(
    room: RoomPath,
    service: CalendarServiceDependency,
    date_value: Annotated[date, Query(alias="date")],
) -> RoomScheduleResponse:
    if not service.physical_room_exists(room):
        raise HTTPException(404, detail={"code": "unknown_room", "message": "Room was not found."})
    result = service.get_room_schedule_for_date(room, date_value)
    return schedule_response(room, result)


@router.get("/{room}/availability", response_model=RoomAvailabilityResponse, summary="Check one room's availability")
def room_availability(
    room: RoomPath,
    service: CalendarServiceDependency,
    date_value: Annotated[date, Query(alias="date")],
    time: Annotated[str, Query(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")],
    duration: Annotated[int, Query(gt=0, le=1440)],
) -> RoomAvailabilityResponse:
    if not service.physical_room_exists(room):
        raise HTTPException(404, detail={"code": "unknown_room", "message": "Room was not found."})
    minute = parse_api_clock(time)
    if minute + duration > 24 * 60:
        raise HTTPException(422, detail={
            "code": "validation_error", "message": "requested interval must remain within one day"
        })
    result = service.get_room_availability_for_datetime(
        room, local_datetime(date_value, minute), duration
    )
    if result.status == "unknown_room":
        raise HTTPException(404, detail={"code": "unknown_room", "message": result.reason})
    return availability_response(result)
