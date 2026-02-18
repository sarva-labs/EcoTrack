# Tutorial: Adding a New Data Source

**Prerequisites:** [Quickstart Guide](./QUICKSTART.md) completed, Python 3.11+, `ecotrack-data` package installed
**Time:** ~30 minutes
**Difficulty:** Intermediate

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. Understanding the DataSource Base Class](#2-understanding-the-datasource-base-class)
- [3. Step-by-Step: Building a Weather Station Source](#3-step-by-step-building-a-weather-station-source)
- [4. Registering with the SourceRegistry](#4-registering-with-the-sourceregistry)
- [5. Running Ingestion](#5-running-ingestion)
- [6. Writing Tests](#6-writing-tests)
- [7. Next Steps](#7-next-steps)

---

## 1. Overview

EcoTrack's data pipeline ingests environmental data through a plugin-based connector architecture. Every data source—whether a satellite imagery API, weather station network, or biodiversity database—implements the same three-phase contract: **fetch → validate → transform**.

This tutorial walks through implementing a complete data source connector for a hypothetical weather station API. By the end, you will have a working connector registered with the [`SourceRegistry`](../../packages/data-pipeline/ecotrack_data/registry.py:18) and running through the [`DataPipeline`](../../packages/data-pipeline/ecotrack_data/pipeline.py:87).

### Architecture at a Glance

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Fetch     │────▶│   Validate   │────▶│  Transform   │────▶│    Store     │
│  (API call)  │     │ (quality QC) │     │ (→ domain)   │     │ (persist)    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

The existing data sources in [`ecotrack_data/sources/`](../../packages/data-pipeline/ecotrack_data/sources/__init__.py) provide reference implementations:

| Source | File | Domain |
|--------|------|--------|
| NOAA Climate Data Online | [`noaa_climate.py`](../../packages/data-pipeline/ecotrack_data/sources/noaa_climate.py) | Weather observations |
| Copernicus CDS | [`copernicus.py`](../../packages/data-pipeline/ecotrack_data/sources/copernicus.py) | Climate reanalysis |
| NASA Earthdata | [`nasa_earthdata.py`](../../packages/data-pipeline/ecotrack_data/sources/nasa_earthdata.py) | Satellite imagery |
| OpenAQ | [`openaq.py`](../../packages/data-pipeline/ecotrack_data/sources/openaq.py) | Air quality |
| GBIF | [`gbif.py`](../../packages/data-pipeline/ecotrack_data/sources/gbif.py) | Biodiversity |
| ERA5 | [`era5.py`](../../packages/data-pipeline/ecotrack_data/sources/era5.py) | Climate reanalysis |
| USDA CropScape | [`usda_cropscape.py`](../../packages/data-pipeline/ecotrack_data/sources/usda_cropscape.py) | Land cover |

---

## 2. Understanding the DataSource Base Class

All data sources extend [`DataSource`](../../packages/data-pipeline/ecotrack_data/sources/base.py:58), an abstract generic class with three required methods:

```python
from ecotrack_data.sources.base import DataSource, DataSourceConfig, FetchResult

class DataSource(abc.ABC, Generic[T]):
    """Abstract base class for all data sources."""

    def __init__(self, config: DataSourceConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    @abc.abstractmethod
    async def fetch(self, bbox=None, start_time=None, end_time=None, **kwargs) -> AsyncIterator[FetchResult]:
        """Fetch data from the source — yields pages of results."""
        ...

    @abc.abstractmethod
    async def validate(self, result: FetchResult) -> bool:
        """Validate a fetched result for correctness."""
        ...

    @abc.abstractmethod
    async def transform(self, result: FetchResult) -> list[T]:
        """Transform raw data into typed domain models."""
        ...
```

### Key Supporting Types

**[`DataSourceConfig`](../../packages/data-pipeline/ecotrack_data/sources/base.py:31)** — Configuration dataclass:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | — | Unique source identifier |
| `base_url` | `str` | — | API base URL |
| `api_key` | `str \| None` | `None` | Optional API key |
| `rate_limit_per_second` | `float` | `1.0` | Max requests per second |
| `timeout_seconds` | `float` | `30.0` | HTTP request timeout |
| `max_retries` | `int` | `3` | Retry count on failure |
| `cache_dir` | `Path` | `data/cache` | Local cache directory |
| `formats` | `list[DataFormat]` | `[]` | Supported data formats |

**[`FetchResult`](../../packages/data-pipeline/ecotrack_data/sources/base.py:45)** — Result of a fetch operation containing `source`, `timestamp`, `data`, `format`, `size_bytes`, `checksum`, and `metadata`.

**[`DataFormat`](../../packages/data-pipeline/ecotrack_data/sources/base.py:17)** — Enum of supported formats: `GEOJSON`, `COG`, `ZARR`, `NETCDF`, `CSV`, `PARQUET`, `STAC`, `JSON`, `GRIB2`.

---

## 3. Step-by-Step: Building a Weather Station Source

We will build a connector for a fictional "GlobalWeather API" that provides station-based temperature and precipitation observations.

### Step 1: Create the Source File

Create `packages/data-pipeline/ecotrack_data/sources/globalweather.py`:

```python
"""GlobalWeather API data source.

Provides access to weather station observations from the
fictional GlobalWeather network.

Endpoint: https://api.globalweather.example.com/v1
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult
```

### Step 2: Define the Default Configuration

```python
_DEFAULT_URL = "https://api.globalweather.example.com/v1"
_PAGE_SIZE = 500


def _default_config(api_key: str | None = None) -> DataSourceConfig:
    """Build a default DataSourceConfig for GlobalWeather."""
    return DataSourceConfig(
        name="globalweather",
        base_url=_DEFAULT_URL,
        api_key=api_key,
        rate_limit_per_second=10.0,
        timeout_seconds=30.0,
        max_retries=3,
        formats=[DataFormat.JSON],
    )
```

### Step 3: Implement the Source Class

```python
class GlobalWeatherSource(DataSource[dict[str, Any]]):
    """GlobalWeather API connector.

    Queries the GlobalWeather API for station-based observations
    and transforms them into standardised records.

    Example::

        async with GlobalWeatherSource(api_key="<TOKEN>") as src:
            async for result in src.fetch(
                bbox=(-90, 30, -80, 40),
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
            ):
                records = await src.transform(result)
    """

    def __init__(
        self,
        config: DataSourceConfig | None = None,
        *,
        api_key: str | None = None,
    ) -> None:
        super().__init__(config or _default_config(api_key))
        self._rate_semaphore = asyncio.Semaphore(
            max(1, int(self.config.rate_limit_per_second))
        )
```

### Step 4: Implement `fetch()`

The `fetch()` method is an async generator that yields [`FetchResult`](../../packages/data-pipeline/ecotrack_data/sources/base.py:45) pages:

```python
    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Fetch weather observations from the GlobalWeather API."""
        client = await self._get_client()
        page = 1
        total_fetched = 0
        max_items = kwargs.get("max_items", 5000)

        while total_fetched < max_items:
            params: dict[str, Any] = {
                "page": page,
                "per_page": _PAGE_SIZE,
            }

            if bbox:
                params["min_lon"] = bbox[0]
                params["min_lat"] = bbox[1]
                params["max_lon"] = bbox[2]
                params["max_lat"] = bbox[3]

            if start_time:
                params["start"] = start_time.isoformat()
            if end_time:
                params["end"] = end_time.isoformat()

            # Make the API call with rate limiting
            data = await self._do_request(client, "/observations", params)
            records = data.get("observations", [])

            if not records:
                break

            raw_bytes = str(records).encode()
            yield FetchResult(
                source="globalweather",
                timestamp=datetime.utcnow(),
                data=records,
                format=DataFormat.JSON,
                size_bytes=len(raw_bytes),
                checksum=self.compute_checksum(raw_bytes),
                metadata={"page": page, "count": len(records)},
            )

            total_fetched += len(records)
            page += 1

            # Stop if last page was incomplete
            if len(records) < _PAGE_SIZE:
                break
```

### Step 5: Implement `validate()`

```python
    async def validate(self, result: FetchResult) -> bool:
        """Validate that results contain required fields."""
        if not isinstance(result.data, list) or len(result.data) == 0:
            return False

        required_keys = {"station_id", "timestamp", "temperature", "latitude", "longitude"}
        for record in result.data:
            if not required_keys.issubset(record.keys()):
                return False
            # Range checks
            if not (-90 <= record["latitude"] <= 90):
                return False
            if not (-180 <= record["longitude"] <= 180):
                return False

        return True
```

### Step 6: Implement `transform()`

```python
    async def transform(self, result: FetchResult) -> list[dict[str, Any]]:
        """Transform raw API records into standardised observations."""
        observations = []

        for record in result.data:
            obs = {
                "source": "globalweather",
                "station_id": record["station_id"],
                "timestamp": record["timestamp"],
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "temperature_celsius": record["temperature"],
                "precipitation_mm": record.get("precipitation", 0.0),
                "wind_speed_ms": record.get("wind_speed"),
                "humidity_pct": record.get("humidity"),
            }
            observations.append(obs)

        return observations
```

### Step 7: Add Rate-Limited HTTP Helper

```python
    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        reraise=True,
    )
    async def _do_request(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a rate-limited GET request with retry logic."""
        async with self._rate_semaphore:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()


__all__ = ["GlobalWeatherSource"]
```

---

## 4. Registering with the SourceRegistry

### Automatic Discovery

If your source file is placed in the [`ecotrack_data/sources/`](../../packages/data-pipeline/ecotrack_data/sources/) directory, it will be auto-discovered by [`SourceRegistry.auto_discover()`](../../packages/data-pipeline/ecotrack_data/registry.py:81). The registry scans for concrete `DataSource` subclasses and registers them under an inferred name (derived from `config.name` or the class name):

```python
from ecotrack_data import SourceRegistry

registry = SourceRegistry()
discovered = registry.auto_discover()
print(registry.names)
# ['copernicus', 'era5', 'gbif', 'globalweather', 'nasa_earthdata',
#  'noaa_climate', 'openaq', 'usda_cropscape']
```

### Manual Registration

For sources outside the `sources/` package, register explicitly:

```python
from ecotrack_data import SourceRegistry
from my_package.sources import GlobalWeatherSource

registry = SourceRegistry()
registry.register("globalweather", GlobalWeatherSource)
```

### Creating Instances via the Registry

The registry provides a factory method that handles configuration:

```python
source = registry.create(
    "globalweather",
    api_key="your-api-key-here",
)
```

---

## 5. Running Ingestion

### Using the DataPipeline

The [`DataPipeline`](../../packages/data-pipeline/ecotrack_data/pipeline.py:87) chains your source through the full fetch → validate → transform → store workflow:

```python
import asyncio
from datetime import datetime
from ecotrack_data import DataPipeline, get_registry

async def main():
    # Get the source from the registry
    registry = get_registry()
    source = registry.create("globalweather", api_key="your-key")

    # Define a storage function (or use built-in storage backends)
    async def store_records(records: list) -> int:
        # Store to database, local files, or S3
        print(f"Storing {len(records)} records")
        return len(records)

    # Create and run the pipeline
    pipeline = DataPipeline(
        source=source,
        store=store_records,
        max_retries=3,
        retry_delay_s=5.0,
    )

    result = await pipeline.run(
        bbox=(-90, 30, -80, 40),
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 1, 31),
    )

    print(f"Status: {result.status.value}")
    print(f"Records: {result.total_records}")
    print(f"Duration: {result.total_duration_s:.2f}s")
    print(f"Errors: {result.errors}")

asyncio.run(main())
```

### Dry Run Mode

Test your source without persisting data by enabling `dry_run`:

```python
pipeline = DataPipeline(source=source, dry_run=True)
result = await pipeline.run(bbox=(-90, 30, -80, 40))
assert result.status == PipelineStatus.DRY_RUN
```

### Using the CLI

The EcoTrack CLI provides a command-line interface for data ingestion:

```bash
# Run ingestion for a specific source
ecotrack data ingest --source globalweather \
    --bbox "-90,30,-80,40" \
    --start 2024-01-01 \
    --end 2024-01-31 \
    --api-key "$GLOBALWEATHER_API_KEY"

# Dry run (no storage)
ecotrack data ingest --source globalweather --dry-run

# List available sources
ecotrack data sources
```

---

## 6. Writing Tests

Create `tests/unit/test_globalweather.py`:

```python
"""Tests for the GlobalWeather data source."""
from __future__ import annotations

import pytest
from datetime import datetime
from ecotrack_data.sources.base import DataFormat, FetchResult
from ecotrack_data.sources.globalweather import GlobalWeatherSource


@pytest.fixture
def source() -> GlobalWeatherSource:
    """Create a GlobalWeatherSource for testing."""
    return GlobalWeatherSource(api_key="test-key")


@pytest.fixture
def valid_fetch_result() -> FetchResult:
    """Create a valid FetchResult for testing."""
    data = [
        {
            "station_id": "GW001",
            "timestamp": "2024-01-15T12:00:00Z",
            "temperature": 22.5,
            "precipitation": 5.2,
            "latitude": 35.0,
            "longitude": -85.0,
            "wind_speed": 3.4,
            "humidity": 65.0,
        },
        {
            "station_id": "GW002",
            "timestamp": "2024-01-15T12:00:00Z",
            "temperature": 18.3,
            "precipitation": 0.0,
            "latitude": 36.5,
            "longitude": -82.0,
        },
    ]
    raw_bytes = str(data).encode()
    return FetchResult(
        source="globalweather",
        timestamp=datetime.utcnow(),
        data=data,
        format=DataFormat.JSON,
        size_bytes=len(raw_bytes),
        checksum="abc123",
    )


class TestValidation:
    """Tests for the validate() method."""

    @pytest.mark.asyncio
    async def test_valid_data_passes(self, source, valid_fetch_result):
        assert await source.validate(valid_fetch_result) is True

    @pytest.mark.asyncio
    async def test_empty_data_fails(self, source):
        result = FetchResult(
            source="globalweather",
            timestamp=datetime.utcnow(),
            data=[],
            format=DataFormat.JSON,
            size_bytes=0,
            checksum="",
        )
        assert await source.validate(result) is False

    @pytest.mark.asyncio
    async def test_missing_fields_fails(self, source):
        result = FetchResult(
            source="globalweather",
            timestamp=datetime.utcnow(),
            data=[{"station_id": "GW001"}],  # Missing required fields
            format=DataFormat.JSON,
            size_bytes=10,
            checksum="abc",
        )
        assert await source.validate(result) is False

    @pytest.mark.asyncio
    async def test_invalid_coordinates_fails(self, source):
        result = FetchResult(
            source="globalweather",
            timestamp=datetime.utcnow(),
            data=[{
                "station_id": "GW001",
                "timestamp": "2024-01-15T12:00:00Z",
                "temperature": 22.5,
                "latitude": 999.0,  # Invalid
                "longitude": -85.0,
            }],
            format=DataFormat.JSON,
            size_bytes=10,
            checksum="abc",
        )
        assert await source.validate(result) is False


class TestTransform:
    """Tests for the transform() method."""

    @pytest.mark.asyncio
    async def test_transforms_records(self, source, valid_fetch_result):
        records = await source.transform(valid_fetch_result)
        assert len(records) == 2
        assert records[0]["temperature_celsius"] == 22.5
        assert records[0]["source"] == "globalweather"
        assert records[0]["station_id"] == "GW001"

    @pytest.mark.asyncio
    async def test_handles_optional_fields(self, source, valid_fetch_result):
        records = await source.transform(valid_fetch_result)
        # Second record has no wind_speed
        assert records[1]["wind_speed_ms"] is None
        assert records[1]["precipitation_mm"] == 0.0
```

Run the tests:

```bash
pytest tests/unit/test_globalweather.py -v
```

---

## 7. Next Steps

- **Add storage integration** — Connect your source to PostgreSQL using the storage backends in [`ecotrack_data/storage/`](../../packages/data-pipeline/ecotrack_data/storage/)
- **Implement caching** — Use the `cache_dir` from `DataSourceConfig` to cache API responses
- **Add to the worker** — Register your pipeline as a Dramatiq task in [`ecotrack_worker/tasks/data_ingestion.py`](../../apps/worker/ecotrack_worker/tasks/data_ingestion.py)
- **Train a model on ingested data** — Follow the [Model Training Tutorial](./MODEL_TRAINING.md)
- **Read the architecture** — See [`SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md) for the full data architecture

---

*See also: [Quickstart Guide](./QUICKSTART.md) · [API Documentation](../../API.md) · [Contributing Guide](../../CONTRIBUTING.md)*
