from datetime import date

import pytest

from ntu_room_checker.calendar import default_resolver
from ntu_room_checker.calendar.models import PeriodType
from ntu_room_checker.calendar.calendars.ay2026_27 import AY2026_27


@pytest.mark.parametrize(
    ("value", "week", "weekday"),
    [
        ("2026-08-10", 1, "MON"),
        ("2026-08-15", 1, "SAT"),
        ("2026-08-17", 2, "MON"),
        ("2026-08-22", 2, "SAT"),
        ("2026-08-24", 3, "MON"),
        ("2026-08-29", 3, "SAT"),
        ("2026-08-31", 4, "MON"),
        ("2026-09-05", 4, "SAT"),
        ("2026-09-07", 5, "MON"),
        ("2026-09-12", 5, "SAT"),
        ("2026-09-14", 6, "MON"),
        ("2026-09-19", 6, "SAT"),
        ("2026-09-21", 7, "MON"),
        ("2026-09-26", 7, "SAT"),
        ("2026-10-05", 8, "MON"),
        ("2026-10-10", 8, "SAT"),
        ("2026-10-12", 9, "MON"),
        ("2026-10-17", 9, "SAT"),
        ("2026-10-19", 10, "MON"),
        ("2026-10-24", 10, "SAT"),
        ("2026-10-26", 11, "MON"),
        ("2026-10-31", 11, "SAT"),
        ("2026-11-02", 12, "MON"),
        ("2026-11-07", 12, "SAT"),
        ("2026-11-09", 13, "MON"),
        ("2026-11-14", 13, "SAT"),
        ("2027-01-11", 1, "MON"),
        ("2027-01-16", 1, "SAT"),
        ("2027-01-18", 2, "MON"),
        ("2027-01-23", 2, "SAT"),
        ("2027-01-25", 3, "MON"),
        ("2027-01-30", 3, "SAT"),
        ("2027-02-01", 4, "MON"),
        ("2027-02-06", 4, "SAT"),
        ("2027-02-08", 5, "MON"),
        ("2027-02-13", 5, "SAT"),
        ("2027-02-15", 6, "MON"),
        ("2027-02-20", 6, "SAT"),
        ("2027-02-22", 7, "MON"),
        ("2027-02-27", 7, "SAT"),
        ("2027-03-08", 8, "MON"),
        ("2027-03-13", 8, "SAT"),
        ("2027-03-15", 9, "MON"),
        ("2027-03-20", 9, "SAT"),
        ("2027-03-22", 10, "MON"),
        ("2027-03-27", 10, "SAT"),
        ("2027-03-29", 11, "MON"),
        ("2027-04-03", 11, "SAT"),
        ("2027-04-05", 12, "MON"),
        ("2027-04-10", 12, "SAT"),
        ("2027-04-12", 13, "MON"),
        ("2027-04-17", 13, "SAT"),
    ],
)
def test_regular_semester_teaching_week_boundaries(
    value: str, week: int, weekday: str
) -> None:
    result = default_resolver().resolve(value)
    assert result.period_type == PeriodType.TEACHING_WEEK
    assert result.teaching_week == week
    assert result.weekday == weekday
    assert result.regular_timetable_applicable


@pytest.mark.parametrize(
    ("value", "semester"),
    [
        ("2026-09-28", "1"),
        ("2026-10-02", "1"),
        ("2027-03-01", "2"),
        ("2027-03-05", "2"),
    ],
)
def test_recess_boundaries_are_not_regular_timetable_days(
    value: str, semester: str
) -> None:
    result = default_resolver().resolve(value)
    assert result.period_type == PeriodType.RECESS_WEEK
    assert result.semester == semester
    assert result.teaching_week is None
    assert not result.regular_timetable_applicable


@pytest.mark.parametrize(
    ("value", "semester"),
    [
        ("2026-11-16", "1"),
        ("2026-11-20", "1"),
        ("2026-11-23", "1"),
        ("2026-12-04", "1"),
        ("2027-04-19", "2"),
        ("2027-04-23", "2"),
        ("2027-04-26", "2"),
        ("2027-05-07", "2"),
    ],
)
def test_revision_exam_boundaries(value: str, semester: str) -> None:
    result = default_resolver().resolve(value)
    assert result.period_type == PeriodType.REVISION_EXAM
    assert result.semester == semester
    assert not result.regular_timetable_applicable


@pytest.mark.parametrize(
    ("value", "week"),
    [
        ("2027-05-10", 1),
        ("2027-05-15", 1),
        ("2027-05-31", 4),
        ("2027-06-05", 4),
        ("2027-06-07", 5),
        ("2027-06-12", 5),
        ("2027-06-14", 6),
        ("2027-06-19", 6),
        ("2027-06-21", 7),
        ("2027-06-26", 7),
        ("2027-06-28", 8),
        ("2027-07-03", 8),
        ("2027-07-05", 9),
        ("2027-07-10", 9),
        ("2027-07-12", 10),
        ("2027-07-17", 10),
        ("2027-07-19", 11),
        ("2027-07-24", 11),
        ("2027-07-26", 12),
        ("2027-07-31", 12),
    ],
)
def test_special_term_blocks(value: str, week: int) -> None:
    result = default_resolver().resolve(value)
    assert result.period_type == PeriodType.SPECIAL_TERM
    assert result.semester == "S"
    assert result.teaching_week == week
    assert result.regular_timetable_applicable


def test_special_term_ends_in_july() -> None:
    result = default_resolver().resolve("2027-08-02")
    assert result.period_type == PeriodType.OUTSIDE_TERM
    assert result.teaching_week is None
    assert not result.regular_timetable_applicable


@pytest.mark.parametrize(
    ("value", "name", "observed"),
    [
        ("2026-08-09", "National Day", False),
        ("2026-08-10", "National Day (replacement holiday)", True),
        ("2026-11-08", "Deepavali", False),
        ("2026-11-09", "Deepavali (replacement holiday)", True),
        ("2026-12-25", "Christmas Day", False),
        ("2027-01-01", "New Year's Day", False),
        ("2027-02-06", "Chinese New Year (Day 1)", False),
        ("2027-02-07", "Chinese New Year (Day 2)", False),
        ("2027-02-08", "Chinese New Year (replacement holiday)", True),
        ("2027-03-10", "Hari Raya Puasa", False),
        ("2027-03-26", "Good Friday", False),
        ("2027-05-01", "Labour Day", False),
        ("2027-05-17", "Hari Raya Haji", False),
        ("2027-05-20", "Vesak Day", False),
    ],
)
def test_public_holidays_are_independent_flags(
    value: str, name: str, observed: bool
) -> None:
    result = default_resolver().resolve(value)
    assert result.is_public_holiday
    assert result.holiday_name == name
    assert result.holiday_observed is observed


def test_holiday_does_not_automatically_disable_timetable() -> None:
    result = default_resolver().resolve("2026-08-10")
    assert result.is_public_holiday
    assert result.teaching_week == 1
    assert result.regular_timetable_applicable


@pytest.mark.parametrize("sunday,monday", [("2026-08-09", "2026-08-10"), ("2026-11-08", "2026-11-09"), ("2027-02-07", "2027-02-08")])
def test_sunday_holiday_has_separate_monday_replacement(
    sunday: str, monday: str
) -> None:
    actual = default_resolver().resolve(sunday)
    replacement = default_resolver().resolve(monday)
    assert actual.is_public_holiday and not actual.holiday_observed
    assert replacement.is_public_holiday and replacement.holiday_observed


def test_saturday_holiday_does_not_create_monday_replacement() -> None:
    saturday = default_resolver().resolve("2027-05-01")
    monday = default_resolver().resolve("2027-05-03")
    assert saturday.is_public_holiday
    assert not monday.is_public_holiday


def test_students_union_day_exception_is_structured() -> None:
    result = default_resolver().resolve("2026-09-04")
    assert result.teaching_week == 4
    assert len(result.exceptions) == 1
    exception = result.exceptions[0]
    assert (exception.start_minute, exception.end_minute) == (630, 870)
    assert exception.affected_population == "undergraduate_programmes"
    assert "No classes" in exception.description


def test_holiday_eve_1430_rule_is_structured_metadata() -> None:
    assert len(AY2026_27.early_dismissal_policies) == 1
    policy = AY2026_27.early_dismissal_policies[0]
    assert policy.end_minute == 870
    assert policy.holiday_names == (
        "New Year's Day", "Chinese New Year", "Hari Raya Puasa", "Deepavali"
    )
    assert "no meeting truncation" in policy.source_note


@pytest.mark.parametrize("value", ["2026-07-01", "2026-09-27", "2026-10-03", "2026-11-15", "2026-11-21", "2027-03-06", "2027-04-24", "2027-08-02", "2028-01-01"])
def test_dates_outside_encoded_periods_are_not_available(value: str) -> None:
    result = default_resolver().resolve(value)
    assert result.period_type == PeriodType.OUTSIDE_TERM
    assert not result.regular_timetable_applicable


def test_gap_inside_calendar_retains_academic_year_context() -> None:
    result = default_resolver().resolve("2026-09-27")
    assert result.academic_year_label == "AY2026-27"
    assert result.semester is None
    assert result.period_type == PeriodType.OUTSIDE_TERM


def test_requested_example_resolves_to_semester_one_week_six() -> None:
    result = default_resolver().resolve(date(2026, 9, 15))
    assert (result.academic_year, result.semester, result.teaching_week, result.weekday) == (
        2026, "1", 6, "TUE"
    )
