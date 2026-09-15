"""FastAPI application factory."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

from ntu_room_checker.api.config import ApiSettings
from ntu_room_checker.api.routes import calendar, health, locations, rooms

API_PREFIX = "/api/v1"


class HashedStaticFiles(StaticFiles):
    """Static asset files with aggressive immutable caching."""

    def file_response(self, *args: object, **kwargs: object) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    configured = settings or ApiSettings.from_environment()
    application = FastAPI(
        title="NTU Free Room Checker API",
        version="1.0.0",
        description=(
            "Versioned access to normalized NTU room schedules and conservative "
            "availability decisions. `is_free=null` means availability is not confidently known."
        ),
    )
    application.state.settings = configured
    if configured.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(configured.cors_origins),
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Accept", "Content-Type"],
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": {
                "code": "validation_error",
                "message": "Request parameters are invalid.",
                "details": details,
            }},
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        detail = error.detail if isinstance(error.detail, dict) else {
            "code": "not_found" if error.status_code == 404 else "http_error",
            "message": str(error.detail),
        }
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {
                "code": detail.get("code", "http_error"),
                "message": detail.get("message", "Request failed."),
                "details": detail.get("details", []),
            }},
            headers=error.headers,
        )

    application.include_router(health.router, prefix=API_PREFIX)
    application.include_router(calendar.router, prefix=API_PREFIX)
    application.include_router(rooms.router, prefix=API_PREFIX)
    application.include_router(locations.router, prefix=API_PREFIX)

    static_dir = configured.static_dir
    if static_dir and (static_dir / "index.html").is_file():
        resolved_static = static_dir.resolve()
        index_file = resolved_static / "index.html"
        assets_dir = resolved_static / "assets"
        if assets_dir.is_dir():
            application.mount(
                "/assets",
                HashedStaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @application.get("/", include_in_schema=False)
        async def serve_spa_root() -> Response:
            return FileResponse(
                index_file,
                media_type="text/html",
                headers={"Cache-Control": "no-cache"},
            )

        @application.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa_fallback(full_path: str) -> Response:
            normalized = full_path.strip("/")
            if normalized == "api" or normalized.startswith("api/"):
                raise StarletteHTTPException(
                    status_code=404,
                    detail={"code": "not_found", "message": f"API endpoint /{full_path} not found."},
                )

            candidate = (resolved_static / full_path).resolve()
            if candidate.is_file() and resolved_static in candidate.parents:
                return FileResponse(candidate)

            return FileResponse(
                index_file,
                media_type="text/html",
                headers={"Cache-Control": "no-cache"},
            )

    return application


app = create_app()
