"""Academic-calendar resolution independent of scraping and normalization."""

from ntu_room_checker.calendar.resolver import CalendarResolver, default_resolver
from ntu_room_checker.calendar.policy import CalendarPolicyEngine

__all__ = ["CalendarPolicyEngine", "CalendarResolver", "default_resolver"]
