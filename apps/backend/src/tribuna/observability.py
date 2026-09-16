"""Structured logging configuration for the backend boundary."""

from __future__ import annotations

import logging
import sys

from typing import cast

import structlog

from structlog.typing import FilteringBoundLogger

from tribuna.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure deterministic JSON logs for the current process."""
    level = getattr(logging, settings.log_level)
    logging.basicConfig(
        stream=sys.stdout, format="%(message)s", level=level, force=True
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger() -> FilteringBoundLogger:
    """Return a structured logger configured by the application factory."""
    return cast(FilteringBoundLogger, structlog.get_logger("tribuna-api"))
