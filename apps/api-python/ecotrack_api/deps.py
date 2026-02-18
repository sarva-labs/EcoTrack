"""Dependency injection for EcoTrack API."""
from __future__ import annotations

from typing import Any, AsyncIterator

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

async def get_db_session() -> AsyncIterator[Any]:
    """Get an async SQLAlchemy database session.

    Yields:
        An async SQLAlchemy session (or ``None`` while the database
        layer is not yet configured).

    Note:
        Database session management will be fully implemented when
        SQLAlchemy models and Alembic migrations are set up.
    """
    # TODO: Replace with real async session factory
    # from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    # engine = create_async_engine(DATABASE_URL)
    # async_session = async_sessionmaker(engine, class_=AsyncSession)
    # async with async_session() as session:
    #     yield session
    yield None


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

async def get_redis() -> AsyncIterator[Any]:
    """Get a Redis connection.

    Yields:
        A ``redis.asyncio.Redis`` instance (or ``None`` while Redis
        is not yet configured).
    """
    # TODO: Replace with real Redis connection
    # import redis.asyncio as aioredis
    # pool = aioredis.ConnectionPool.from_url(REDIS_URL)
    # client = aioredis.Redis(connection_pool=pool)
    # yield client
    # await client.aclose()
    yield None


# ---------------------------------------------------------------------------
# Application config
# ---------------------------------------------------------------------------

_config_cache: dict[str, Any] | None = None


def get_config() -> dict[str, Any]:
    """Get the application configuration.

    Returns:
        A dictionary of configuration values.  In a future iteration this
        will return a typed Pydantic settings object loaded from environment
        variables and config files.
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = {
            "env": "development",
            "debug": True,
            "api_host": "0.0.0.0",
            "api_port": 8000,
            "database_url": "postgresql+asyncpg://localhost/ecotrack",
            "redis_url": "redis://localhost:6379/0",
            "log_level": "INFO",
        }
    return _config_cache


# ---------------------------------------------------------------------------
# Agent orchestrator
# ---------------------------------------------------------------------------

_orchestrator_instance: Any = None


def get_agent_orchestrator() -> Any:
    """Get the agent orchestrator singleton.

    Returns:
        The ``AgentOrchestrator`` instance (or ``None`` while the agent
        package is not yet wired up).
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        # TODO: Wire up actual orchestrator
        # from ecotrack_agents.orchestrator import AgentOrchestrator
        # _orchestrator_instance = AgentOrchestrator()
        logger.info("agent_orchestrator.stub", message="Using stub orchestrator")
    return _orchestrator_instance


__all__ = [
    "get_db_session",
    "get_redis",
    "get_config",
    "get_agent_orchestrator",
]
