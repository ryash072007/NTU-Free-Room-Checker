from datetime import date

import pytest

from ntu_room_checker.calendar import default_resolver
from ntu_room_checker.calendar.models import PeriodType


@pytest.mark.parametrize(
    ("value", "week", "weekday"),
    [
        ("2026-08-10", 1, "MON"),
        ("2026-08-15", 1, "SAT"),
        ("2026-08-17", 2, "MON"),
        ("2026-09-26", 7, "SAT"),
        ("2026-10-05", 8, "MON"),
        ("2026-11-14", 13, "SAT"),
        ("2027-01-11", 1, "MON"),
        ("2027-01-16", 1, "SAT"),
        ("2027-03-08", 8, "MON"),
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
        ("2026-10-03", "1"),
        ("2027-03-01", "2"),
        ("2027-03-06", "2"),
        ("2027-06-07", "S"),
        ("2027-06-12", "S"),
        ("2027-07-12", "S"),
        ("2027-07-17", "S"),
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
        ("2026-12-04", "1"),
        ("2027-04-19", "2"),
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
        ("2027-06-05", 4),
        ("2027-06-14", 5),
        ("2027-07-10", 8),
        ("2027-07-19", 9),
        ("2027-07-31", 10),
        ("2027-08-02", 11),
        ("2027-08-14", 12),
    ],
)
def test_special_term_blocks(value: str, week: int) -> None:
    result = default_resolver().resolve(value)
    assert result.period_type == PeriodType.SPECIAL_TERM
    assert result.semester == "S"
    assert result.teaching_week == week
    assert result.regular_timetable_applicable


def test_special_term_inferred_august_dates_are_transparent() -> None:
    result = default_resolver().resolve("2027-08-09")
    assert result.teaching_week == 12
    assert "August grid is not shown" in result.source_note


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


@pytest.mark.parametrize("value", ["2026-07-01", "2026-09-27", "2026-11-15", "2027-08-15", "2028-01-01"])
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
