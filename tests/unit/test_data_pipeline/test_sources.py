"""Tests for data source base classes."""
from __future__ import annotations

import pytest

from ecotrack_data.sources.base import DataFormat, DataSourceConfig, FetchResult


class TestDataFormat:
    def test_format_values(self) -> None:
        assert DataFormat.COG == "cog"
        assert DataFormat.ZARR == "zarr"
        assert DataFormat.GEOJSON == "geojson"


class TestDataSourceConfig:
    def test_default_config(self) -> None:
        config = DataSourceConfig(name="test", base_url="https://example.com")
        assert config.rate_limit_per_second == 1.0
        assert config.max_retries == 3
        assert config.timeout_seconds == 30.0

    def test_custom_config(self) -> None:
        config = DataSourceConfig(
            name="test",
            base_url="https://api.example.com",
            api_key="test-key",
            rate_limit_per_second=5.0,
        )
        assert config.api_key == "test-key"
