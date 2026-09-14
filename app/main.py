from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.v1 import (
    admin_router,
    auth_router,
    availability_router,
    consultation_router,
    doctor_router,
)
from app.api.v1.prescription import router as prescription_router
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.redis import get_redis, close_redis
from app.core.rate_limit import RedisRateLimitMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


settings = get_settings()

logger = structlog.get_logger()


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                headers.extend(
                    [
                        (
                            b"x-content-type-options",
                            b"nosniff",
                        ),
                        (
                            b"x-frame-options",
                            b"DENY",
                        ),
                        (
                            b"referrer-policy",
                            b"no-referrer",
                        ),
                        (
                            b"permissions-policy",
                            b"camera=(), microphone=(), geolocation=()",
                        ),
                    ]
                )

                forwarded_proto = None

                for header_name, header_value in headers:
                    if header_name.lower() == b"x-forwarded-proto":
                        forwarded_proto = header_value.lower()
                        break

                if forwarded_proto == b"https":
                    headers.append(
                        (
                            b"strict-transport-security",
                            b"max-age=31536000; includeSubDomains",
                        )
                    )

                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = None

        for key, value in scope.get("headers", []):
            if key.lower() == b"x-request-id":
                try:
                    request_id = value.decode("utf-8")
                except UnicodeDecodeError:
                    request_id = None
                break

        if not request_id:
            request_id = str(uuid.uuid4())

        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                headers.append(
                    (
                        b"x-request-id",
                        request_id.encode("utf-8"),
                    )
                )

                message["headers"] = headers

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

        finally:
            duration_ms = (
                time.perf_counter() - start
            ) * 1000

            logger.info(
                "http_request_completed",
                request_id=request_id,
                method=scope.get("method"),
                path=scope.get("path"),
                duration_ms=round(duration_ms, 2),
            )


def configure_telemetry(app: FastAPI) -> None:
    """Configure OpenTelemetry when explicitly enabled."""

    if not settings.otel_enabled:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
        }
    )

    provider = TracerProvider(
        resource=resource
    )

    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=True,
    )

    provider.add_span_processor(
        BatchSpanProcessor(exporter)
    )

    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app
    )

    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        environment=settings.app_env,
    )

    yield

    await close_redis()

    logger.info(
        "application_shutdown"
    )


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Production-grade backend for Amrutam telemedicine."
    ),
    debug=settings.debug,
    lifespan=lifespan,
)


configure_telemetry(app)


# ------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------

app.add_middleware(
    RedisRateLimitMiddleware,
    requests=60,
    window_seconds=60,
    exempt_paths={"/health", "/ready", "/metrics", "/docs", "/openapi.json"},
)

app.add_middleware(
    SecurityHeadersMiddleware,
)

app.add_middleware(
    RequestContextMiddleware,
)

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=["*"],
    )


# ------------------------------------------------------------------
# API routers
# ------------------------------------------------------------------

app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    doctor_router,
    prefix="/api/v1",
)

app.include_router(
    availability_router,
    prefix="/api/v1",
)

app.include_router(
    consultation_router,
    prefix="/api/v1",
)

app.include_router(
    prescription_router,
    prefix="/api/v1",
)

app.include_router(
    admin_router,
    prefix="/api/v1",
)


# ------------------------------------------------------------------
# Prometheus instrumentation
# ------------------------------------------------------------------

instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    excluded_handlers={
        "/metrics",
        "/health",
        "/ready",
    },
)

instrumentator.instrument(app)
instrumentator.expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
)


# ------------------------------------------------------------------
# System endpoints
# ------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "metrics": "/metrics",
    }


@app.get("/health")
async def health():
    """
    Liveness probe.

    The process is alive when this endpoint responds successfully.
    Dependency failures are intentionally handled by /ready instead.
    """
    return {
        "status": "healthy",
    }


@app.get("/ready")
async def readiness():
    """
    Readiness probe for PostgreSQL and Redis.
    """

    postgres_status = "ok"
    redis_status = "ok"

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("SELECT 1")
            )

    except Exception as exc:
        postgres_status = "error"

        logger.error(
            "readiness_postgres_failed",
            error=str(exc),
        )

    try:
        redis = await get_redis()
        await redis.ping()

    except Exception as exc:
        redis_status = "error"

        logger.error(
            "readiness_redis_failed",
            error=str(exc),
        )

    ready = (
        postgres_status == "ok"
        and redis_status == "ok"
    )

    if not ready:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "dependencies": {
                    "postgres": postgres_status,
                    "redis": redis_status,
                },
            },
        )

    return {
        "status": "ready",
        "dependencies": {
            "postgres": postgres_status,
            "redis": redis_status,
        },
    }


# ------------------------------------------------------------------
# Global exception handler
# ------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    request_id = getattr(
        request.state,
        "request_id",
        str(uuid.uuid4()),
    )

    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )



