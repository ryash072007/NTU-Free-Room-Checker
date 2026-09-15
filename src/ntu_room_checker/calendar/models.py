"""Auditable academic calendar domain values."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class PeriodType(StrEnum):
    TEACHING_WEEK = "teaching_week"
    RECESS_WEEK = "recess_week"
    REVISION_EXAM = "revision_exam"
    ORIENTATION = "orientation"
    SPECIAL_TERM = "special_term"
    OUTSIDE_TERM = "outside_term"


@dataclass(frozen=True, slots=True)
class CalendarPeriod:
    start: date
    end: date
    period_type: PeriodType
    semester: str
    teaching_week: int | None = None
    regular_timetable_applicable: bool = False
    source_note: str = ""

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("calendar period start must not follow its end")
        if self.teaching_week is not None and not 1 <= self.teaching_week <= 13:
            raise ValueError("teaching week must be between 1 and 13")

    def contains(self, value: date) -> bool:
        return self.start <= value <= self.end


@dataclass(frozen=True, slots=True)
class PublicHoliday:
    date: date
    name: str
    observed: bool = False
    source_note: str = ""


@dataclass(frozen=True, slots=True)
class CalendarException:
    date: date
    start_minute: int
    end_minute: int
    affected_population: str
    description: str
    source_note: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.start_minute < self.end_minute <= 24 * 60:
            raise ValueError("calendar exception must be a valid within-day interval")


@dataclass(frozen=True, slots=True)
class EarlyDismissalPolicy:
    end_minute: int
    holiday_names: tuple[str, ...]
    description: str
    source_note: str = ""


@dataclass(frozen=True, slots=True)
class AcademicCalendar:
    academic_year: int
    label: str
    coverage_start: date
    coverage_end: date
    periods: tuple[CalendarPeriod, ...]
    public_holidays: tuple[PublicHoliday, ...]
    exceptions: tuple[CalendarException, ...]
    early_dismissal_policies: tuple[EarlyDismissalPolicy, ...]
    source: str
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.coverage_start > self.coverage_end:
            raise ValueError("academic calendar coverage start must not follow its end")
        ordered = sorted(self.periods, key=lambda period: period.start)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.end >= current.start:
                raise ValueError(f"overlapping calendar periods: {previous} and {current}")
        if any(
            period.start < self.coverage_start or period.end > self.coverage_end
            for period in self.periods
        ):
            raise ValueError("calendar period falls outside declared coverage")


@dataclass(frozen=True, slots=True)
class DateResolution:
    date: date
    academic_year: int | None
    academic_year_label: str | None
    semester: str | None
    weekday: str
    day_of_week: int
    period_type: PeriodType
    teaching_week: int | None
    regular_timetable_applicable: bool
    is_public_holiday: bool
    holiday_name: str | None
    holiday_observed: bool
    holiday_note: str
    source_note: str
    exceptions: tuple[CalendarException, ...] = ()
