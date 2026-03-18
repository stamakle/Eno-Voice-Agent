from contextlib import asynccontextmanager
from time import perf_counter
import re

import pathlib
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from english_tech.api.routes.audio import router as audio_router
from english_tech.api.routes.auth import router as auth_router
from english_tech.api.routes.coach import router as coach_router
from english_tech.api.routes.curriculum import router as curriculum_router
from english_tech.api.routes.dashboard import router as dashboard_router
from english_tech.api.routes.health import router as health_router
from english_tech.api.routes.lesson import router as lesson_router
from english_tech.api.routes.live_lesson import router as live_lesson_router
from english_tech.api.routes.metrics import router as metrics_router
from english_tech.api.routes.profile import router as profile_router

from english_tech.config import CORS_ORIGIN_REGEX, DB_AUTO_CREATE
from english_tech.db import ensure_database_connection, init_db
from english_tech.observability.metrics import metrics_store

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

_cors_pattern = re.compile(CORS_ORIGIN_REGEX)


def _add_cors_headers(request: Request, response: JSONResponse) -> JSONResponse:
    """Stamp CORS headers on error responses that bypass CORSMiddleware."""
    origin = request.headers.get("origin", "")
    if origin and _cors_pattern.match(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database_connection()
    if DB_AUTO_CREATE:
        init_db()
    yield


app = FastAPI(title="english_tech", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": "60"},
    )
    return _add_cors_headers(request, response)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=dict(exc.headers or {}),
    )
    return _add_cors_headers(request, response)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
    return _add_cors_headers(request, response)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware('http')
async def record_request_metrics(request: Request, call_next):
    start = perf_counter()
    logger.info(f"Incoming request {request.method} {request.url.path}")
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000
    logger.info(f"Completed request {request.method} {request.url.path} in {duration_ms:.2f}ms with status {response.status_code}")
    metrics_store.record_http(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response

# Mount Static Assets for UI
BASE_DIR = pathlib.Path(__file__).parent.resolve()
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(health_router)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(audio_router, prefix="/api/audio", tags=["audio"])
app.include_router(coach_router, prefix="/api/coach", tags=["coach"])
app.include_router(curriculum_router, prefix="/api/curriculum", tags=["curriculum"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(lesson_router, prefix="/api/lesson", tags=["lesson"])
app.include_router(live_lesson_router, tags=["lesson-live"])
app.include_router(metrics_router, prefix="/api", tags=["ops"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
