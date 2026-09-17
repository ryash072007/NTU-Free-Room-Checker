from pathlib import Path

from ntu_room_checker.scraper.facility_list import (
    FacilityListStorage,
    parse_facility_list_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_facility_rows_and_splits_descriptive_names() -> None:
    html = (FIXTURES / "facility_list_sample.html").read_text(encoding="utf-8")

    entries = parse_facility_list_html(html)

    assert len(entries) == 5
    lt1, tct, recep, tutorial_room, maybe_row = entries

    assert lt1.facility_code == "LT1"
    assert lt1.capacity == 502
    assert lt1.bookable_by_staff is True
    assert lt1.bookable_by_student_orgs is True

    assert tct.facility_code == "TCT-LT"
    assert tct.capacity == 306
    assert tct.bookable_by_student_orgs is False


def test_blank_capacity_is_unparsed_not_guessed() -> None:
    entries = parse_facility_list_html((FIXTURES / "facility_list_sample.html").read_text(encoding="utf-8"))
    recep = entries[2]
    assert recep.facility_code == "RECEP RM"
    assert recep.capacity_raw == ""
    assert recep.capacity is None
    assert recep.bookable_by_staff is False
    assert recep.bookable_by_student_orgs is False


def test_descriptive_suffix_is_split_off_the_facility_code() -> None:
    entries = parse_facility_list_html((FIXTURES / "facility_list_sample.html").read_text(encoding="utf-8"))
    tutorial_room = entries[3]
    assert tutorial_room.facility_code == "LHN-TR+56"
    assert tutorial_room.facility_name_raw == "LHN-TR+56 Derek Goh Bak Heng Tutorial Room"


def test_non_yes_no_bookable_cell_is_unparsed_not_guessed() -> None:
    entries = parse_facility_list_html((FIXTURES / "facility_list_sample.html").read_text(encoding="utf-8"))
    maybe_row = entries[4]
    assert maybe_row.bookable_by_staff_raw == "MAYBE"
    assert maybe_row.bookable_by_staff is None
    assert maybe_row.bookable_by_student_orgs is True


def test_header_row_and_short_rows_are_excluded() -> None:
    entries = parse_facility_list_html((FIXTURES / "facility_list_sample.html").read_text(encoding="utf-8"))
    assert all(entry.spine.upper() != "SPINES" for entry in entries)


def test_zero_parsed_rows_raises_instead_of_silently_succeeding(tmp_path: Path) -> None:
    import pytest

    import ntu_room_checker.scraper.facility_list as module
    from ntu_room_checker.scraper.facility_list import run_facility_list_scrape

    def _empty_fetch(url: str = "", *, timeout: float = 30.0) -> str:
        return "<html><body>no table here</body></html>"

    original = module.fetch_facility_list_html
    module.fetch_facility_list_html = _empty_fetch
    try:
        with pytest.raises(ValueError, match="zero facility rows"):
            run_facility_list_scrape(tmp_path / "facility.db")
    finally:
        module.fetch_facility_list_html = original

    with FacilityListStorage(tmp_path / "facility.db") as storage:
        assert storage.latest_completed_run() is None


def test_storage_records_run_lifecycle_and_persists_raw_and_parsed_fields(tmp_path: Path) -> None:
    entries = parse_facility_list_html((FIXTURES / "facility_list_sample.html").read_text(encoding="utf-8"))
    db_path = tmp_path / "facility.db"
    with FacilityListStorage(db_path) as storage:
        run_id = storage.start_run("https://example.test/facility-list")
        count = storage.save_entries(run_id, entries)
        assert count == 5
        assert storage.latest_completed_run() == run_id

        row = storage.connection.execute(
            "SELECT * FROM facility_list_entries WHERE run_id=? ORDER BY row_index LIMIT 1", (run_id,)
        ).fetchone()
        assert row["facility_code"] == "LT1"
        assert row["capacity"] == 502
        assert row["bookable_by_staff"] == 1

        maybe_row = storage.connection.execute(
            "SELECT * FROM facility_list_entries WHERE run_id=? AND facility_code='LHN-TR+99'", (run_id,)
        ).fetchone()
        assert maybe_row["bookable_by_staff_raw"] == "MAYBE"
        assert maybe_row["bookable_by_staff"] is None


def test_failed_run_records_error_and_is_not_latest_completed(tmp_path: Path) -> None:
    db_path = tmp_path / "facility.db"
    with FacilityListStorage(db_path) as storage:
        run_id = storage.start_run("https://example.test/facility-list")
        storage.fail_run(run_id, "boom")
        assert storage.latest_completed_run() is None
        status = storage.connection.execute(
            "SELECT status, error_message FROM facility_list_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert status["status"] == "failed"
        assert status["error_message"] == "boom"
