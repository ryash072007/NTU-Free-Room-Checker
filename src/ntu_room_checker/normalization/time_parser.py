"""Strict parsing of time formats observed in the full NTU dataset."""

import re

from ntu_room_checker.normalization.models import TimeResult

TIME_PATTERN = re.compile(r"^(\d{2})(\d{2})-(\d{2})(\d{2})$")


def parse_time(raw: str) -> TimeResult:
    value = raw.strip()
    if not value:
        return TimeResult(raw, None, None, "missing")
    match = TIME_PATTERN.fullmatch(value)
    if match is None:
        return TimeResult(raw, None, None, "unparsed")
    start_hour, start_minute, end_hour, end_minute = map(int, match.groups())
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        return TimeResult(raw, None, None, "invalid_range")
    if not (0 <= start_minute <= 59 and 0 <= end_minute <= 59):
        return TimeResult(raw, None, None, "invalid_range")
    start = start_hour * 60 + start_minute
    end = end_hour * 60 + end_minute
    if start >= end:
        return TimeResult(raw, None, None, "invalid_order")
    return TimeResult(raw, start, end, "parsed")


def parse_clock(value: str) -> int:
    """Parse a query clock in HHMM or HH:MM form."""
    compact = value.replace(":", "").strip()
    match = re.fullmatch(r"(\d{2})(\d{2})", compact)
    if match is None:
        raise ValueError("time must be HHMM or HH:MM")
    hour, minute = map(int, match.groups())
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time is outside the valid 00:00-23:59 range")
    return hour * 60 + minute
