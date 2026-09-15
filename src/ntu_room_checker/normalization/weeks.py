"""Conservative parser for teaching-week remarks observed in NTU data."""

import re

from ntu_room_checker.normalization.models import WeekResult

PREFIX = "Teaching Wk"


def parse_weeks(raw: str) -> WeekResult:
    value = raw.strip()
    if not value:
        # Query code treats unspecified applicability as occupied in every requested
        # teaching week. This conservative policy prevents false availability.
        return WeekResult(raw, (), "unspecified_conservative")
    if value == "Not conducted during Teaching Weeks":
        return WeekResult(raw, (), "not_during_teaching_weeks")
    if not value.startswith(PREFIX):
        return WeekResult(raw, (), "unparsed_conservative")
    expression = value[len(PREFIX) :]
    if not re.fullmatch(r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*", expression):
        return WeekResult(raw, (), "unparsed_conservative")
    weeks: set[int] = set()
    for part in expression.split(","):
        if "-" in part:
            start, end = map(int, part.split("-", maxsplit=1))
            if start > end:
                return WeekResult(raw, (), "invalid")
            weeks.update(range(start, end + 1))
        else:
            weeks.add(int(part))
    if not weeks or min(weeks) < 1 or max(weeks) > 13:
        return WeekResult(raw, (), "invalid")
    return WeekResult(raw, tuple(sorted(weeks)), "parsed")
