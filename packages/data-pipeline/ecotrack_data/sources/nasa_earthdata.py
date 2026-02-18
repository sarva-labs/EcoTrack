"""NASA Earthdata data source.

Provides access to MODIS, Landsat, GPM rainfall, and other datasets
via the NASA CMR STAC API.

Endpoint: https://cmr.earthdata.nasa.gov/stac
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator

from ecotrack.logging import get_logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import httpx

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult

logger = get_logger(__name__)

#: Well-known NASA CMR STAC collection identifiers.
NASA_COLLECTIONS: dict[str, str] = {
    "modis-ndvi": "MODIS/Terra+Aqua NDVI",
    "modis-mod13q1": "MOD13Q1.061",
    "landsat-c2-l2": "Landsat Collection 2 Level-2",
    "gpm-imerg": "GPM_3IMERGHH.07",
    "viirs-vnp46a2": "VNP46A2.001",
    "aster-dem": "ASTGTM.003",
}

_DEFAULT_CMR_STAC_URL = "https://cmr.earthdata.nasa.gov/stac"
_ITEMS_PER_PAGE = 50


def _default_config(api_key: str | None = None) -> DataSourceConfig:
    """Build a default :class:`DataSourceConfig` for NASA CMR STAC."""
    return DataSourceConfig(
        name="nasa_earthdata",
        base_url=_DEFAULT_CMR_STAC_URL,
        api_key=api_key,
        rate_limit_per_second=5.0,
        timeout_seconds=60.0,
        max_retries=3,
        formats=[DataFormat.STAC, DataFormat.COG, DataFormat.NETCDF],
    )


class NASAEarthdataSource(DataSource[dict]):
    """NASA Earthdata CMR STAC connector.

    Searches the CMR STAC API for MODIS, Landsat, GPM, and other
    NASA datasets.  Results are yielded as pages of STAC item dicts.

    Authentication is handled via *Bearer* token passed in the
    ``Authorization`` header.  Obtain a token from
    https://urs.earthdata.nasa.gov/.

    Example::

        async with NASAEarthdataSource(api_key="<EDL_TOKEN>") as src:
            async for result in src.fetch(
                bbox=(-120, 35, -115, 40),
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 31),
                collections=["modis-mod13q1"],
            ):
                items = await src.transform(result)
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

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        *,
        collections: list[str] | None = None,
        max_items: int = 200,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Search the NASA CMR STAC API and yield pages of items.

        Args:
            bbox: Bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
            start_time: Temporal range start.
            end_time: Temporal range end.
            collections: CMR STAC collection IDs to search.
            max_items: Maximum number of items to return across all pages.
            **kwargs: Extra parameters forwarded to the search payload.

        Yields:
            :class:`FetchResult` containing a list of STAC item dicts.
        """
        if collections is None:
            collections = ["MOD13Q1.061"]

        client = await self._get_client()
        items_yielded = 0
        cursor: str | None = None

        while items_yielded < max_items:
            remaining = max_items - items_yielded
            limit = min(_ITEMS_PER_PAGE, remaining)

            payload = self._build_search_payload(
                bbox=bbox,
                start_time=start_time,
                end_time=end_time,
                collections=collections,
                limit=limit,
                cursor=cursor,
            )
            payload.update(kwargs)

            data = await self._do_search(client, payload)
            features: list[dict[str, Any]] = data.get("features", [])

            if not features:
                logger.info(
                    "nasa_earthdata.search_exhausted",
                    total_yielded=items_yielded,
                )
                break

            raw_bytes = str(features).encode()
            result = FetchResult(
                source="nasa_earthdata",
                timestamp=datetime.utcnow(),
                data=features,
                format=DataFormat.STAC,
                size_bytes=len(raw_bytes),
                checksum=self.compute_checksum(raw_bytes),
                metadata={
                    "collections": collections,
                    "returned": len(features),
                    "context": data.get("context", {}),
                },
            )
            yield result
            items_yielded += len(features)

            # CMR STAC uses link-based pagination — find ``next`` link
            cursor = self._extract_next_cursor(data)
            if cursor is None:
                break

        logger.info(
            "nasa_earthdata.fetch_complete",
            total_items=items_yielded,
            collections=collections,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, result: FetchResult) -> bool:
        """Validate that *result* contains well-formed STAC items.

        Args:
            result: A :class:`FetchResult` from :pymethod:`fetch`.

        Returns:
            ``True`` when all items pass structural validation.
        """
        if not isinstance(result.data, list) or len(result.data) == 0:
            logger.warning("nasa_earthdata.validate_empty", source=result.source)
            return False

        for item in result.data:
            if "id" not in item or "properties" not in item:
                logger.warning(
                    "nasa_earthdata.validate_missing_keys",
                    item_id=item.get("id"),
                )
                return False
        return True

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    async def transform(self, result: FetchResult) -> list[dict]:
        """Transform raw STAC items into normalised metadata dicts.

        Each returned dict contains:
        - ``id``: STAC item ID
        - ``collection``: Source collection
        - ``datetime``: Acquisition datetime (ISO-8601)
        - ``bbox``: Bounding box
        - ``assets``: Mapping of asset key → href
        - ``geometry``: GeoJSON geometry
        - ``platform``: Satellite platform name
        - ``instruments``: List of instruments

        Args:
            result: Validated :class:`FetchResult`.

        Returns:
            List of normalised metadata dicts.
        """
        items: list[dict] = []
        for raw in result.data:
            props = raw.get("properties", {})
            assets_raw = raw.get("assets", {})
            assets = {k: v.get("href", "") for k, v in assets_raw.items()}

            items.append(
                {
                    "id": raw.get("id"),
                    "collection": raw.get("collection", ""),
                    "datetime": props.get("datetime"),
                    "start_datetime": props.get("start_datetime"),
                    "end_datetime": props.get("end_datetime"),
                    "bbox": raw.get("bbox"),
                    "assets": assets,
                    "geometry": raw.get("geometry"),
                    "platform": props.get("platform", ""),
                    "instruments": props.get("instruments", []),
                    "cloud_cover": props.get("eo:cloud_cover"),
                }
            )
        logger.info("nasa_earthdata.transform_complete", count=len(items))
        return items

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_search_payload(
        *,
        bbox: tuple[float, float, float, float] | None,
        start_time: datetime | None,
        end_time: datetime | None,
        collections: list[str],
        limit: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        """Construct the STAC search POST body for CMR."""
        payload: dict[str, Any] = {
            "collections": collections,
            "limit": limit,
        }
        if bbox is not None:
            payload["bbox"] = list(bbox)

        if start_time or end_time:
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ") if start_time else ".."
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ") if end_time else ".."
            payload["datetime"] = f"{start_str}/{end_str}"

        if cursor is not None:
            payload["token"] = cursor

        return payload

    @staticmethod
    def _extract_next_cursor(data: dict[str, Any]) -> str | None:
        """Extract the pagination cursor from STAC ``links``."""
        for link in data.get("links", []):
            if link.get("rel") == "next":
                # CMR STAC next link carries a ``body`` with ``token``
                body = link.get("body", {})
                if isinstance(body, dict) and "token" in body:
                    return body["token"]
                # Fallback: parse from href query params
                href = link.get("href", "")
                if "token=" in href:
                    for part in href.split("?")[-1].split("&"):
                        if part.startswith("token="):
                            return part.split("=", 1)[1]
        return None

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _do_search(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a STAC search POST with retry logic.

        Args:
            client: The HTTP client.
            payload: Search body.

        Returns:
            Parsed JSON response.
        """
        async with self._rate_semaphore:
            logger.debug("nasa_earthdata.search_request", payload=payload)
            response = await client.post("/search", json=payload)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


__all__ = ["NASAEarthdataSource", "NASA_COLLECTIONS"]
