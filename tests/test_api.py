from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from ntu_room_checker.api.app import create_app
from ntu_room_checker.api.config import ApiSettings
from ntu_room_checker.api.time import singapore_now
from ntu_room_checker.normalization.runner import normalize_database
from ntu_room_checker.scraper.models import AcademicTerm, ProgrammeOption, ScheduleEntry
from ntu_room_checker.scraper.storage import ScheduleStorage


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    path = tmp_path / "api.db"
    term = AcademicTerm("2026;1", "Acad Yr 2026 Semester 1", "2026", "1")
    entries = [
        ScheduleEntry("AB1001", "FIRST", "3.0 AU", "", "10001", "TUT", "G1", "TUE", "1430-1530", "LHN-TR+15", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1002", "NEXT", "3.0 AU", "", "10002", "TUT", "G2", "TUE", "1700-1800", "LHN-TR+15", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1003", "OTHER", "3.0 AU", "", "10003", "TUT", "G3", "TUE", "1000-1100", "LHN-TR+16", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1004", "UNION", "3.0 AU", "", "10004", "TUT", "G4", "FRI", "1000-1200", "TR+15", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1005", "UNPARSED", "3.0 AU", "", "10005", "TUT", "G5", "", "unknown", "TR+17", "Teaching Wk1-13", {}),
        ScheduleEntry("AB1006", "CONTAINS", "3.0 AU", "", "10006", "TUT", "G6", "TUE", "1200-1300", "NIE-LHN-B1-01", "Teaching Wk1-13", {}),
    ]
    with ScheduleStorage(path) as storage:
        run_id = storage.start_run("https://example.test", term, resume=False)
        storage.register_programmes(run_id, [ProgrammeOption("P1", "Programme")])
        selection = storage.remaining_programmes(run_id)[0]
        storage.save_entries(run_id, selection["id"], entries)
        storage.finish_run(run_id)
    normalize_database(path)
    return path


@pytest.fixture
def client(api_db: Path) -> TestClient:
    return TestClient(create_app(ApiSettings(api_db, ("http://localhost:5173",))))


def test_health_checks_normalized_database_without_exposing_path(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "database": "available", "academic_calendar": "available"
    }
    assert "api.db" not in response.text


@pytest.mark.parametrize(
    ("value", "period", "week"),
    [
        ("2026-09-15", "teaching_week", 6),
        ("2026-09-28", "recess_week", None),
        ("2026-08-10", "teaching_week", 1),
    ],
)
def test_calendar_endpoint(value: str, period: str, week: int | None, client: TestClient) -> None:
    response = client.get(f"/api/v1/calendar/{value}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["period_type"] == period
    assert payload["teaching_week"] == week


def test_calendar_exposes_students_union_exception(client: TestClient) -> None:
    payload = client.get("/api/v1/calendar/2026-09-04").json()
    assert payload["exceptions"][0]["id"] == "students_union_day_2026"
    assert payload["exceptions"][0]["start"] == "10:30"


@pytest.mark.parametrize(
    ("query", "first"),
    [
        ("LHN-TR+15", "LHN-TR+15"),
        ("lhn-tr", "LHN-TR+15"),
        ("B1-01", "NIE-LHN-B1-01"),
        ("LHN", "LHN-TR+15"),
    ],
)
def test_room_search_ranking_and_case_insensitivity(
    query: str, first: str, client: TestClient
) -> None:
    payload = client.get("/api/v1/rooms", params={"q": query}).json()
    assert payload["rooms"][0]["name"] == first


def test_room_search_limit_and_no_match(client: TestClient) -> None:
    limited = client.get("/api/v1/rooms", params={"q": "LHN", "limit": 1}).json()
    missing = client.get("/api/v1/rooms", params={"q": "NO-SUCH-ROOM"}).json()
    assert limited["count"] == 1
    assert missing == {"rooms": [], "count": 0}


def test_schedule_supports_url_encoded_plus_and_explicit_intervals(client: TestClient) -> None:
    room = quote("LHN-TR+15", safe="")
    response = client.get(f"/api/v1/rooms/{room}/schedule", params={"date": "2026-09-15"})
    assert response.status_code == 200
    meeting = response.json()["meetings"][0]
    assert meeting["course_code"] == "AB1001"
    assert meeting["scheduled_start"] == meeting["effective_start"] == "14:30"
    assert meeting["applicability"] == "applicable"


def test_schedule_exception_and_unknown_room(client: TestClient) -> None:
    uncertain = client.get(
        "/api/v1/rooms/TR%2B15/schedule", params={"date": "2026-09-04"}
    )
    missing = client.get(
        "/api/v1/rooms/NOPE/schedule", params={"date": "2026-09-15"}
    )
    assert uncertain.json()["status"] == "uncertain"
    assert uncertain.json()["meetings"][0]["uncertain_intervals"] == [
        {"start": "10:30", "end": "12:00"}
    ]
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "unknown_room"


def test_availability_free_occupied_and_boundary_adjacency(client: TestClient) -> None:
    occupied = client.get("/api/v1/rooms/LHN-TR%2B15/availability", params={
        "date": "2026-09-15", "time": "14:30", "duration": 60,
    }).json()
    adjacent = client.get("/api/v1/rooms/LHN-TR%2B15/availability", params={
        "date": "2026-09-15", "time": "15:30", "duration": 60,
    }).json()
    assert occupied["status"] == "occupied" and occupied["is_free"] is False
    assert adjacent["status"] == "free" and adjacent["is_free"] is True
    assert adjacent["free_until"] == "17:00"
    assert adjacent["free_duration_minutes"] == 90


def test_availability_uncertain_and_unknown_room(client: TestClient) -> None:
    uncertain = client.get("/api/v1/rooms/TR%2B15/availability", params={
        "date": "2026-09-04", "time": "11:00", "duration": 60,
    }).json()
    missing = client.get("/api/v1/rooms/NOPE/availability", params={
        "date": "2026-09-15", "time": "11:00", "duration": 60,
    })
    assert uncertain["status"] == "uncertain"
    assert uncertain["is_free"] is None
    assert uncertain["reason_codes"] == ["population_scope_unknown"]
    assert missing.status_code == 404


@pytest.mark.parametrize(
    ("value", "status"),
    [
        ("2026-09-28", "regular_timetable_not_applicable"),
        ("2026-11-16", "regular_timetable_not_authoritative"),
        ("2026-08-10", "regular_timetable_not_authoritative"),
    ],
)
def test_availability_non_regular_calendar_states(
    value: str, status: str, client: TestClient
) -> None:
    payload = client.get("/api/v1/rooms/LHN-TR%2B15/availability", params={
        "date": value, "time": "11:00", "duration": 60,
    }).json()
    assert payload["status"] == status
    assert payload["is_free"] is None


def test_free_rooms_separates_confident_and_uncertain(client: TestClient) -> None:
    normal = client.get("/api/v1/rooms/free", params={
        "date": "2026-09-15", "time": "14:30", "duration": 60,
        "include_uncertain": True, "limit": 20,
    }).json()
    union = client.get("/api/v1/rooms/free", params={
        "date": "2026-09-04", "time": "11:00", "duration": 60,
        "include_uncertain": True, "limit": 20,
    }).json()
    assert "LHN-TR+15" not in {item["room"] for item in normal["rooms"]}
    assert "TR+17" in {item["room"] for item in normal["uncertain_rooms"]}
    assert "TR+15" not in {item["room"] for item in union["rooms"]}
    assert "TR+15" in {item["room"] for item in union["uncertain_rooms"]}


def test_free_rooms_limit_and_default_omits_uncertain(client: TestClient) -> None:
    payload = client.get("/api/v1/rooms/free", params={
        "date": "2026-09-04", "time": "11:00", "duration": 60, "limit": 1,
    }).json()
    assert len(payload["rooms"]) == 1
    assert payload["uncertain_rooms"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/calendar/not-a-date",
        "/api/v1/rooms/free?date=2026-09-15&time=1430&duration=60",
        "/api/v1/rooms/free?date=2026-09-15&time=14:30&duration=0",
        "/api/v1/rooms/free?date=2026-09-15&time=23:30&duration=60",
        "/api/v1/rooms/free?date=2026-09-15&time=14:30&duration=60&limit=101",
    ],
)
def test_invalid_inputs_use_structured_422(path: str, client: TestClient) -> None:
    response = client.get(path)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_route_uses_structured_404(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_openapi_documents_versioned_routes_and_nullable_is_free(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/rooms/free" in schema["paths"]
    assert "/api/v1/rooms/{room}/availability" in schema["paths"]
    assert "RoomAvailabilityResponse" in schema["components"]["schemas"]


def test_singapore_now_is_timezone_aware() -> None:
    current = singapore_now()
    assert current.utcoffset() == timedelta(hours=8)
