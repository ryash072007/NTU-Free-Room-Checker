"""Conservative, evidence-backed room location classification."""

from .catalog import LOCATIONS, get_location
from .classifier import classify_room, rooms_by_location
from .models import Location

__all__ = ["LOCATIONS", "Location", "classify_room", "get_location", "rooms_by_location"]
