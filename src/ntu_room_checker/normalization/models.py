"""Small immutable values returned by normalization parsers."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeResult:
    raw: str
    start_minute: int | None
    end_minute: int | None
    status: str


@dataclass(frozen=True, slots=True)
class DayResult:
    raw: str
    day_of_week: int | None
    status: str


@dataclass(frozen=True, slots=True)
class VenueResult:
    raw: str
    normalized: str
    venue_type: str


@dataclass(frozen=True, slots=True)
class WeekResult:
    raw: str
    weeks: tuple[int, ...]
    status: str
