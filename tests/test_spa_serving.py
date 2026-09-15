"""Tests for single-service static frontend serving and SPA fallback routing."""

from pathlib import Path
from starlette.testclient import TestClient

from ntu_room_checker.api.app import create_app
from ntu_room_checker.api.config import ApiSettings


def test_spa_serving_and_fallback(tmp_path: Path) -> None:
    # Set up mock static build directory with index.html and an asset
    static_dir = tmp_path / "dist"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)

    index_content = "<!doctype html><html><head><title>NTU Free Room</title></head><body><div id='root'></div></body></html>"
    (static_dir / "index.html").write_text(index_content, encoding="utf-8")
    (assets_dir / "main-xyz123.js").write_text("console.log('test-asset');", encoding="utf-8")
    (static_dir / "favicon.ico").write_text("fake-icon", encoding="utf-8")

    db_path = tmp_path / "test.db"
    settings = ApiSettings(
        database_path=db_path,
        static_dir=static_dir,
    )

    app = create_app(settings)
    client = TestClient(app)

    # 1. Root route returns index.html without aggressive caching
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "text/html" in root_response.headers.get("content-type", "")
    assert root_response.headers.get("cache-control") == "no-cache"
    assert "NTU Free Room" in root_response.text

    # 2. Client-side routes return index.html
    schedule_response = client.get("/schedule")
    assert schedule_response.status_code == 200
    assert "NTU Free Room" in schedule_response.text

    room_response = client.get("/rooms/LHN-TR+15")
    assert room_response.status_code == 200
    assert "NTU Free Room" in room_response.text

    encoded_room_response = client.get("/rooms/LHN-TR%2B15")
    assert encoded_room_response.status_code == 200
    assert "NTU Free Room" in encoded_room_response.text

    arbitrary_route = client.get("/random-spa-page")
    assert arbitrary_route.status_code == 200
    assert "NTU Free Room" in arbitrary_route.text

    # 3. Static assets have immutable long-lived caching
    asset_response = client.get("/assets/main-xyz123.js")
    assert asset_response.status_code == 200
    assert "console.log('test-asset');" in asset_response.text
    assert asset_response.headers.get("cache-control") == "public, max-age=31536000, immutable"

    # 4. Root static file (e.g. favicon.ico) is served directly
    favicon_response = client.get("/favicon.ico")
    assert favicon_response.status_code == 200
    assert favicon_response.text == "fake-icon"

    # 5. API routes remain functional JSON endpoints
    health_response = client.get("/api/v1/health")
    assert health_response.status_code == 200
    assert health_response.headers.get("content-type") == "application/json"
    data = health_response.json()
    assert "status" in data
    assert data["academic_calendar"] == "available"

    # 6. Unknown API routes MUST return JSON 404, NEVER index.html
    api_404_response = client.get("/api/v1/nonexistent")
    assert api_404_response.status_code == 404
    assert api_404_response.headers.get("content-type") == "application/json"
    err = api_404_response.json()
    assert "error" in err
    assert err["error"]["code"] == "not_found"

    generic_api_404 = client.get("/api/other-route")
    assert generic_api_404.status_code == 404
    assert generic_api_404.headers.get("content-type") == "application/json"
    assert generic_api_404.json()["error"]["code"] == "not_found"

    # 7. Documentation routes continue to work
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200
    assert "swagger" in docs_response.text.lower() or "html" in docs_response.headers.get("content-type", "")

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    assert openapi_response.headers.get("content-type") == "application/json"
    assert "openapi" in openapi_response.json()


def test_api_only_when_static_dir_missing(tmp_path: Path) -> None:
    # When static_dir is not provided or empty, API runs without frontend routes
    db_path = tmp_path / "test.db"
    settings = ApiSettings(database_path=db_path, static_dir=None)

    app = create_app(settings)
    client = TestClient(app)

    # Health works
    health_response = client.get("/api/v1/health")
    assert health_response.status_code == 200

    # Non-API route returns JSON 404 error envelope
    root_response = client.get("/")
    assert root_response.status_code == 404
    assert root_response.headers.get("content-type") == "application/json"
