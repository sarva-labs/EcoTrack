"""API middleware for EcoTrack."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with timing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = (time.perf_counter() - start_time) * 1000

        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration, 2),
            client=request.client.host if request.client else "unknown",
        )

        response.headers["X-Request-Duration-Ms"] = str(round(duration, 2))
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter.

    Tracks requests per client IP over a sliding 60-second window and
    returns ``429 Too Many Requests`` when the limit is exceeded.
    """

    def __init__(self, app: object, requests_per_minute: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.requests_per_minute = requests_per_minute
        self._counters: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old entries outside the 60-second window
        self._counters[client_ip] = [
            t for t in self._counters[client_ip] if now - t < 60
        ]

        if len(self._counters[client_ip]) >= self.requests_per_minute:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_minute} requests per minute",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        self._counters[client_ip].append(now)
        return await call_next(request)
