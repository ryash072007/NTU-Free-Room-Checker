"""Location catalog values."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Location:
    id: str
    name: str
    short_name: str
    official_name: str | None
    aliases: tuple[str, ...]
    patterns: tuple[str, ...]
    explicit_rooms: frozenset[str] = frozenset()
    excluded_rooms: frozenset[str] = frozenset()
