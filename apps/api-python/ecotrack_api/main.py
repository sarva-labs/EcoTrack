"""EcoTrack API — Planetary Environmental Intelligence Platform."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from ecotrack_api.errors import register_error_handlers
from ecotrack_api.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from ecotrack_api.routers import (
    agents,
    analytics,
    biodiversity,
    climate,
    data_pipeline,
    food_security,
    health_domain,
    resources,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    logger.info("ecotrack_api.starting", version="0.1.0")
    # Startup: initialize connections, warm caches
    yield
    # Shutdown: close connections
    logger.info("ecotrack_api.shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="EcoTrack API",
        description=(
            "Planetary-scale environmental intelligence platform providing "
            "climate, biodiversity, public health, food security, and resource "
            "equity analytics."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware (order matters — last added = first executed)
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------
    register_error_handlers(app)

    # ------------------------------------------------------------------
    # Domain routers
    # ------------------------------------------------------------------
    app.include_router(climate.router, prefix="/api/v1/climate", tags=["Climate"])
    app.include_router(biodiversity.router, prefix="/api/v1/biodiversity", tags=["Biodiversity"])
    app.include_router(health_domain.router, prefix="/api/v1/health", tags=["Public Health"])
    app.include_router(food_security.router, prefix="/api/v1/food-security", tags=["Food Security"])
    app.include_router(resources.router, prefix="/api/v1/resources", tags=["Resource Equity"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["AI Agents"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(data_pipeline.router, prefix="/api/v1/data", tags=["Data Pipeline"])

    # ------------------------------------------------------------------
    # System endpoints
    # ------------------------------------------------------------------

    @app.get("/api/health", tags=["System"], summary="Health check")
    async def health_check() -> dict[str, str]:
        """Service health check."""
        return {"status": "healthy", "version": "0.1.0", "service": "ecotrack-api"}

    @app.get("/api/v1/domains", tags=["System"], summary="List available domains")
    async def list_domains() -> dict[str, Any]:
        """List all EcoTrack domain endpoints and their descriptions."""
        return {
            "domains": [
                {"name": "climate", "description": "Climate intelligence and forecasting", "endpoints": "/api/v1/climate"},
                {"name": "biodiversity", "description": "Biodiversity monitoring and assessment", "endpoints": "/api/v1/biodiversity"},
                {"name": "health", "description": "Public health and environmental health", "endpoints": "/api/v1/health"},
                {"name": "food_security", "description": "Food security and agricultural monitoring", "endpoints": "/api/v1/food-security"},
                {"name": "resources", "description": "Resource equity and allocation", "endpoints": "/api/v1/resources"},
                {"name": "agents", "description": "AI agent interaction and orchestration", "endpoints": "/api/v1/agents"},
                {"name": "analytics", "description": "Cross-domain analytics and reporting", "endpoints": "/api/v1/analytics"},
                {"name": "data", "description": "Data pipeline and catalog management", "endpoints": "/api/v1/data"},
            ]
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("ecotrack_api.main:app", host="0.0.0.0", port=8000, reload=True)
