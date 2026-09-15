"""Academic-calendar resolution independent of scraping and normalization."""

from ntu_room_checker.calendar.resolver import CalendarResolver, default_resolver

__all__ = ["CalendarResolver", "default_resolver"]
