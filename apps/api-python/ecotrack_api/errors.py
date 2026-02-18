"""Centralized error handling for EcoTrack API."""
from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class EcoTrackAPIError(Exception):
    """Base API error."""

    def __init__(
        self, message: str, status_code: int = 500, detail: str = ""
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.detail = detail


class NotFoundError(EcoTrackAPIError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            f"{resource} not found: {identifier}",
            status_code=404,
            detail=f"The requested {resource} with identifier '{identifier}' does not exist.",
        )


class ValidationError(EcoTrackAPIError):
    """Request validation error."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422, detail=message)


class ServiceUnavailableError(EcoTrackAPIError):
    """Downstream service unavailable."""

    def __init__(self, service: str) -> None:
        super().__init__(
            f"Service unavailable: {service}",
            status_code=503,
            detail=f"The upstream service '{service}' is currently unavailable. Please retry later.",
        )


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application."""

    @app.exception_handler(EcoTrackAPIError)
    async def ecotrack_error_handler(
        request: Request, exc: EcoTrackAPIError
    ) -> JSONResponse:
        logger.error(
            "api.error",
            error=exc.message,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "detail": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "api.unhandled_error",
            error=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if getattr(app, "debug", False) else "",
                "status_code": 500,
            },
        )
