from fastapi import APIRouter
from pydantic import BaseModel

from ntu_room_checker.api.dependencies import SettingsDependency
from ntu_room_checker.calendar import default_resolver
from ntu_room_checker.queries import TimetableQueries

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    academic_calendar: str


@router.get("/health", response_model=HealthResponse, summary="Check API dependencies")
def health(settings: SettingsDependency) -> HealthResponse:
    database = "available" if TimetableQueries.database_available(settings.database_path) else "unavailable"
    calendar = "available" if default_resolver().calendars else "unavailable"
    status = "ok" if database == calendar == "available" else "degraded"
    return HealthResponse(status=status, database=database, academic_calendar=calendar)

