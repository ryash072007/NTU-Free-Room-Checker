"""Conservative venue normalization and classification."""

import re

from ntu_room_checker.normalization.models import VenueResult

UNKNOWN_VALUES = {"TBA", "TBC", "NIL", "N/A", "NA"}
ONLINE_VALUES = {"ONLINE"}
OTHER_VALUES = {"OVERSEAS"}


def normalize_venue(raw: str) -> VenueResult:
    normalized = re.sub(r"\s+", " ", raw.strip()).upper()
    if not normalized:
        venue_type = "none"
    elif normalized in ONLINE_VALUES:
        venue_type = "online"
    elif normalized in UNKNOWN_VALUES:
        venue_type = "unknown"
    elif normalized in OTHER_VALUES:
        venue_type = "other"
    else:
        venue_type = "physical_room"
    return VenueResult(raw, normalized, venue_type)
