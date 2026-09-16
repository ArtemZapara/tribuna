"""Stable API error responses."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def request_id_for(request: Request) -> str:
    """Return the request identifier assigned by middleware."""
    return str(getattr(request.state, "request_id", "unknown"))


def error_response(
    *, request: Request, status_code: int, code: str, message: str
) -> JSONResponse:
    """Create the public API error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id_for(request),
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    """Install handlers for errors FastAPI resolves before request middleware."""

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, error: HTTPException) -> JSONResponse:
        code = (
            "not_found" if error.status_code == HTTPStatus.NOT_FOUND else "http_error"
        )
        message = error.detail if isinstance(error.detail, str) else "Request failed"
        return error_response(
            request=request,
            status_code=error.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        _ = error
        return error_response(
            request=request,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="request_validation_error",
            message="Request validation failed",
        )
