"""Strict normalization of observed NTU weekday labels."""

from ntu_room_checker.normalization.models import DayResult

DAYS = {"MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6, "SUN": 7}


def parse_day(raw: str) -> DayResult:
    value = raw.strip().upper()
    if not value:
        return DayResult(raw, None, "missing")
    if value not in DAYS:
        return DayResult(raw, None, "unparsed")
    return DayResult(raw, DAYS[value], "parsed")


def day_number(value: str | int) -> int:
    if isinstance(value, int):
        if 1 <= value <= 7:
            return value
        raise ValueError("day number must be from 1 (Monday) to 7 (Sunday)")
    result = parse_day(value)
    if result.day_of_week is None:
        raise ValueError(f"unsupported weekday: {value!r}")
    return result.day_of_week
