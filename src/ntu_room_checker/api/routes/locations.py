from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from ntu_room_checker.api.dependencies import CalendarServiceDependency, QueriesDependency
from ntu_room_checker.api.schemas.common import ErrorResponse
from ntu_room_checker.api.schemas.locations import LocationListResponse, LocationResponse, LocationRoomsResponse
from ntu_room_checker.api.serialization import location_rooms_response
from ntu_room_checker.api.validation import local_datetime, parse_api_clock
from ntu_room_checker.locations import LOCATIONS, get_location, rooms_by_location

router = APIRouter(
    prefix="/locations", tags=["locations"],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)


def _location_response(location, count: int) -> LocationResponse:
    return LocationResponse(
        id=location.id, name=location.name, official_name=location.official_name,
        short_name=location.short_name, aliases=list(location.aliases), room_count=count,
    )


@router.get("", response_model=LocationListResponse, summary="List locations containing known rooms")
def locations(queries: QueriesDependency) -> LocationListResponse:
    grouped = rooms_by_location(queries.latest_physical_rooms())
    return LocationListResponse(locations=[
        _location_response(location, len(grouped[location.id]))
        for location in LOCATIONS if location.id in grouped
    ])


@router.get("/{location_id}/rooms", response_model=LocationRoomsResponse, summary="Browse room status at a location")
def location_rooms(
    location_id: Annotated[str, Path(min_length=1, max_length=80)],
    service: CalendarServiceDependency,
    date_value: Annotated[date, Query(alias="date")],
    time: Annotated[str, Query(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")],
    duration: Annotated[int, Query(gt=0, le=1440)] = 1,
) -> LocationRoomsResponse:
    if get_location(location_id) is None:
        raise HTTPException(404, detail={"code": "unknown_location", "message": "Location was not found."})
    minute = parse_api_clock(time)
    if minute + duration > 24 * 60:
        raise HTTPException(422, detail={"code": "validation_error", "message": "requested interval must remain within one day"})
    result = service.get_location_rooms_for_datetime(
        location_id, local_datetime(date_value, minute), duration
    )
    return location_rooms_response(result, duration)
