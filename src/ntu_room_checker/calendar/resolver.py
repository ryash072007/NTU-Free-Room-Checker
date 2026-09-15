"""Generic resolver over registered, explicit academic calendars."""

from datetime import date
from typing import Iterable

from ntu_room_checker.calendar.models import (
    AcademicCalendar,
    DateResolution,
    PeriodType,
)

WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


class CalendarResolver:
    def __init__(self, calendars: Iterable[AcademicCalendar]) -> None:
        self.calendars = tuple(calendars)

    def resolve(self, value: date | str) -> DateResolution:
        target = date.fromisoformat(value) if isinstance(value, str) else value
        weekday_number = target.isoweekday()
        for calendar in self.calendars:
            holiday = next(
                (item for item in calendar.public_holidays if item.date == target), None
            )
            period = next((item for item in calendar.periods if item.contains(target)), None)
            if period is not None or holiday is not None:
                return DateResolution(
                    date=target,
                    academic_year=calendar.academic_year,
                    academic_year_label=calendar.label,
                    semester=period.semester if period else None,
                    weekday=WEEKDAYS[weekday_number - 1],
                    day_of_week=weekday_number,
                    period_type=period.period_type if period else PeriodType.OUTSIDE_TERM,
                    teaching_week=period.teaching_week if period else None,
                    regular_timetable_applicable=(
                        period.regular_timetable_applicable if period else False
                    ),
                    is_public_holiday=holiday is not None,
                    holiday_name=holiday.name if holiday else None,
                    holiday_observed=holiday.observed if holiday else False,
                    holiday_note=holiday.source_note if holiday else "",
                    source_note=period.source_note if period else "",
                )
        return DateResolution(
            target, None, None, None, WEEKDAYS[weekday_number - 1], weekday_number,
            PeriodType.OUTSIDE_TERM, None, False, False, None, False, "", "",
        )


def default_resolver() -> CalendarResolver:
    from ntu_room_checker.calendar.calendars.ay2026_27 import AY2026_27

    return CalendarResolver((AY2026_27,))
