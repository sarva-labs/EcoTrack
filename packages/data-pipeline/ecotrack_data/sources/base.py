"""Base data source abstractions for EcoTrack data pipeline."""
from __future__ import annotations

import abc
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Generic, TypeVar

import httpx

T = TypeVar("T")


class DataFormat(str, Enum):
    """Supported data formats."""

    GEOJSON = "geojson"
    COG = "cog"  # Cloud Optimized GeoTIFF
    ZARR = "zarr"
    NETCDF = "netcdf"
    CSV = "csv"
    PARQUET = "parquet"
    STAC = "stac"
    JSON = "json"
    GRIB2 = "grib2"


@dataclass
class DataSourceConfig:
    """Configuration for a data source."""

    name: str
    base_url: str
    api_key: str | None = None
    rate_limit_per_second: float = 1.0
    timeout_seconds: float = 30.0
    max_retries: int = 3
    cache_dir: Path = field(default_factory=lambda: Path("data/cache"))
    formats: list[DataFormat] = field(default_factory=list)


@dataclass
class FetchResult:
    """Result of a data fetch operation."""

    source: str
    timestamp: datetime
    data: Any
    format: DataFormat
    size_bytes: int
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DataSource(abc.ABC, Generic[T]):
    """Abstract base class for all data sources.

    Provides common HTTP client management, checksum computation,
    and defines the fetch → validate → transform contract that
    every concrete source must implement.

    Type Parameters:
        T: The domain model type produced by :pymethod:`transform`.
    """

    def __init__(self, config: DataSourceConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a lazily-initialised :class:`httpx.AsyncClient`.

        The client is configured with the source's *base_url*, optional
        ``Authorization`` header, and request timeout from config.
        """
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    @abc.abstractmethod
    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Fetch data from the source.

        Args:
            bbox: Optional bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
            start_time: Optional temporal range start.
            end_time: Optional temporal range end.
            **kwargs: Source-specific parameters.

        Yields:
            :class:`FetchResult` instances for each fetched data chunk.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def validate(self, result: FetchResult) -> bool:
        """Validate fetched data for completeness and correctness.

        Args:
            result: The :class:`FetchResult` to validate.

        Returns:
            ``True`` if the result passes all validation checks.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    async def transform(self, result: FetchResult) -> list[T]:
        """Transform raw data into domain models.

        Args:
            result: The :class:`FetchResult` to transform.

        Returns:
            A list of domain model instances of type *T*.
        """
        ...  # pragma: no cover

    async def close(self) -> None:
        """Close the underlying HTTP client if open."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def compute_checksum(data: bytes) -> str:
        """Compute a SHA-256 hex-digest for *data*.

        Args:
            data: Raw bytes to hash.

        Returns:
            Lowercase hex-encoded SHA-256 digest.
        """
        return hashlib.sha256(data).hexdigest()

    async def __aenter__(self) -> DataSource[T]:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


__all__ = [
    "DataFormat",
    "DataSourceConfig",
    "FetchResult",
    "DataSource",
]
