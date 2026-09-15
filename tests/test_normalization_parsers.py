import pytest
from pathlib import Path

from ntu_room_checker.normalization.day_parser import day_number, parse_day
from ntu_room_checker.normalization.time_parser import parse_clock, parse_time
from ntu_room_checker.normalization.venue import normalize_venue
from ntu_room_checker.normalization.weeks import parse_weeks

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("raw", "start", "end"),
    [("0830-0920", 510, 560), ("1030-1120", 630, 680), ("2200-2250", 1320, 1370)],
)
def test_parses_observed_time_shape(raw: str, start: int, end: int) -> None:
    result = parse_time(raw)
    assert (result.start_minute, result.end_minute, result.status) == (start, end, "parsed")


@pytest.mark.parametrize("raw,status", [("", "missing"), ("2500-2600", "invalid_range"), ("1200-1100", "invalid_order"), ("noon", "unparsed")])
def test_preserves_unsupported_times(raw: str, status: str) -> None:
    result = parse_time(raw)
    assert result.raw == raw and result.status == status
    assert result.start_minute is None and result.end_minute is None


def test_every_nonblank_time_value_observed_in_full_database() -> None:
    observed = (FIXTURES / "observed_time_values.txt").read_text().splitlines()
    assert len(observed) == 84
    assert all(parse_time(value).status == "parsed" for value in observed)


def test_query_clock_formats() -> None:
    assert parse_clock("1430") == parse_clock("14:30") == 870


def test_days_are_iso_numbered_and_missing_is_not_fabricated() -> None:
    assert parse_day("MON").day_of_week == 1
    assert parse_day("SAT").day_of_week == 6
    assert parse_day("").status == "missing"
    assert day_number("sun") == 7


@pytest.mark.parametrize(
    ("raw", "normalized", "kind"),
    [(" LHN-TR+15 ", "LHN-TR+15", "physical_room"), ("online", "ONLINE", "online"), ("TBA", "TBA", "unknown"), ("ADM VENUE", "ADM VENUE", "unknown"), ("", "", "none"), ("overseas", "OVERSEAS", "other"), ("RECORDED", "RECORDED", "other"), ("SITE VISIT", "SITE VISIT", "other"), ("4&11 AUG", "4&11 AUG", "other")],
)
def test_conservative_venue_classification(raw: str, normalized: str, kind: str) -> None:
    result = normalize_venue(raw)
    assert (result.normalized, result.venue_type) == (normalized, kind)


@pytest.mark.parametrize(
    ("raw", "weeks", "status"),
    [("Teaching Wk2-6,8-12", tuple(range(2, 7)) + tuple(range(8, 13)), "parsed"), ("Teaching Wk1,3,5,7,9,11,13", (1, 3, 5, 7, 9, 11, 13), "parsed"), ("", (), "unspecified_conservative"), ("Not conducted during Teaching Weeks", (), "not_during_teaching_weeks"), ("Cancelled on a date", (), "unparsed_conservative")],
)
def test_week_parser(raw: str, weeks: tuple[int, ...], status: str) -> None:
    assert parse_weeks(raw) == type(parse_weeks(raw))(raw, weeks, status)
