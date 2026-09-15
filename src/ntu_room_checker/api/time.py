"""Singapore-local time and API clock helpers."""

from datetime import datetime

from ntu_room_checker.api.config import SINGAPORE_TIMEZONE


def singapore_now() -> datetime:
    return datetime.now(SINGAPORE_TIMEZONE)


def minute_to_clock(value: int | None) -> str | None:
    if value is None:
        return None
    return f"{value // 60:02d}:{value % 60:02d}"

