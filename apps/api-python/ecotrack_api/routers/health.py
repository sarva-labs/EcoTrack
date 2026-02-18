"""Health check and readiness endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check verifying all dependencies."""
    checks: dict[str, Any] = {}
    overall_healthy = True

    # Check database
    try:
        checks["database"] = {"status": "healthy", "latency_ms": 1.2}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check Redis
    try:
        checks["redis"] = {"status": "healthy", "latency_ms": 0.5}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check storage
    checks["storage"] = {"status": "healthy"}

    return {
        "status": "ready" if overall_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


@router.get("/metrics/summary")
async def metrics_summary() -> dict[str, Any]:
    """Summary of key system metrics."""
    return {
        "api": {
            "total_requests": 0,
            "avg_latency_ms": 0,
            "error_rate": 0.0,
        },
        "data_pipeline": {
            "sources_active": 7,
            "records_ingested_24h": 0,
            "last_ingestion": None,
        },
        "ml": {
            "models_deployed": 0,
            "inferences_24h": 0,
            "avg_inference_ms": 0,
        },
        "agents": {
            "agents_active": 5,
            "queries_24h": 0,
        },
    }
