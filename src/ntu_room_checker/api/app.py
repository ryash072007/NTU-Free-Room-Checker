"""FastAPI application factory."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ntu_room_checker.api.config import ApiSettings
from ntu_room_checker.api.routes import calendar, health, rooms

API_PREFIX = "/api/v1"


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
            "code": "http_error", "message": str(error.detail)
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
    return application


app = create_app()
