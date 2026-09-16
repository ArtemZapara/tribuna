"""FastAPI application composition root."""

from __future__ import annotations

import time

from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from tribuna import __version__
from tribuna.adapters.api.errors import error_response, install_error_handlers
from tribuna.adapters.api.routes.health import router as health_router
from tribuna.config import Settings, get_settings
from tribuna.observability import configure_logging, get_logger

RequestHandler = Callable[[Request], Awaitable[Response]]
Middleware = Callable[[Request, RequestHandler], Awaitable[Response]]


def request_context_middleware(settings: Settings) -> Middleware:
    """Build middleware that adds request IDs and one structured access log."""

    async def middleware(request: Request, call_next: RequestHandler) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started_ns = time.perf_counter_ns()
        logger = get_logger()
        try:
            response = await call_next(request)
        except Exception as error:
            logger.exception(
                "request_failed",
                service="tribuna-api",
                environment=settings.environment,
                method=request.method,
                path=request.url.path,
                error_type=type(error).__name__,
                exc_info=False,
            )
            response = error_response(
                request=request,
                status_code=500,
                code="internal_error",
                message="An unexpected error occurred",
            )

        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        logger.info(
            "request_completed",
            service="tribuna-api",
            environment=settings.environment,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 3),
        )
        structlog.contextvars.clear_contextvars()
        return response

    return middleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application using validated settings."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    app = FastAPI(
        title="Tribuna API",
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = resolved_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(resolved_settings.web_origin).rstrip("/")],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
    )
    app.middleware("http")(request_context_middleware(resolved_settings))
    install_error_handlers(app)
    app.include_router(health_router)
    return app
