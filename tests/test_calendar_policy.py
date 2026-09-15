from datetime import date

import pytest

from ntu_room_checker.calendar import CalendarPolicyEngine, default_resolver
from ntu_room_checker.calendar.policy import ApplicabilityStatus, TimetableAuthority


@pytest.fixture
def policy() -> CalendarPolicyEngine:
    return CalendarPolicyEngine()


def test_normal_teaching_meeting_applies_unchanged(policy: CalendarPolicyEngine) -> None:
    result = policy.evaluate_meeting(default_resolver().resolve("2026-09-15"), 810, 920)
    assert result.status == ApplicabilityStatus.APPLICABLE
    assert (result.effective_start, result.effective_end) == (810, 920)


@pytest.mark.parametrize(
    ("start", "end", "status", "effective"),
    [
        (780, 840, ApplicabilityStatus.APPLICABLE, (780, 840)),
        (810, 870, ApplicabilityStatus.APPLICABLE, (810, 870)),
        (810, 920, ApplicabilityStatus.APPLICABLE, (810, 870)),
        (870, 920, ApplicabilityStatus.NOT_APPLICABLE, (None, None)),
        (930, 1040, ApplicabilityStatus.NOT_APPLICABLE, (None, None)),
    ],
)
def test_holiday_eve_cutoff_effective_intervals(
    policy: CalendarPolicyEngine,
    start: int,
    end: int,
    status: ApplicabilityStatus,
    effective: tuple[int | None, int | None],
) -> None:
    result = policy.evaluate_meeting(default_resolver().resolve("2027-02-05"), start, end)
    assert result.status == status
    assert (result.effective_start, result.effective_end) == effective


@pytest.mark.parametrize(
    "value", ["2026-11-07", "2026-12-31", "2027-02-05", "2027-03-09"]
)
def test_each_holiday_eve_is_structured(value: str) -> None:
    resolution = default_resolver().resolve(value)
    assert len(resolution.exceptions) == 1
    assert resolution.exceptions[0].cutoff_minute == 870


@pytest.mark.parametrize(
    ("start", "end", "status"),
    [
        (540, 600, ApplicabilityStatus.APPLICABLE),
        (570, 630, ApplicabilityStatus.APPLICABLE),
        (600, 660, ApplicabilityStatus.UNCERTAIN),
        (630, 870, ApplicabilityStatus.UNCERTAIN),
        (840, 900, ApplicabilityStatus.UNCERTAIN),
        (870, 930, ApplicabilityStatus.APPLICABLE),
        (900, 960, ApplicabilityStatus.APPLICABLE),
    ],
)
def test_students_union_boundaries(
    policy: CalendarPolicyEngine,
    start: int,
    end: int,
    status: ApplicabilityStatus,
) -> None:
    result = policy.evaluate_meeting(default_resolver().resolve("2026-09-04"), start, end)
    assert result.status == status
    if status == ApplicabilityStatus.UNCERTAIN:
        assert result.reason_code == "population_scope_unknown"


@pytest.mark.parametrize(
    ("value", "authority"),
    [
        ("2026-09-15", TimetableAuthority.AUTHORITATIVE),
        ("2026-09-28", TimetableAuthority.NOT_APPLICABLE),
        ("2026-11-16", TimetableAuthority.NOT_AUTHORITATIVE),
        ("2026-07-21", TimetableAuthority.NOT_APPLICABLE),
        ("2026-09-27", TimetableAuthority.UNAVAILABLE),
        ("2026-07-01", TimetableAuthority.UNAVAILABLE),
    ],
)
def test_non_teaching_authority_taxonomy(
    policy: CalendarPolicyEngine, value: str, authority: TimetableAuthority
) -> None:
    assert policy.evaluate_date(default_resolver().resolve(value)).authority == authority


@pytest.mark.parametrize(
    ("value", "observed"),
    [
        ("2026-08-09", False),
        ("2026-08-10", True),
        ("2027-05-01", False),
    ],
)
def test_actual_and_replacement_holidays_are_not_authoritative(
    policy: CalendarPolicyEngine, value: str, observed: bool
) -> None:
    resolution = default_resolver().resolve(value)
    assert resolution.holiday_observed is observed
    assert policy.evaluate_date(resolution).authority == TimetableAuthority.NOT_AUTHORITATIVE


def test_monday_after_saturday_holiday_remains_normal_calendar_policy(
    policy: CalendarPolicyEngine,
) -> None:
    # Labour Day is Saturday 1 May; the PDF explicitly says Monday proceeds normally.
    resolution = default_resolver().resolve(date(2027, 5, 3))
    assert not resolution.is_public_holiday
    assert policy.evaluate_date(resolution).authority == TimetableAuthority.NOT_AUTHORITATIVE
    assert resolution.period_type.value == "revision_exam"
