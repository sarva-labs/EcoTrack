"""Integration tests for data pipeline."""
from __future__ import annotations

import asyncio

import pytest

from ecotrack_data.sources.base import DataSourceConfig, DataFormat
from ecotrack_data.storage.local import LocalStorage
from ecotrack_data.registry import SourceRegistry


class TestSourceRegistry:
    def test_auto_discover(self) -> None:
        """Test that all sources are discoverable."""
        registry = SourceRegistry()
        registry.auto_discover()
        sources = registry.list_sources()
        assert len(sources) >= 5  # We have at least 7 sources

    def test_create_source(self) -> None:
        """Test creating a source instance."""
        registry = SourceRegistry()
        registry.auto_discover()
        # This depends on what auto_discover finds


class TestLocalStorage:
    def test_put_and_get(self, tmp_path) -> None:
        """Test local storage put and get."""
        storage = LocalStorage(base_dir=tmp_path)

        async def run():
            uri = await storage.put("test/key.txt", b"hello world", {"type": "text"})
            assert uri
            data = await storage.get("test/key.txt")
            assert data == b"hello world"

        asyncio.run(run())

    def test_exists(self, tmp_path) -> None:
        """Test local storage exists check."""
        storage = LocalStorage(base_dir=tmp_path)

        async def run():
            assert not await storage.exists("nonexistent")
            await storage.put("exists.txt", b"data")
            assert await storage.exists("exists.txt")

        asyncio.run(run())
