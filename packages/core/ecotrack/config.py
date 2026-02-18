"""EcoTrack configuration management."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """Database connection configuration."""

    host: str = "localhost"
    port: int = 5432
    name: str = "ecotrack"
    user: str = "ecotrack"
    password: str = "ecotrack"

    @property
    def url(self) -> str:
        """Build async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    model_config = {"env_prefix": "DB_"}


class RedisConfig(BaseSettings):
    """Redis connection configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def url(self) -> str:
        """Build Redis connection URL."""
        return f"redis://{self.host}:{self.port}/{self.db}"

    model_config = {"env_prefix": "REDIS_"}


class StorageConfig(BaseSettings):
    """S3-compatible object storage configuration."""

    endpoint: str = "http://localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "ecotrack"
    region: str = "us-east-1"

    model_config = {"env_prefix": "S3_"}


class MLConfig(BaseSettings):
    """Machine learning configuration."""

    mlflow_tracking_uri: str = "http://localhost:5000"
    model_registry_uri: str = "http://localhost:5000"
    device: str = "cpu"
    default_batch_size: int = 32

    model_config = {"env_prefix": "ML_"}


class EcoTrackConfig(BaseSettings):
    """Main application configuration."""

    env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    ml: MLConfig = Field(default_factory=MLConfig)

    model_config = {"env_prefix": "ECOTRACK_"}


@lru_cache
def get_config() -> EcoTrackConfig:
    """Get cached application configuration."""
    return EcoTrackConfig()


__all__ = [
    "DatabaseConfig",
    "RedisConfig",
    "StorageConfig",
    "MLConfig",
    "EcoTrackConfig",
    "get_config",
]
