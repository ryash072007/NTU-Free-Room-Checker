"""Request-scoped domain-service dependencies."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from ntu_room_checker.api.config import ApiSettings
from ntu_room_checker.queries import CalendarTimetableService, TimetableQueries


def get_settings(request: Request) -> ApiSettings:
    return request.app.state.settings


def get_calendar_service(
    settings: Annotated[ApiSettings, Depends(get_settings)],
) -> Iterator[CalendarTimetableService]:
    if not settings.database_path.is_file():
        raise HTTPException(503, detail={
            "code": "database_unavailable", "message": "Timetable database is unavailable."
        })
    with CalendarTimetableService(settings.database_path) as service:
        yield service


def get_timetable_queries(
    settings: Annotated[ApiSettings, Depends(get_settings)],
) -> Iterator[TimetableQueries]:
    if not settings.database_path.is_file():
        raise HTTPException(503, detail={
            "code": "database_unavailable", "message": "Timetable database is unavailable."
        })
    with TimetableQueries(settings.database_path) as queries:
        yield queries


SettingsDependency = Annotated[ApiSettings, Depends(get_settings)]
CalendarServiceDependency = Annotated[CalendarTimetableService, Depends(get_calendar_service)]
QueriesDependency = Annotated[TimetableQueries, Depends(get_timetable_queries)]
