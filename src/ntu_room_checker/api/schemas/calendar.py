from datetime import date

from pydantic import BaseModel, Field


class CalendarExceptionResponse(BaseModel):
    id: str
    effect: str
    date: date
    start: str | None
    end: str | None
    cutoff: str | None
    affected_population: str
    description: str
    source_note: str


class CalendarResponse(BaseModel):
    date: date
    weekday: str
    academic_year: str | None
    academic_year_start: int | None
    semester: str | None
    period_type: str
    teaching_week: int | None
    regular_timetable_applicable: bool
    is_public_holiday: bool
    holiday: str | None
    holiday_observed: bool
    exceptions: list[CalendarExceptionResponse] = Field(default_factory=list)

