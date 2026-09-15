"""Conservative venue normalization and classification."""

import re

from ntu_room_checker.normalization.models import VenueResult

UNKNOWN_VALUES = {"TBA", "TBC", "NIL", "N/A", "NA", "ADM VENUE"}
ONLINE_VALUES = {"ONLINE"}
OTHER_VALUES = {"OVERSEAS", "RECORDED", "RECORDING", "SITE VISIT"}
DATE_EXPRESSION = re.compile(
    r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b"
)


def normalize_venue(raw: str) -> VenueResult:
    normalized = re.sub(r"\s+", " ", raw.strip()).upper()
    # Sixteen source rows wrap otherwise conventional venue identifiers in a
    # balanced pair of quotes (for example, "LT1A"). Treat the quotes as source
    # formatting while retaining the untouched value in venue_raw.
    if len(normalized) >= 2 and normalized.startswith('"') and normalized.endswith('"'):
        normalized = normalized[1:-1].strip()
    if not normalized:
        venue_type = "none"
    elif normalized in ONLINE_VALUES:
        venue_type = "online"
    elif normalized in UNKNOWN_VALUES:
        venue_type = "unknown"
    elif normalized in OTHER_VALUES or DATE_EXPRESSION.search(normalized):
        venue_type = "other"
    else:
        venue_type = "physical_room"
    return VenueResult(raw, normalized, venue_type)
