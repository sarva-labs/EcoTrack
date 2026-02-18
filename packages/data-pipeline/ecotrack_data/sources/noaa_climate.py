"""NOAA Climate Data Online source.

Provides access to weather station data, global temperature records,
and climate normals via the NOAA CDO API.

Endpoint: https://www.ncei.noaa.gov/cdo-web/api/v2
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator

import httpx
from ecotrack.logging import get_logger
from ecotrack.models.climate import ClimateObservation, ClimateVariable
from ecotrack.models.geospatial import GeoPoint
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult

logger = get_logger(__name__)

#: NOAA CDO dataset identifiers.
NOAA_DATASETS: dict[str, str] = {
    "GHCND": "Daily Summaries",
    "GSOM": "Global Summary of the Month",
    "GSOY": "Global Summary of the Year",
    "NORMAL_DLY": "Climate Normals Daily",
    "NORMAL_MLY": "Climate Normals Monthly",
}

#: Mapping of NOAA data-type IDs to EcoTrack climate variables.
_NOAA_VARIABLE_MAP: dict[str, ClimateVariable] = {
    "TAVG": ClimateVariable.TEMPERATURE,
    "TMAX": ClimateVariable.TEMPERATURE,
    "TMIN": ClimateVariable.TEMPERATURE,
    "PRCP": ClimateVariable.PRECIPITATION,
    "AWND": ClimateVariable.WIND_SPEED,
    "RHAV": ClimateVariable.HUMIDITY,
    "SLP": ClimateVariable.PRESSURE,
}

#: NOAA CDO API units per data type (values are tenths of °C or mm).
_NOAA_UNIT_MAP: dict[str, str] = {
    "TAVG": "°C",
    "TMAX": "°C",
    "TMIN": "°C",
    "PRCP": "mm",
    "AWND": "m/s",
    "RHAV": "%",
    "SLP": "hPa",
}

_DEFAULT_CDO_URL = "https://www.ncei.noaa.gov/cdo-web/api/v2"
_PAGE_LIMIT = 1000  # CDO max per request


def _default_config(api_key: str | None = None) -> DataSourceConfig:
    """Build a default :class:`DataSourceConfig` for NOAA CDO."""
    return DataSourceConfig(
        name="noaa_climate",
        base_url=_DEFAULT_CDO_URL,
        api_key=api_key,
        rate_limit_per_second=5.0,
        timeout_seconds=30.0,
        max_retries=3,
        formats=[DataFormat.JSON],
    )


class NOAAClimateSource(DataSource[ClimateObservation]):
    """NOAA Climate Data Online connector.

    Queries the CDO API v2 for station-based climate observations and
    transforms them into :class:`ClimateObservation` domain models.

    Authentication requires a CDO API token obtained from
    https://www.ncdc.noaa.gov/cdo-web/token — the token is sent in
    a ``token`` HTTP header (not ``Authorization``).

    Example::

        async with NOAAClimateSource(api_key="<CDO_TOKEN>") as src:
            async for result in src.fetch(
                bbox=(-90, 30, -80, 40),
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                dataset_id="GHCND",
                data_types=["TAVG", "PRCP"],
            ):
                observations = await src.transform(result)
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
        """Override to use NOAA's ``token`` header instead of Bearer auth."""
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {}
            if self.config.api_key:
                headers["token"] = self.config.api_key
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
        dataset_id: str = "GHCND",
        data_types: list[str] | None = None,
        station_ids: list[str] | None = None,
        max_items: int = 5000,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Fetch climate data from the NOAA CDO API.

        Args:
            bbox: Bounding box ``(min_lon, min_lat, max_lon, max_lat)``
                used to build an ``extent`` query parameter.
            start_time: Temporal range start (inclusive).
            end_time: Temporal range end (inclusive).
            dataset_id: CDO dataset, e.g. ``"GHCND"`` or ``"GSOM"``.
            data_types: List of CDO data-type IDs (e.g. ``["TAVG", "PRCP"]``).
            station_ids: Optional list of specific station IDs.
            max_items: Maximum total items to retrieve.
            **kwargs: Extra query parameters forwarded to the API.

        Yields:
            :class:`FetchResult` containing a list of observation dicts.
        """
        client = await self._get_client()
        offset = 1
        items_yielded = 0

        while items_yielded < max_items:
            params = self._build_query_params(
                bbox=bbox,
                start_time=start_time,
                end_time=end_time,
                dataset_id=dataset_id,
                data_types=data_types,
                station_ids=station_ids,
                offset=offset,
                limit=min(_PAGE_LIMIT, max_items - items_yielded),
            )
            params.update(kwargs)

            data = await self._do_request(client, "/data", params)
            results: list[dict[str, Any]] = data.get("results", [])

            if not results:
                logger.info(
                    "noaa.fetch_exhausted",
                    offset=offset,
                    total_yielded=items_yielded,
                )
                break

            raw_bytes = str(results).encode()
            result = FetchResult(
                source="noaa_climate",
                timestamp=datetime.utcnow(),
                data=results,
                format=DataFormat.JSON,
                size_bytes=len(raw_bytes),
                checksum=self.compute_checksum(raw_bytes),
                metadata={
                    "dataset_id": dataset_id,
                    "offset": offset,
                    "returned": len(results),
                    "metadata": data.get("metadata", {}),
                },
            )
            yield result
            items_yielded += len(results)
            offset += len(results)

            # Check if we've retrieved everything
            total_count = (
                data.get("metadata", {}).get("resultset", {}).get("count", 0)
            )
            if items_yielded >= total_count:
                break

        logger.info(
            "noaa.fetch_complete",
            total_items=items_yielded,
            dataset=dataset_id,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, result: FetchResult) -> bool:
        """Validate that *result* contains well-formed CDO observations.

        Checks each record for required fields: ``date``, ``datatype``,
        ``value``, and ``station``.

        Args:
            result: A :class:`FetchResult` from :pymethod:`fetch`.

        Returns:
            ``True`` when all records pass validation.
        """
        if not isinstance(result.data, list) or len(result.data) == 0:
            logger.warning("noaa.validate_empty", source=result.source)
            return False

        required_keys = {"date", "datatype", "value", "station"}
        for record in result.data:
            if not required_keys.issubset(record.keys()):
                logger.warning(
                    "noaa.validate_missing_keys",
                    station=record.get("station"),
                    missing=required_keys - record.keys(),
                )
                return False
        return True

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    async def transform(self, result: FetchResult) -> list[ClimateObservation]:
        """Transform CDO records into :class:`ClimateObservation` models.

        NOAA CDO temperature values are in tenths of °C — they are
        converted to °C here.  Precipitation is in tenths of mm.

        Args:
            result: Validated :class:`FetchResult`.

        Returns:
            List of :class:`ClimateObservation` instances.
        """
        observations: list[ClimateObservation] = []

        # Pre-fetch station locations for coordinate lookup
        station_coords = await self._resolve_station_locations(result.data)

        for record in result.data:
            datatype: str = record["datatype"]
            variable = _NOAA_VARIABLE_MAP.get(datatype)
            if variable is None:
                continue  # Skip unmapped variables

            raw_value: float = record["value"]
            # Convert NOAA tenths values
            if datatype in {"TAVG", "TMAX", "TMIN"}:
                value = raw_value / 10.0
            elif datatype == "PRCP":
                value = raw_value / 10.0
            else:
                value = raw_value

            station_id: str = record["station"]
            coords = station_coords.get(station_id)
            if coords is None:
                continue  # Cannot geolocate

            obs = ClimateObservation(
                variable=variable,
                value=value,
                unit=_NOAA_UNIT_MAP.get(datatype, "unknown"),
                location=GeoPoint(
                    latitude=coords["latitude"],
                    longitude=coords["longitude"],
                    elevation_m=coords.get("elevation"),
                ),
                timestamp=datetime.fromisoformat(
                    record["date"].replace("T", " ").rstrip("Z")
                ),
                source=f"noaa_cdo:{station_id}",
                quality_flag=_parse_quality_flag(record),
                metadata={
                    "datatype": datatype,
                    "station_id": station_id,
                    "attributes": record.get("attributes", ""),
                },
            )
            observations.append(obs)

        logger.info("noaa.transform_complete", count=len(observations))
        return observations

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query_params(
        *,
        bbox: tuple[float, float, float, float] | None,
        start_time: datetime | None,
        end_time: datetime | None,
        dataset_id: str,
        data_types: list[str] | None,
        station_ids: list[str] | None,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        """Build query parameters for a ``/data`` request."""
        params: dict[str, Any] = {
            "datasetid": dataset_id,
            "limit": limit,
            "offset": offset,
            "units": "metric",
        }
        if start_time:
            params["startdate"] = start_time.strftime("%Y-%m-%d")
        if end_time:
            params["enddate"] = end_time.strftime("%Y-%m-%d")
        if bbox is not None:
            # CDO uses extent=minlat,minlon,maxlat,maxlon
            params["extent"] = f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}"
        if data_types:
            params["datatypeid"] = ",".join(data_types)
        if station_ids:
            params["stationid"] = ",".join(station_ids)
        return params

    async def _resolve_station_locations(
        self, records: list[dict[str, Any]]
    ) -> dict[str, dict[str, float]]:
        """Fetch geographic coordinates for stations in *records*.

        Returns:
            Mapping of station ID → ``{latitude, longitude, elevation}``.
        """
        station_ids = {r["station"] for r in records if "station" in r}
        coords: dict[str, dict[str, float]] = {}

        client = await self._get_client()
        for station_id in station_ids:
            if station_id in coords:
                continue
            try:
                data = await self._do_request(
                    client,
                    f"/stations/{station_id}",
                    {},
                )
                if "latitude" in data and "longitude" in data:
                    coords[station_id] = {
                        "latitude": data["latitude"],
                        "longitude": data["longitude"],
                        "elevation": data.get("elevation"),
                    }
            except (httpx.HTTPStatusError, httpx.TransportError):
                logger.warning(
                    "noaa.station_lookup_failed", station_id=station_id
                )
        return coords

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
        """Execute a GET request to the CDO API with retry logic.

        Args:
            client: The HTTP client.
            path: API path (e.g. ``"/data"``).
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        async with self._rate_semaphore:
            logger.debug("noaa.request", path=path, params=params)
            response = await client.get(path, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


def _parse_quality_flag(record: dict[str, Any]) -> int:
    """Extract a numeric quality flag from a CDO record's attributes.

    NOAA attributes are a comma-separated string; the first character
    of certain flags represents measurement quality (0 = passed all QC).

    Args:
        record: A single CDO result dict.

    Returns:
        Integer quality flag (0–9).  Defaults to 0 when parsing fails.
    """
    attrs = record.get("attributes", "")
    if not attrs:
        return 0
    # First flag character is typically the measurement flag
    first_char = attrs.strip().split(",")[0].strip()
    if first_char.isdigit():
        return int(first_char)
    return 0


__all__ = ["NOAAClimateSource", "NOAA_DATASETS"]
