"""Exact and anchored classification; canonical room identifiers are never changed."""

import re
from collections.abc import Iterable

from .catalog import LOCATIONS
from .models import Location


def classify_room(room: str) -> Location | None:
    for location in LOCATIONS:
        if room in location.excluded_rooms:
            continue
        if room in location.explicit_rooms or any(re.match(pattern, room) for pattern in location.patterns):
            return location
    return None


def rooms_by_location(rooms: Iterable[str]) -> dict[str, list[str]]:
    grouped = {location.id: [] for location in LOCATIONS}
    for room in rooms:
        location = classify_room(room)
        if location is not None:
            grouped[location.id].append(room)
    return {key: sorted(values) for key, values in grouped.items() if values}
