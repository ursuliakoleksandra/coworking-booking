import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings, settings
from app.routers import admin, auth, bookings, health, home, rooms

logger = logging.getLogger("app")
STATIC_DIR = Path(__file__).parent / "static"


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = uuid.uuid4().hex[:8]
    logger.error(
        "Unhandled error %s on %s %s", error_id, request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутрішня помилка сервера. Спробуйте пізніше.", "error_id": error_id},
    )


def create_app(app_settings: Settings | None = None) -> FastAPI:
    cfg = app_settings or settings
    app = FastAPI(
        title=cfg.app_name,
        debug=cfg.debug,
        docs_url="/docs" if cfg.enable_docs else None,
        redoc_url="/redoc" if cfg.enable_docs else None,
        openapi_url="/openapi.json" if cfg.enable_docs else None,
    )

    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(home.router)
    app.include_router(admin.router)
    app.include_router(rooms.router)
    app.include_router(bookings.router)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def ui_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
