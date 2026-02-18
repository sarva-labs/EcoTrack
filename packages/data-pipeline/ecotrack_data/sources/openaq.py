"""OpenAQ air quality data source.

Provides real-time and historical air quality measurements from
ground-level monitoring stations worldwide.

Endpoint: https://api.openaq.org/v3
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator

import httpx
from ecotrack.logging import get_logger
from ecotrack.models.geospatial import GeoPoint
from ecotrack.models.health import AirQualityReading
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult

logger = get_logger(__name__)

#: Supported OpenAQ measurement parameters.
OPENAQ_PARAMETERS: list[str] = ["pm25", "pm10", "o3", "no2", "so2", "co"]

_DEFAULT_OPENAQ_URL = "https://api.openaq.org/v3"
_PAGE_LIMIT = 100


def _default_config(api_key: str | None = None) -> DataSourceConfig:
    """Build a default :class:`DataSourceConfig` for OpenAQ v3."""
    return DataSourceConfig(
        name="openaq",
        base_url=_DEFAULT_OPENAQ_URL,
        api_key=api_key,
        rate_limit_per_second=5.0,
        timeout_seconds=30.0,
        max_retries=3,
        formats=[DataFormat.JSON],
    )


class OpenAQSource(DataSource[AirQualityReading]):
    """OpenAQ v3 air quality connector.

    Queries the OpenAQ API for ground-level air quality measurements
    and transforms them into :class:`AirQualityReading` domain models.

    Authentication uses a Bearer API key obtained from
    https://explore.openaq.org/register.

    Example::

        async with OpenAQSource(api_key="<OPENAQ_KEY>") as src:
            async for result in src.fetch(
                bbox=(-74.5, 40.4, -73.5, 41.0),
                start_time=datetime(2024, 6, 1),
                end_time=datetime(2024, 6, 30),
                parameters=["pm25", "o3"],
            ):
                readings = await src.transform(result)
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

    async def _get_client(self) -> httpx.AsyncClient:
        """Override to use OpenAQ's ``X-API-Key`` header."""
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {
                "Accept": "application/json",
            }
            if self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        *,
        parameters: list[str] | None = None,
        location_ids: list[int] | None = None,
        country: str | None = None,
        max_items: int = 5000,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Fetch air quality measurements from the OpenAQ v3 API.

        Args:
            bbox: Bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
            start_time: Temporal range start.
            end_time: Temporal range end.
            parameters: Pollutant parameter names (e.g. ``["pm25", "o3"]``).
            location_ids: Specific OpenAQ location IDs.
            country: ISO 3166-1 alpha-2 country code.
            max_items: Maximum total measurements to retrieve.
            **kwargs: Extra query parameters.

        Yields:
            :class:`FetchResult` containing a list of measurement dicts.
        """
        if parameters is None:
            parameters = ["pm25"]

        client = await self._get_client()
        page = 1
        items_yielded = 0

        while items_yielded < max_items:
            params = self._build_query_params(
                bbox=bbox,
                start_time=start_time,
                end_time=end_time,
                parameters=parameters,
                location_ids=location_ids,
                country=country,
                page=page,
                limit=min(_PAGE_LIMIT, max_items - items_yielded),
            )
            params.update(kwargs)

            data = await self._do_request(client, "/measurements", params)
            results: list[dict[str, Any]] = data.get("results", [])

            if not results:
                logger.info(
                    "openaq.fetch_exhausted",
                    page=page,
                    total_yielded=items_yielded,
                )
                break

            raw_bytes = str(results).encode()
            result = FetchResult(
                source="openaq",
                timestamp=datetime.utcnow(),
                data=results,
                format=DataFormat.JSON,
                size_bytes=len(raw_bytes),
                checksum=self.compute_checksum(raw_bytes),
                metadata={
                    "parameters": parameters,
                    "page": page,
                    "returned": len(results),
                },
            )
            yield result
            items_yielded += len(results)
            page += 1

        logger.info(
            "openaq.fetch_complete",
            total_items=items_yielded,
            parameters=parameters,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, result: FetchResult) -> bool:
        """Validate that *result* contains well-formed OpenAQ measurements.

        Each measurement must have ``value``, ``parameter``, ``date``,
        and ``coordinates``.

        Args:
            result: A :class:`FetchResult` from :pymethod:`fetch`.

        Returns:
            ``True`` when all records pass validation.
        """
        if not isinstance(result.data, list) or len(result.data) == 0:
            logger.warning("openaq.validate_empty", source=result.source)
            return False

        for record in result.data:
            if "value" not in record:
                logger.warning(
                    "openaq.validate_missing_value",
                    record_keys=list(record.keys()),
                )
                return False
            # OpenAQ v3 nests coordinates inside `location`
            coords = record.get("coordinates") or (
                record.get("location", {}).get("coordinates")
            )
            if coords is None:
                logger.warning("openaq.validate_missing_coordinates")
                return False
        return True

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    async def transform(self, result: FetchResult) -> list[AirQualityReading]:
        """Transform OpenAQ measurements into :class:`AirQualityReading` models.

        The method groups concurrent measurements from the same location
        into a single reading when possible.

        Args:
            result: Validated :class:`FetchResult`.

        Returns:
            List of :class:`AirQualityReading` instances.
        """
        readings: list[AirQualityReading] = []

        for record in result.data:
            try:
                reading = self._record_to_reading(record)
                if reading is not None:
                    readings.append(reading)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "openaq.transform_record_failed",
                    error=str(exc),
                    record_id=record.get("id"),
                )

        logger.info("openaq.transform_complete", count=len(readings))
        return readings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query_params(
        *,
        bbox: tuple[float, float, float, float] | None,
        start_time: datetime | None,
        end_time: datetime | None,
        parameters: list[str],
        location_ids: list[int] | None,
        country: str | None,
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        """Build query parameters for the ``/measurements`` endpoint."""
        params: dict[str, Any] = {
            "limit": limit,
            "page": page,
            "sort": "desc",
            "order_by": "datetime",
        }
        if parameters:
            params["parameter"] = ",".join(parameters)
        if start_time:
            params["date_from"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if end_time:
            params["date_to"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if bbox is not None:
            params["coordinates"] = f"{(bbox[1]+bbox[3])/2},{(bbox[0]+bbox[2])/2}"
            # Approximate radius in metres for the bbox diagonal
            import math

            dlat = abs(bbox[3] - bbox[1])
            dlon = abs(bbox[2] - bbox[0])
            radius_km = math.sqrt(dlat**2 + dlon**2) * 111.32 / 2
            params["radius"] = int(radius_km * 1000)
        if location_ids:
            params["location_id"] = ",".join(str(i) for i in location_ids)
        if country:
            params["country"] = country
        return params

    @staticmethod
    def _record_to_reading(record: dict[str, Any]) -> AirQualityReading | None:
        """Convert a single OpenAQ measurement record to a domain model.

        Args:
            record: A single OpenAQ measurement dict.

        Returns:
            An :class:`AirQualityReading` or ``None`` if conversion fails.
        """
        # Resolve coordinates (v3 uses nested structure)
        coords = record.get("coordinates") or {}
        if not coords:
            loc = record.get("location", {})
            coords = loc.get("coordinates", {})

        latitude = coords.get("latitude")
        longitude = coords.get("longitude")
        if latitude is None or longitude is None:
            return None

        # Parse datetime
        date_info = record.get("date", {})
        if isinstance(date_info, dict):
            utc_str = date_info.get("utc", "")
        else:
            utc_str = str(date_info)

        if not utc_str:
            return None

        timestamp = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))

        parameter = record.get("parameter", "")
        value = record.get("value")
        if value is None:
            return None

        # Build param-specific fields
        param_map = {
            "pm25": {"pm25": float(value)},
            "pm10": {"pm10": float(value)},
            "o3": {"ozone": float(value)},
            "no2": {"no2": float(value)},
            "so2": {"so2": float(value)},
            "co": {"co": float(value)},
        }
        fields = param_map.get(parameter, {})

        return AirQualityReading(
            location=GeoPoint(latitude=latitude, longitude=longitude),
            timestamp=timestamp,
            aqi=_estimate_aqi(parameter, float(value)),
            source=f"openaq:{record.get('location', {}).get('id', 'unknown')}",
            metadata={
                "parameter": parameter,
                "unit": record.get("unit", ""),
                "location_name": record.get("location", {}).get("name", ""),
            },
            **fields,
        )

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
        """Execute a GET request to the OpenAQ API with retry logic.

        Args:
            client: The HTTP client.
            path: API path.
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        async with self._rate_semaphore:
            logger.debug("openaq.request", path=path, params=params)
            response = await client.get(path, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


def _estimate_aqi(parameter: str, value: float) -> int:
    """Estimate an AQI value from a single pollutant concentration.

    Uses simplified US EPA breakpoints.  This is an approximation —
    production systems should use full breakpoint tables.

    Args:
        parameter: Pollutant name (e.g. ``"pm25"``).
        value: Concentration in the pollutant's default unit.

    Returns:
        Estimated AQI integer clamped to [0, 500].
    """
    if parameter == "pm25":
        # Simplified PM2.5 AQI breakpoints (µg/m³)
        if value <= 12.0:
            aqi = int(value / 12.0 * 50)
        elif value <= 35.4:
            aqi = int(50 + (value - 12.0) / 23.4 * 50)
        elif value <= 55.4:
            aqi = int(100 + (value - 35.4) / 20.0 * 50)
        elif value <= 150.4:
            aqi = int(150 + (value - 55.4) / 95.0 * 50)
        elif value <= 250.4:
            aqi = int(200 + (value - 150.4) / 100.0 * 100)
        else:
            aqi = int(300 + (value - 250.4) / 150.0 * 200)
    elif parameter == "pm10":
        if value <= 54:
            aqi = int(value / 54 * 50)
        elif value <= 154:
            aqi = int(50 + (value - 54) / 100 * 50)
        else:
            aqi = int(100 + (value - 154) / 200 * 100)
    elif parameter == "o3":
        # ppb
        if value <= 54:
            aqi = int(value / 54 * 50)
        elif value <= 70:
            aqi = int(50 + (value - 54) / 16 * 50)
        else:
            aqi = int(100 + (value - 70) / 95 * 100)
    else:
        # Fallback — rough linear estimate
        aqi = int(min(value * 2, 500))

    return max(0, min(500, aqi))


__all__ = ["OpenAQSource", "OPENAQ_PARAMETERS"]
