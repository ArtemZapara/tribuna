"""Health endpoint."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from tribuna import __version__
from tribuna.config import Environment, Settings

router = APIRouter(prefix="/api/v1", tags=["system"])


class HealthResponse(BaseModel):
    """Liveness response for the API process."""

    status: Literal["ok"]
    service: Literal["tribuna-api"]
    version: str
    environment: Environment


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
async def get_health(request: Request) -> HealthResponse:
    """Report process liveness without testing deferred dependencies."""
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service="tribuna-api",
        version=__version__,
        environment=settings.environment,
    )
