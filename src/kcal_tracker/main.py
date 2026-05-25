from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kcal_tracker.api.routes import router
from kcal_tracker.config import settings, validate_production_settings
from kcal_tracker.logging import configure_logging

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_production_settings()
    yield


app = FastAPI(title="Kcal Tracker API", version="0.1.0", lifespan=lifespan)
app.include_router(router)

WEBAPP_STATIC_DIR = Path(__file__).resolve().parent / "webapp_static"
app.mount("/app/static", StaticFiles(directory=WEBAPP_STATIC_DIR), name="webapp-static")


@app.get("/app", include_in_schema=False)
async def telegram_webapp() -> FileResponse:
    return FileResponse(WEBAPP_STATIC_DIR / "index.html")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "Unhandled request error method=%s path=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "Request completed method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
