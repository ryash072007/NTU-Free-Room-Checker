"""Official NTU Academic Calendar (Semester), AY2026-27 PDF transcription."""

from datetime import date

from ntu_room_checker.calendar.models import (
    AcademicCalendar,
    CalendarException,
    CalendarPeriod,
    EarlyDismissalPolicy,
    ExceptionEffect,
    PeriodType,
    PopulationScope,
    PublicHoliday,
)


def _teaching(start: tuple[int, int, int], end: tuple[int, int, int], semester: str, week: int) -> CalendarPeriod:
    return CalendarPeriod(
        date(*start), date(*end), PeriodType.TEACHING_WEEK, semester,
        teaching_week=week, regular_timetable_applicable=True,
    )


def _special(start: tuple[int, int, int], end: tuple[int, int, int], week: int, note: str = "") -> CalendarPeriod:
    return CalendarPeriod(
        date(*start), date(*end), PeriodType.SPECIAL_TERM, "S",
        teaching_week=week, regular_timetable_applicable=True, source_note=note,
    )


PERIODS = (
    CalendarPeriod(date(2026, 7, 20), date(2026, 8, 6), PeriodType.ORIENTATION, "1"),
    _teaching((2026, 8, 10), (2026, 8, 15), "1", 1),
    _teaching((2026, 8, 17), (2026, 8, 22), "1", 2),
    _teaching((2026, 8, 24), (2026, 8, 29), "1", 3),
    _teaching((2026, 8, 31), (2026, 9, 5), "1", 4),
    _teaching((2026, 9, 7), (2026, 9, 12), "1", 5),
    _teaching((2026, 9, 14), (2026, 9, 19), "1", 6),
    _teaching((2026, 9, 21), (2026, 9, 26), "1", 7),
    CalendarPeriod(date(2026, 9, 28), date(2026, 10, 2), PeriodType.RECESS_WEEK, "1"),
    _teaching((2026, 10, 5), (2026, 10, 10), "1", 8),
    _teaching((2026, 10, 12), (2026, 10, 17), "1", 9),
    _teaching((2026, 10, 19), (2026, 10, 24), "1", 10),
    _teaching((2026, 10, 26), (2026, 10, 31), "1", 11),
    _teaching((2026, 11, 2), (2026, 11, 7), "1", 12),
    _teaching((2026, 11, 9), (2026, 11, 14), "1", 13),
    CalendarPeriod(date(2026, 11, 16), date(2026, 11, 20), PeriodType.REVISION_EXAM, "1"),
    CalendarPeriod(date(2026, 11, 23), date(2026, 11, 27), PeriodType.REVISION_EXAM, "1"),
    CalendarPeriod(date(2026, 11, 30), date(2026, 12, 4), PeriodType.REVISION_EXAM, "1"),

    CalendarPeriod(
        date(2027, 1, 4), date(2027, 1, 8), PeriodType.ORIENTATION, "2",
        source_note="Orientation Activities: 4-8 Jan 2027 (For PG Only).",
    ),
    _teaching((2027, 1, 11), (2027, 1, 16), "2", 1),
    _teaching((2027, 1, 18), (2027, 1, 23), "2", 2),
    _teaching((2027, 1, 25), (2027, 1, 30), "2", 3),
    _teaching((2027, 2, 1), (2027, 2, 6), "2", 4),
    _teaching((2027, 2, 8), (2027, 2, 13), "2", 5),
    _teaching((2027, 2, 15), (2027, 2, 20), "2", 6),
    _teaching((2027, 2, 22), (2027, 2, 27), "2", 7),
    CalendarPeriod(date(2027, 3, 1), date(2027, 3, 5), PeriodType.RECESS_WEEK, "2"),
    _teaching((2027, 3, 8), (2027, 3, 13), "2", 8),
    _teaching((2027, 3, 15), (2027, 3, 20), "2", 9),
    _teaching((2027, 3, 22), (2027, 3, 27), "2", 10),
    _teaching((2027, 3, 29), (2027, 4, 3), "2", 11),
    _teaching((2027, 4, 5), (2027, 4, 10), "2", 12),
    _teaching((2027, 4, 12), (2027, 4, 17), "2", 13),
    CalendarPeriod(date(2027, 4, 19), date(2027, 4, 23), PeriodType.REVISION_EXAM, "2"),
    CalendarPeriod(date(2027, 4, 26), date(2027, 4, 30), PeriodType.REVISION_EXAM, "2"),
    CalendarPeriod(date(2027, 5, 3), date(2027, 5, 7), PeriodType.REVISION_EXAM, "2"),

    _special((2027, 5, 10), (2027, 5, 15), 1),
    _special((2027, 5, 17), (2027, 5, 22), 2),
    _special((2027, 5, 24), (2027, 5, 29), 3),
    _special((2027, 5, 31), (2027, 6, 5), 4),
    _special((2027, 6, 7), (2027, 6, 12), 5),
    _special((2027, 6, 14), (2027, 6, 19), 6),
    _special((2027, 6, 21), (2027, 6, 26), 7),
    _special((2027, 6, 28), (2027, 7, 3), 8),
    _special((2027, 7, 5), (2027, 7, 10), 9),
    _special((2027, 7, 12), (2027, 7, 17), 10),
    _special((2027, 7, 19), (2027, 7, 24), 11),
    _special((2027, 7, 26), (2027, 7, 31), 12),
)


HOLIDAYS = (
    PublicHoliday(date(2026, 8, 9), "National Day", source_note="Official date falls on Sunday."),
    PublicHoliday(date(2026, 8, 10), "National Day (replacement holiday)", observed=True, source_note="Calendar note: a Sunday public holiday is replaced on Monday."),
    PublicHoliday(date(2026, 11, 8), "Deepavali", source_note="Official date falls on Sunday."),
    PublicHoliday(date(2026, 11, 9), "Deepavali (replacement holiday)", observed=True, source_note="Calendar note: a Sunday public holiday is replaced on Monday."),
    PublicHoliday(date(2026, 12, 25), "Christmas Day"),
    PublicHoliday(date(2027, 1, 1), "New Year's Day"),
    PublicHoliday(date(2027, 2, 6), "Chinese New Year (Day 1)"),
    PublicHoliday(date(2027, 2, 7), "Chinese New Year (Day 2)", source_note="Official date falls on Sunday."),
    PublicHoliday(date(2027, 2, 8), "Chinese New Year (replacement holiday)", observed=True, source_note="Calendar marks Monday as the replacement holiday."),
    PublicHoliday(date(2027, 3, 10), "Hari Raya Puasa"),
    PublicHoliday(date(2027, 3, 26), "Good Friday"),
    PublicHoliday(date(2027, 5, 1), "Labour Day", source_note="Calendar note says classes proceed normally on the immediate Monday after a Saturday public holiday."),
    PublicHoliday(date(2027, 5, 17), "Hari Raya Haji"),
    PublicHoliday(date(2027, 5, 20), "Vesak Day"),
)


EXCEPTIONS = (
    CalendarException(
        exception_id="students_union_day_2026",
        date=date(2026, 9, 4),
        effect=ExceptionEffect.NO_CLASSES,
        affected_population=PopulationScope.UNDERGRADUATE,
        description="Students' Union Day: No classes for UG programmes from 1030 to 1430 hours.",
        start_minute=10 * 60 + 30,
        end_minute=14 * 60 + 30,
        source_note="University Key Events table in the official AY2026-27 PDF.",
    ),
    CalendarException(
        exception_id="deepavali_eve_2026",
        date=date(2026, 11, 7),
        effect=ExceptionEffect.CLASSES_END_AT,
        affected_population=PopulationScope.ALL,
        cutoff_minute=14 * 60 + 30,
        description="Classes end at 1430 hours on the eve of Deepavali.",
        source_note="Caret footnote in the official AY2026-27 PDF.",
    ),
    CalendarException(
        exception_id="new_year_eve_2026",
        date=date(2026, 12, 31),
        effect=ExceptionEffect.CLASSES_END_AT,
        affected_population=PopulationScope.ALL,
        cutoff_minute=14 * 60 + 30,
        description="Classes end at 1430 hours on the eve of New Year's Day.",
        source_note="Caret footnote in the official AY2026-27 PDF.",
    ),
    CalendarException(
        exception_id="chinese_new_year_eve_2027",
        date=date(2027, 2, 5),
        effect=ExceptionEffect.CLASSES_END_AT,
        affected_population=PopulationScope.ALL,
        cutoff_minute=14 * 60 + 30,
        description="Classes end at 1430 hours on the eve of Chinese New Year.",
        source_note="Caret footnote in the official AY2026-27 PDF.",
    ),
    CalendarException(
        exception_id="hari_raya_puasa_eve_2027",
        date=date(2027, 3, 9),
        effect=ExceptionEffect.CLASSES_END_AT,
        affected_population=PopulationScope.ALL,
        cutoff_minute=14 * 60 + 30,
        description="Classes end at 1430 hours on the eve of Hari Raya Puasa.",
        source_note="Caret footnote in the official AY2026-27 PDF.",
    ),
)


EARLY_DISMISSAL_POLICIES = (
    EarlyDismissalPolicy(
        end_minute=14 * 60 + 30,
        holiday_names=("New Year's Day", "Chinese New Year", "Hari Raya Puasa", "Deepavali"),
        description="Classes end at 1430 hours on the eves of the listed public holidays.",
        source_note="Caret footnote in the official AY2026-27 PDF; no meeting truncation is applied automatically.",
    ),
)


AY2026_27 = AcademicCalendar(
    academic_year=2026,
    label="AY2026-27",
    coverage_start=date(2026, 7, 20),
    coverage_end=date(2027, 7, 31),
    periods=PERIODS,
    public_holidays=HOLIDAYS,
    exceptions=EXCEPTIONS,
    early_dismissal_policies=EARLY_DISMISSAL_POLICIES,
    source="Official NTU Academic Calendar (Semester): AY2026-27 PDF, published 10 March 2026",
    notes=(
        "Public-holiday status does not itself disable regular timetable applicability.",
        "Classes proceed normally on the immediate Monday after a Saturday public holiday.",
        "All dates are subject to change at the discretion of the University.",
    ),
)
