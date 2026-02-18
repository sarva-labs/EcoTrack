"""Tests for EcoTrack configuration."""
from __future__ import annotations

import os

from ecotrack.config import DatabaseConfig, EcoTrackConfig, RedisConfig, get_config


class TestDatabaseConfig:
    def test_default_values(self) -> None:
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.name == "ecotrack"

    def test_url_property(self) -> None:
        config = DatabaseConfig()
        assert "postgresql+asyncpg" in config.url
        assert "localhost" in config.url


class TestRedisConfig:
    def test_url_property(self) -> None:
        config = RedisConfig()
        assert config.url == "redis://localhost:6379/0"


class TestEcoTrackConfig:
    def test_default_env(self) -> None:
        config = EcoTrackConfig()
        assert config.env == "development"
        assert config.debug is True

    def test_nested_configs(self) -> None:
        config = EcoTrackConfig()
        assert isinstance(config.db, DatabaseConfig)
        assert isinstance(config.redis, RedisConfig)
