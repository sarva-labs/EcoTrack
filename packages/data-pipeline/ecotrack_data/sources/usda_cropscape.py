"""USDA CropScape/Cropland Data Layer source.

Provides crop-specific land cover data for the US.

Endpoint: https://nassgeodata.gmu.edu/CropScape
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator

import httpx
from ecotrack.logging import get_logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult

logger = get_logger(__name__)

#: CDL crop type code → human-readable name (selected major crops).
CDL_CROP_CODES: dict[int, str] = {
    1: "Corn",
    2: "Cotton",
    3: "Rice",
    4: "Sorghum",
    5: "Soybeans",
    6: "Sunflower",
    21: "Barley",
    23: "Spring Wheat",
    24: "Winter Wheat",
    26: "Double Crop Winter Wheat/Soybeans",
    27: "Rye",
    28: "Oats",
    36: "Alfalfa",
    37: "Other Hay/Non Alfalfa",
    41: "Sugarbeets",
    42: "Dry Beans",
    43: "Potatoes",
    44: "Other Crops",
    61: "Fallow/Idle Cropland",
    111: "Open Water",
    121: "Developed/Open Space",
    131: "Barren",
    141: "Deciduous Forest",
    142: "Evergreen Forest",
    143: "Mixed Forest",
    152: "Shrubland",
    171: "Grassland/Pasture",
    176: "Grass/Pasture",
    190: "Woody Wetlands",
    195: "Herbaceous Wetlands",
}

_DEFAULT_CROPSCAPE_URL = "https://nassgeodata.gmu.edu/CropScape"


def _default_config() -> DataSourceConfig:
    """Build a default :class:`DataSourceConfig` for CropScape."""
    return DataSourceConfig(
        name="usda_cropscape",
        base_url=_DEFAULT_CROPSCAPE_URL,
        api_key=None,  # CropScape API is public
        rate_limit_per_second=2.0,
        timeout_seconds=60.0,
        max_retries=3,
        formats=[DataFormat.JSON, DataFormat.COG],
    )


class USDAcropSource(DataSource[dict]):
    """USDA CropScape / Cropland Data Layer connector.

    Queries the CropScape NASS API for crop-specific land cover data
    and returns crop type distribution statistics as dicts.

    The CropScape API is public and does not require authentication.

    Example::

        async with USDAcropSource() as src:
            async for result in src.fetch(
                bbox=(-90.5, 38.0, -89.5, 39.0),
                year=2023,
            ):
                stats = await src.transform(result)
    """

    def __init__(
        self,
        config: DataSourceConfig | None = None,
    ) -> None:
        super().__init__(config or _default_config())
        self._rate_semaphore = asyncio.Semaphore(
            max(1, int(self.config.rate_limit_per_second))
        )

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        *,
        year: int | None = None,
        fips: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Fetch crop data from the CropScape API.

        The CropScape API supports two main query modes:

        1. **Bounding-box acreage**: returns crop type distribution
           statistics for a given bbox and year.
        2. **FIPS county**: returns crop data for a US county.

        Args:
            bbox: Bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
            start_time: Ignored by CropScape; use *year* instead.
            end_time: Ignored by CropScape; use *year* instead.
            year: CDL year (e.g. ``2023``).  Defaults to most recent.
            fips: US FIPS county code (e.g. ``"17019"`` for Champaign, IL).
            **kwargs: Extra query parameters.

        Yields:
            :class:`FetchResult` containing crop distribution data.
        """
        if year is None:
            year = (start_time.year if start_time else datetime.utcnow().year - 1)

        client = await self._get_client()

        if bbox is not None:
            data = await self._fetch_bbox_acreage(client, bbox, year)
        elif fips is not None:
            data = await self._fetch_fips_acreage(client, fips, year)
        else:
            raise ValueError("Either bbox or fips must be provided")

        raw_bytes = str(data).encode()
        result = FetchResult(
            source="usda_cropscape",
            timestamp=datetime.utcnow(),
            data=data,
            format=DataFormat.JSON,
            size_bytes=len(raw_bytes),
            checksum=self.compute_checksum(raw_bytes),
            metadata={
                "year": year,
                "bbox": list(bbox) if bbox else None,
                "fips": fips,
            },
        )
        yield result

        logger.info(
            "usda_cropscape.fetch_complete",
            year=year,
            num_categories=len(data) if isinstance(data, list) else 1,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, result: FetchResult) -> bool:
        """Validate that *result* contains well-formed CropScape data.

        Accepts either a list of crop-acreage dicts or a single summary
        dict returned by the API.

        Args:
            result: A :class:`FetchResult` from :pymethod:`fetch`.

        Returns:
            ``True`` when the data passes validation.
        """
        data = result.data
        if isinstance(data, list):
            if len(data) == 0:
                logger.warning("usda_cropscape.validate_empty")
                return False
            # Each entry should have a category/acreage pair
            for entry in data:
                if not isinstance(entry, dict):
                    return False
            return True
        if isinstance(data, dict):
            return len(data) > 0
        logger.warning("usda_cropscape.validate_bad_type", data_type=type(data).__name__)
        return False

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    async def transform(self, result: FetchResult) -> list[dict]:
        """Transform CropScape acreage data into normalised crop statistics.

        Each returned dict contains:
        - ``crop_code``: CDL integer code
        - ``crop_name``: Human-readable name
        - ``acreage``: Area in acres
        - ``percentage``: Percentage of total area
        - ``year``: CDL year

        Args:
            result: Validated :class:`FetchResult`.

        Returns:
            List of normalised crop statistic dicts, sorted by acreage descending.
        """
        raw = result.data
        year = result.metadata.get("year", 0)

        if isinstance(raw, dict):
            raw = [raw]

        stats: list[dict[str, Any]] = []
        total_acreage = 0.0

        for entry in raw:
            acreage = _parse_acreage(entry)
            if acreage is not None and acreage > 0:
                total_acreage += acreage

        for entry in raw:
            crop_code = _parse_crop_code(entry)
            acreage = _parse_acreage(entry)
            if crop_code is None or acreage is None or acreage <= 0:
                continue

            crop_name = CDL_CROP_CODES.get(
                crop_code, entry.get("cropName", entry.get("category", f"Code_{crop_code}"))
            )
            pct = (acreage / total_acreage * 100) if total_acreage > 0 else 0.0

            stats.append(
                {
                    "crop_code": crop_code,
                    "crop_name": crop_name,
                    "acreage": round(acreage, 2),
                    "percentage": round(pct, 2),
                    "year": year,
                }
            )

        stats.sort(key=lambda s: s["acreage"], reverse=True)
        logger.info("usda_cropscape.transform_complete", count=len(stats))
        return stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    )
    async def _fetch_bbox_acreage(
        self,
        client: httpx.AsyncClient,
        bbox: tuple[float, float, float, float],
        year: int,
    ) -> list[dict[str, Any]]:
        """Fetch crop acreage statistics for a bounding box.

        Uses the ``/api/GetCDLStat`` endpoint.

        Args:
            client: HTTP client.
            bbox: ``(min_lon, min_lat, max_lon, max_lat)``.
            year: CDL year.

        Returns:
            List of category/acreage dicts from the API.
        """
        async with self._rate_semaphore:
            params = {
                "year": year,
                "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
                "format": "json",
            }
            logger.debug("usda_cropscape.bbox_request", params=params)
            response = await client.get("/api/GetCDLStat", params=params)
            response.raise_for_status()
            data = response.json()

            # API may return data under various keys
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("cropData", data.get("data", [data]))
            return [data]

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    )
    async def _fetch_fips_acreage(
        self,
        client: httpx.AsyncClient,
        fips: str,
        year: int,
    ) -> list[dict[str, Any]]:
        """Fetch crop acreage statistics for a US county by FIPS code.

        Uses the ``/api/GetCDLStat`` endpoint with a FIPS parameter.

        Args:
            client: HTTP client.
            fips: 5-digit US FIPS county code.
            year: CDL year.

        Returns:
            List of category/acreage dicts from the API.
        """
        async with self._rate_semaphore:
            params = {
                "year": year,
                "fips": fips,
                "format": "json",
            }
            logger.debug("usda_cropscape.fips_request", params=params)
            response = await client.get("/api/GetCDLStat", params=params)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("cropData", data.get("data", [data]))
            return [data]


def _parse_crop_code(entry: dict[str, Any]) -> int | None:
    """Extract a crop code integer from a CropScape entry.

    Args:
        entry: A single CropScape result dict.

    Returns:
        Integer crop code or ``None``.
    """
    for key in ("category", "cropCode", "code", "Category"):
        val = entry.get(key)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                continue
    return None


def _parse_acreage(entry: dict[str, Any]) -> float | None:
    """Extract acreage value from a CropScape entry.

    Args:
        entry: A single CropScape result dict.

    Returns:
        Acreage as float or ``None``.
    """
    for key in ("acreage", "Acreage", "value", "Value", "area"):
        val = entry.get(key)
        if val is not None:
            try:
                return float(str(val).replace(",", ""))
            except (ValueError, TypeError):
                continue
    return None


__all__ = ["USDAcropSource", "CDL_CROP_CODES"]
