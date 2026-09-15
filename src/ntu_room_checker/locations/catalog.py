"""Human-readable location rules backed by docs/room-locations.md."""

from .models import Location


LOCATIONS: tuple[Location, ...] = (
    Location(
        id="the-arc", name="The Arc", short_name="Arc",
        official_name="Learning Hub North",
        aliases=("LHN", "Learning Hub North"), patterns=(r"^LHN-",),
    ),
    Location(
        id="north-spine", name="North Spine", short_name="North Spine",
        official_name=None, aliases=("NS",), patterns=(),
        explicit_rooms=frozenset(
            {"TCT-LT", "TRX43", "TRX44", "LT1A", "LT2A", "LT19A"}
            | {f"LT{n}" for n in range(1, 21)}
            | {f"TR+{n}" for n in (*range(1, 10), *range(15, 24), *range(29, 38))}
        ),
    ),
    Location(
        id="the-hive", name="The Hive", short_name="Hive",
        official_name="Learning Hub South",
        aliases=("LHS", "Learning Hub South"), patterns=(r"^LHS-",),
    ),
    Location(
        id="south-spine", name="South Spine", short_name="South Spine",
        official_name=None, aliases=("SS",), patterns=(),
        explicit_rooms=frozenset(
            {"LKC-LT", "TR102", "TR103", "TR120", "TR121"}
            | {f"LT{n}" for n in range(22, 30)}
            | {f"TR+{n}" for n in (
                *range(61, 70), *range(77, 81), *range(87, 97),
                *range(106, 115), 151, 152, 153, 154, 159, 160, 165, 166,
            )}
        ),
    ),
)

_BY_ID = {location.id: location for location in LOCATIONS}


def get_location(location_id: str) -> Location | None:
    return _BY_ID.get(location_id)
