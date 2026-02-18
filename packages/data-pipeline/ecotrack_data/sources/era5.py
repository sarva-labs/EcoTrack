"""ERA5 Climate Reanalysis data source.

Provides access to ERA5 global reanalysis data from the
Copernicus Climate Data Store (CDS).

Endpoint: https://cds.climate.copernicus.eu/api
"""
from __future__ import annotations

import asyncio
import time
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

#: ERA5 variable mapping: CDS variable name → (ClimateVariable, unit).
ERA5_VARIABLES: dict[str, tuple[ClimateVariable, str]] = {
    "2m_temperature": (ClimateVariable.TEMPERATURE, "K"),
    "total_precipitation": (ClimateVariable.PRECIPITATION, "m"),
    "10m_u_component_of_wind": (ClimateVariable.WIND_SPEED, "m/s"),
    "10m_v_component_of_wind": (ClimateVariable.WIND_SPEED, "m/s"),
    "surface_pressure": (ClimateVariable.PRESSURE, "Pa"),
    "2m_dewpoint_temperature": (ClimateVariable.HUMIDITY, "K"),
    "soil_temperature_level_1": (ClimateVariable.SOIL_MOISTURE, "K"),
    "sea_surface_temperature": (ClimateVariable.SEA_SURFACE_TEMP, "K"),
}

_DEFAULT_CDS_URL = "https://cds.climate.copernicus.eu/api"

#: CDS request statuses
_STATUS_COMPLETED = "successful"
_STATUS_FAILED = "failed"
_STATUS_RUNNING = "running"
_STATUS_QUEUED = "queued"

_POLL_INTERVAL_S = 10.0
_MAX_POLL_ATTEMPTS = 360  # 1 hour max wait


def _default_config(api_key: str | None = None) -> DataSourceConfig:
    """Build a default :class:`DataSourceConfig` for CDS."""
    return DataSourceConfig(
        name="era5",
        base_url=_DEFAULT_CDS_URL,
        api_key=api_key,
        rate_limit_per_second=1.0,
        timeout_seconds=120.0,
        max_retries=3,
        formats=[DataFormat.NETCDF, DataFormat.GRIB2],
    )


class ERA5Source(DataSource[ClimateObservation]):
    """ERA5 Climate Data Store connector.

    Submits data retrieval requests to the CDS API, polls for
    completion, downloads the resulting NetCDF files, and transforms
    them into :class:`ClimateObservation` domain models.

    Authentication requires a CDS API key (``UID:API-KEY`` format)
    obtained from https://cds.climate.copernicus.eu/user.

    Example::

        async with ERA5Source(api_key="12345:abcdef-...") as src:
            async for result in src.fetch(
                bbox=(-10, 35, 5, 45),
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                variables=["2m_temperature", "total_precipitation"],
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
        self._rate_semaphore = asyncio.Semaphore(1)

    async def _get_client(self) -> httpx.AsyncClient:
        """Override to use CDS ``UID:KEY`` Basic authentication."""
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Accept": "application/json"}
            if self.config.api_key:
                headers["PRIVATE-TOKEN"] = self.config.api_key
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
        variables: list[str] | None = None,
        product_type: str = "reanalysis",
        pressure_levels: list[int] | None = None,
        output_format: str = "netcdf",
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Submit a CDS retrieval request and yield the result on completion.

        The CDS API is asynchronous: a request is submitted, then polled
        until the data is ready.  This method handles the full lifecycle.

        Args:
            bbox: Bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
                Converted to ``area`` = ``[north, west, south, east]``.
            start_time: Start of temporal range (day resolution).
            end_time: End of temporal range.
            variables: ERA5 variable short names
                (default: ``["2m_temperature"]``).
            product_type: ``"reanalysis"`` or ``"ensemble_members"``.
            pressure_levels: Pressure levels in hPa (only for pressure-level datasets).
            output_format: ``"netcdf"`` or ``"grib"``.
            **kwargs: Extra keys merged into the CDS request body.

        Yields:
            A single :class:`FetchResult` with the downloaded data bytes.
        """
        if variables is None:
            variables = ["2m_temperature"]

        if start_time is None or end_time is None:
            raise ValueError("ERA5 requires both start_time and end_time")

        client = await self._get_client()

        request_body = self._build_request_body(
            bbox=bbox,
            start_time=start_time,
            end_time=end_time,
            variables=variables,
            product_type=product_type,
            pressure_levels=pressure_levels,
            output_format=output_format,
        )
        request_body.update(kwargs)

        # 1. Submit the request
        logger.info(
            "era5.submit_request",
            variables=variables,
            start=str(start_time),
            end=str(end_time),
        )
        task_info = await self._submit_request(client, request_body)
        task_url = task_info.get("request_id") or task_info.get("requestId", "")

        # 2. Poll until complete
        download_url = await self._poll_until_complete(client, task_url)

        # 3. Download the data
        data_bytes = await self._download_result(client, download_url)

        fmt = DataFormat.NETCDF if output_format == "netcdf" else DataFormat.GRIB2
        result = FetchResult(
            source="era5",
            timestamp=datetime.utcnow(),
            data=data_bytes,
            format=fmt,
            size_bytes=len(data_bytes),
            checksum=self.compute_checksum(data_bytes),
            metadata={
                "variables": variables,
                "product_type": product_type,
                "start_time": str(start_time),
                "end_time": str(end_time),
                "output_format": output_format,
            },
        )
        yield result

        logger.info(
            "era5.fetch_complete",
            size_mb=round(len(data_bytes) / 1_048_576, 2),
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, result: FetchResult) -> bool:
        """Validate the downloaded ERA5 data.

        Checks that the data is non-empty bytes and the format matches
        expected magic bytes for NetCDF (``\\x89HDF`` or ``CDF``) or
        GRIB (``GRIB``).

        Args:
            result: A :class:`FetchResult` from :pymethod:`fetch`.

        Returns:
            ``True`` when the data passes format validation.
        """
        if not isinstance(result.data, bytes) or len(result.data) == 0:
            logger.warning("era5.validate_empty")
            return False

        header = result.data[:4]
        if result.format == DataFormat.NETCDF:
            if not (header.startswith(b"CDF") or header.startswith(b"\x89HDF")):
                logger.warning("era5.validate_bad_header", header=header[:4])
                return False
        elif result.format == DataFormat.GRIB2:
            if not header.startswith(b"GRIB"):
                logger.warning("era5.validate_bad_header", header=header[:4])
                return False
        return True

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    async def transform(self, result: FetchResult) -> list[ClimateObservation]:
        """Transform ERA5 NetCDF data into :class:`ClimateObservation` models.

        Uses :mod:`xarray` to open the in-memory dataset and extracts
        a list of observations at each grid point and time step.

        Temperature values are converted from Kelvin to Celsius.
        Precipitation is converted from metres to millimetres.

        Args:
            result: Validated :class:`FetchResult`.

        Returns:
            List of :class:`ClimateObservation` instances.
        """
        import io

        import numpy as np
        import xarray as xr

        observations: list[ClimateObservation] = []

        ds = xr.open_dataset(io.BytesIO(result.data), engine="scipy")

        try:
            for var_name in ds.data_vars:
                var_str = str(var_name)
                era5_info = ERA5_VARIABLES.get(var_str)
                if era5_info is None:
                    continue

                climate_var, raw_unit = era5_info
                da = ds[var_name]

                # Iterate over time steps
                times = da.coords.get("time", da.coords.get("valid_time"))
                if times is None:
                    continue

                for t_idx, t_val in enumerate(times.values):
                    timestamp = _numpy_dt_to_datetime(t_val)
                    slice_2d = da.isel(time=t_idx) if "time" in da.dims else da

                    lats = slice_2d.coords.get(
                        "latitude", slice_2d.coords.get("lat")
                    )
                    lons = slice_2d.coords.get(
                        "longitude", slice_2d.coords.get("lon")
                    )
                    if lats is None or lons is None:
                        continue

                    # Sub-sample for large grids to avoid millions of records
                    lat_vals = lats.values
                    lon_vals = lons.values
                    step = max(1, len(lat_vals) // 50)

                    for lat_i in range(0, len(lat_vals), step):
                        for lon_i in range(0, len(lon_vals), step):
                            raw_val = float(slice_2d.values[lat_i, lon_i])
                            if np.isnan(raw_val):
                                continue

                            value, unit = _convert_era5_value(
                                var_str, raw_val, raw_unit
                            )

                            obs = ClimateObservation(
                                variable=climate_var,
                                value=round(value, 4),
                                unit=unit,
                                location=GeoPoint(
                                    latitude=float(lat_vals[lat_i]),
                                    longitude=float(lon_vals[lon_i]),
                                ),
                                timestamp=timestamp,
                                source="era5",
                                quality_flag=0,
                                metadata={
                                    "era5_variable": var_str,
                                    "product_type": result.metadata.get(
                                        "product_type", "reanalysis"
                                    ),
                                },
                            )
                            observations.append(obs)
        finally:
            ds.close()

        logger.info("era5.transform_complete", count=len(observations))
        return observations

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_request_body(
        *,
        bbox: tuple[float, float, float, float] | None,
        start_time: datetime,
        end_time: datetime,
        variables: list[str],
        product_type: str,
        pressure_levels: list[int] | None,
        output_format: str,
    ) -> dict[str, Any]:
        """Construct the CDS API request body."""
        # Determine years, months, days, and hours
        years = sorted(
            {str(y) for y in range(start_time.year, end_time.year + 1)}
        )
        months = sorted(
            {f"{m:02d}" for m in range(1, 13)}
            if start_time.year != end_time.year
            else {f"{m:02d}" for m in range(start_time.month, end_time.month + 1)}
        )
        days = [f"{d:02d}" for d in range(1, 32)]
        hours = [f"{h:02d}:00" for h in range(0, 24, 6)]

        body: dict[str, Any] = {
            "product_type": product_type,
            "variable": variables,
            "year": years,
            "month": months,
            "day": days,
            "time": hours,
            "format": output_format,
        }
        if bbox is not None:
            # CDS area: [north, west, south, east]
            body["area"] = [bbox[3], bbox[0], bbox[1], bbox[2]]
        if pressure_levels:
            body["pressure_level"] = [str(p) for p in pressure_levels]
        return body

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        reraise=True,
    )
    async def _submit_request(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a retrieval request to the CDS API.

        Args:
            client: HTTP client.
            body: CDS request body.

        Returns:
            Response JSON containing the request ID and initial state.
        """
        async with self._rate_semaphore:
            response = await client.post(
                "/v1/resources/reanalysis-era5-single-levels",
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def _poll_until_complete(
        self, client: httpx.AsyncClient, request_id: str
    ) -> str:
        """Poll the CDS API until the request completes.

        Args:
            client: HTTP client.
            request_id: The CDS request ID.

        Returns:
            Download URL for the completed dataset.

        Raises:
            RuntimeError: If the request fails or times out.
        """
        for attempt in range(_MAX_POLL_ATTEMPTS):
            response = await client.get(f"/v1/tasks/{request_id}")
            response.raise_for_status()
            state = response.json()

            status = state.get("state", state.get("status", "")).lower()
            logger.debug(
                "era5.poll",
                request_id=request_id,
                status=status,
                attempt=attempt,
            )

            if status == _STATUS_COMPLETED:
                download_url = state.get("location", state.get("result_url", ""))
                if download_url:
                    return download_url
                raise RuntimeError(
                    f"ERA5 request {request_id} completed but no download URL found"
                )

            if status == _STATUS_FAILED:
                reason = state.get("error", {}).get("message", "Unknown error")
                raise RuntimeError(
                    f"ERA5 request {request_id} failed: {reason}"
                )

            await asyncio.sleep(_POLL_INTERVAL_S)

        raise RuntimeError(
            f"ERA5 request {request_id} timed out after "
            f"{_MAX_POLL_ATTEMPTS * _POLL_INTERVAL_S}s"
        )

    @retry(
        retry=retry_if_exception_type((httpx.TransportError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        reraise=True,
    )
    async def _download_result(
        self, client: httpx.AsyncClient, url: str
    ) -> bytes:
        """Download the completed dataset.

        Args:
            client: HTTP client.
            url: Download URL.

        Returns:
            Raw data bytes.
        """
        logger.info("era5.downloading", url=url)
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _numpy_dt_to_datetime(np_dt: Any) -> datetime:
    """Convert a numpy datetime64 to a Python datetime.

    Args:
        np_dt: A numpy ``datetime64`` or pandas ``Timestamp``.

    Returns:
        A Python :class:`datetime`.
    """
    import numpy as np

    ts = (np_dt - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
    return datetime.utcfromtimestamp(float(ts))


def _convert_era5_value(
    variable: str, raw_value: float, raw_unit: str
) -> tuple[float, str]:
    """Convert ERA5 raw values to human-friendly units.

    Args:
        variable: ERA5 variable short name.
        raw_value: Value in the native unit.
        raw_unit: Native unit string.

    Returns:
        Tuple of ``(converted_value, unit_string)``.
    """
    if raw_unit == "K" and "temperature" in variable:
        return raw_value - 273.15, "°C"
    if variable == "total_precipitation":
        return raw_value * 1000.0, "mm"
    if raw_unit == "Pa" and "pressure" in variable:
        return raw_value / 100.0, "hPa"
    return raw_value, raw_unit


__all__ = ["ERA5Source", "ERA5_VARIABLES"]
