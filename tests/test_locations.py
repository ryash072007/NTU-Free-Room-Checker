from ntu_room_checker.locations import classify_room, get_location, rooms_by_location


def test_lhn_room_maps_to_the_arc_without_changing_identifier() -> None:
    room = "LHN-TR+17"
    assert classify_room(room) == get_location("the-arc")
    assert rooms_by_location([room])["the-arc"] == [room]


def test_plain_tr17_is_north_spine_and_not_the_arc() -> None:
    assert classify_room("TR+17") == get_location("north-spine")
    assert classify_room("TR+17") != classify_room("LHN-TR+17")


def test_hive_and_south_spine_are_distinct() -> None:
    assert classify_room("LHS-TR+24") == get_location("the-hive")
    assert classify_room("TR+61") == get_location("south-spine")


def test_unknown_and_substring_codes_remain_unmapped() -> None:
    assert classify_room("UNKNOWN-TR+17") is None
    assert classify_room("NIE-LHN-B1-01") is None
    assert classify_room("TR+10") is None
