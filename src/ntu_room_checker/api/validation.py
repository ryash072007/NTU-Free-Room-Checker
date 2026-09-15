from datetime import date
import re

from fastapi import HTTPException

CLOCK_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def parse_api_clock(value: str) -> int:
    if not CLOCK_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "time must use HH:MM (00:00-23:59)"},
        )
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def local_datetime(value: date, minute: int) -> str:
    # Offset is explicit even though current domain queries consume only local
    # date and clock components.
    return f"{value.isoformat()}T{minute // 60:02d}:{minute % 60:02d}+08:00"
