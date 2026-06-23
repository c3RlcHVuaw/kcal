from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from kcal_tracker.api.routes import router
from kcal_tracker.config import settings, validate_production_settings
from kcal_tracker.logging import configure_logging

configure_logging(settings.log_level, settings.log_format)
logger = logging.getLogger(__name__)
STARTED_AT = time.time()


def _interactive_docs_urls(*, is_production: bool) -> tuple[str | None, str | None]:
    if is_production:
        return None, None
    return "/docs", "/redoc"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_production_settings()
    yield


docs_url, redoc_url = _interactive_docs_urls(is_production=settings.is_production)
app = FastAPI(
    title="Kcal Tracker API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
)
app.include_router(router)

WEBAPP_STATIC_DIR = Path(__file__).resolve().parent / "webapp_static"
LANDING_STATIC_DIR = Path(__file__).resolve().parent / "landing_static"
app.mount("/app/static", StaticFiles(directory=WEBAPP_STATIC_DIR), name="webapp-static")
app.mount("/landing/static", StaticFiles(directory=LANDING_STATIC_DIR), name="landing-static")


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def landing() -> FileResponse:
    return FileResponse(LANDING_STATIC_DIR / "index.html")


@app.api_route("/bot-dlya-podscheta-kaloriy", methods=["GET", "HEAD"], include_in_schema=False)
async def calorie_counter_bot_landing() -> FileResponse:
    return FileResponse(LANDING_STATIC_DIR / "bot-dlya-podscheta-kaloriy.html")


@app.api_route("/kalorii-po-foto", methods=["GET", "HEAD"], include_in_schema=False)
async def photo_calorie_landing() -> FileResponse:
    return FileResponse(LANDING_STATIC_DIR / "kalorii-po-foto.html")


@app.api_route("/dnevnik-pitaniya-telegram", methods=["GET", "HEAD"], include_in_schema=False)
async def telegram_food_diary_landing() -> FileResponse:
    return FileResponse(LANDING_STATIC_DIR / "dnevnik-pitaniya-telegram.html")


@app.api_route("/app", methods=["GET", "HEAD"], include_in_schema=False)
async def telegram_webapp() -> FileResponse:
    return FileResponse(WEBAPP_STATIC_DIR / "index.html")


@app.get("/metrics", include_in_schema=False)
async def metrics() -> PlainTextResponse:
    uptime_seconds = max(time.time() - STARTED_AT, 0)
    content = "\n".join(
        [
            "# HELP kcal_app_info Application build metadata.",
            "# TYPE kcal_app_info gauge",
            f'kcal_app_info{{version="{app.version}",env="{settings.app_env}"}} 1',
            "# HELP kcal_uptime_seconds Seconds since application process start.",
            "# TYPE kcal_uptime_seconds gauge",
            f"kcal_uptime_seconds {uptime_seconds:.3f}",
            "# HELP kcal_health Static application health indicator.",
            "# TYPE kcal_health gauge",
            "kcal_health 1",
            "",
        ]
    )
    return PlainTextResponse(content, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /app\n"
        "Disallow: /webapp/\n"
        "Disallow: /users/\n"
        "Disallow: /integrations/\n"
        "Sitemap: https://kcal-bot.ru/sitemap.xml\n",
        media_type="text/plain; charset=utf-8",
    )


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        "    <loc>https://kcal-bot.ru/</loc>\n"
        "    <lastmod>2026-06-05</lastmod>\n"
        "    <changefreq>weekly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "  <url>\n"
        "    <loc>https://kcal-bot.ru/bot-dlya-podscheta-kaloriy</loc>\n"
        "    <lastmod>2026-06-05</lastmod>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.8</priority>\n"
        "  </url>\n"
        "  <url>\n"
        "    <loc>https://kcal-bot.ru/kalorii-po-foto</loc>\n"
        "    <lastmod>2026-06-05</lastmod>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.8</priority>\n"
        "  </url>\n"
        "  <url>\n"
        "    <loc>https://kcal-bot.ru/dnevnik-pitaniya-telegram</loc>\n"
        "    <lastmod>2026-06-05</lastmod>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.8</priority>\n"
        "  </url>\n"
        "</urlset>\n",
        media_type="application/xml; charset=utf-8",
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "Unhandled request error request_id=%s method=%s path=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - started_at) * 1000
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), payment=()")
    if request.url.path.startswith(("/app/static/", "/landing/static/")):
        response.headers.setdefault("Cache-Control", "public, max-age=604800, immutable")
    logger.info(
        "Request completed request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
