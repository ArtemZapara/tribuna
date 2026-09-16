from __future__ import annotations

import json

from http import HTTPStatus
from uuid import UUID

import pytest

from fastapi import Request
from httpx import ASGITransport, AsyncClient
from pydantic import AnyHttpUrl

from tribuna.adapters.api.app import create_app
from tribuna.config import Settings


class DeliberateTestError(RuntimeError):
    """Exercise the public unexpected-error boundary."""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_contract_and_request_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "status": "ok",
        "service": "tribuna-api",
        "version": "0.1.0",
        "environment": "test",
    }
    UUID(response.headers["X-Request-ID"])
    captured = capsys.readouterr()
    records = [
        json.loads(line) for line in captured.out.splitlines() if line.startswith("{")
    ]
    completed = next(
        record for record in records if record["event"] == "request_completed"
    )
    assert completed["method"] == "GET"
    assert completed["path"] == "/api/v1/health"
    assert completed["status_code"] == HTTPStatus.OK
    assert completed["environment"] == "test"
    assert completed["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.anyio
async def test_unknown_route_uses_stable_error_envelope() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/missing")

    assert response.status_code == HTTPStatus.NOT_FOUND
    UUID(response.headers["X-Request-ID"])
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "request_id": response.headers["X-Request-ID"],
        }
    }


@pytest.mark.anyio
async def test_unhandled_error_uses_stable_error_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    @app.get("/boom")
    async def boom(_request: Request) -> None:
        raise DeliberateTestError

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/boom")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred",
            "request_id": response.headers["X-Request-ID"],
        }
    }
    assert "private diagnostic" not in response.text
    assert "private diagnostic" not in capsys.readouterr().out


@pytest.mark.anyio
async def test_request_logs_exclude_query_and_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    @app.post("/inspect")
    async def inspect(_request: Request) -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/inspect?token=query-secret", content="body-secret"
        )

    assert response.status_code == HTTPStatus.OK
    captured = capsys.readouterr().out
    assert "query-secret" not in captured
    assert "body-secret" not in captured


@pytest.mark.anyio
async def test_cors_allows_only_the_configured_origin() -> None:
    app = create_app(
        Settings(
            environment="test",
            web_origin=AnyHttpUrl("https://web.tribuna.test"),
            _env_file=None,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        allowed = await client.get(
            "/api/v1/health", headers={"Origin": "https://web.tribuna.test"}
        )
        rejected = await client.get(
            "/api/v1/health", headers={"Origin": "https://other.test"}
        )

    assert allowed.headers["access-control-allow-origin"] == "https://web.tribuna.test"
    assert "access-control-allow-origin" not in rejected.headers


def test_openapi_contains_health_contract() -> None:
    schema = create_app(Settings(environment="test", _env_file=None)).openapi()

    operation = schema["paths"]["/api/v1/health"]["get"]
    assert operation["operationId"] == "getHealth"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]
