"""Register global exception handlers on the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from studio.adapters.inbound.http.mappers.exception_mapper import DEFAULT_STATUS, STATUS_MAP
from studio.adapters.inbound.http.mappers.validation_mapper import map_validation_report
from studio.domain.exceptions.app_error import AppError
from studio.domain.exceptions.validation_failed_error import ValidationFailedError

__all__ = ["register_exception_handler"]


def register_exception_handler(app: FastAPI) -> None:
    """Install a single handler mapping domain errors to HTTP responses."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        status = STATUS_MAP.get(type(exc), DEFAULT_STATUS)
        content: dict[str, object] = {"error": type(exc).__name__, "detail": str(exc)}
        if isinstance(exc, ValidationFailedError):
            content["report"] = map_validation_report(exc.report).model_dump()
        return JSONResponse(status_code=status, content=content)
