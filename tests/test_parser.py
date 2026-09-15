from pathlib import Path

from ntu_room_checker.scraper.parser import parse_schedule_html


FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_module_metadata_and_expands_rowspans() -> None:
    html = (FIXTURES / "schedule_with_inheritance.html").read_text(encoding="utf-8")

    entries = parse_schedule_html(html)

    assert len(entries) == 3
    assert entries[0].course_code == "TEST1001"
    assert entries[0].course_title == "REPRESENTATIVE MODULE"
    assert entries[0].academic_units == "3.0 AU"
    assert entries[0].course_remark == "Module-level note"
    assert entries[1].index_number == "12345"
    assert entries[1].class_type == "TUT"
    assert entries[1].group_name == "GP1"
    assert entries[1].day == "WED"
    assert entries[1].time == "1430-1530"
    assert entries[1].venue == "TR+2"
    assert entries[2].remark == "Odd Week"


def test_inherits_blank_class_identity_cells() -> None:
    html = """
    <table><tr><td>AB1234</td><td>Title</td><td>2.0 AU</td></tr></table>
    <table><tr><th>INDEX</th><th>TYPE</th><th>GROUP</th><th>DAY</th><th>TIME</th><th>VENUE</th><th>REMARK</th></tr>
    <tr><td>10001</td><td>LEC</td><td>LE1</td><td>MON</td><td>0900-1000</td><td>LT1</td><td></td></tr>
    <tr><td></td><td></td><td></td><td>THU</td><td>0900-1000</td><td>LT2</td><td>Week 7</td></tr></table>
    """

    entries = parse_schedule_html(html)

    assert (entries[1].index_number, entries[1].class_type, entries[1].group_name) == (
        "10001", "LEC", "LE1"
    )
    assert entries[1].day == "THU"
