"""Copernicus Data Space Ecosystem data source.

Provides access to Sentinel-1 (SAR), Sentinel-2 (optical),
Sentinel-3 (ocean/land), and Sentinel-5P (atmospheric) data
via the Copernicus STAC API.

Endpoint: https://catalogue.dataspace.copernicus.eu/stac
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

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult

logger = get_logger(__name__)

#: Well-known Copernicus STAC collections.
COPERNICUS_COLLECTIONS: dict[str, str] = {
    "sentinel-2-l2a": "SENTINEL-2",
    "sentinel-1-grd": "SENTINEL-1",
    "sentinel-3-olci-lfr": "SENTINEL-3",
    "sentinel-5p-l2": "SENTINEL-5P",
}

_DEFAULT_COPERNICUS_URL = "https://catalogue.dataspace.copernicus.eu/stac"


def _default_config(api_key: str | None = None) -> DataSourceConfig:
    """Build a default :class:`DataSourceConfig` for the Copernicus STAC API."""
    return DataSourceConfig(
        name="copernicus",
        base_url=_DEFAULT_COPERNICUS_URL,
        api_key=api_key,
        rate_limit_per_second=2.0,
        timeout_seconds=60.0,
        max_retries=3,
        formats=[DataFormat.STAC, DataFormat.COG],
    )


class CopernicusSource(DataSource[dict]):
    """Copernicus Data Space STAC connector.

    Searches the Copernicus STAC catalogue for Sentinel imagery and
    returns item metadata dictionaries.  COG asset URLs are resolved
    via the signed-URL mechanism when an API key is provided.

    Example::

        async with CopernicusSource() as src:
            async for result in src.fetch(
                bbox=(-10.0, 35.0, 5.0, 45.0),
                start_time=datetime(2024, 6, 1),
                end_time=datetime(2024, 6, 30),
                collections=["sentinel-2-l2a"],
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
        max_items: int = 100,
        cloud_cover_max: float | None = 30.0,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Search the Copernicus STAC API and yield pages of items.

        Args:
            bbox: Bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
            start_time: Temporal range start.
            end_time: Temporal range end.
            collections: STAC collection IDs to search (default: all Sentinel-2 L2A).
            max_items: Maximum number of items to return.
            cloud_cover_max: Maximum cloud cover percentage (Sentinel-2 only).
            **kwargs: Forwarded to the STAC search payload.

        Yields:
            :class:`FetchResult` containing a list of STAC item dicts.
        """
        if collections is None:
            collections = ["sentinel-2-l2a"]

        client = await self._get_client()
        page = 1
        items_yielded = 0

        while items_yielded < max_items:
            payload = self._build_search_payload(
                bbox=bbox,
                start_time=start_time,
                end_time=end_time,
                collections=collections,
                cloud_cover_max=cloud_cover_max,
                page=page,
                limit=min(50, max_items - items_yielded),
            )
            payload.update(kwargs)

            data = await self._do_search(client, payload)
            features: list[dict[str, Any]] = data.get("features", [])

            if not features:
                logger.info(
                    "copernicus.search_exhausted",
                    page=page,
                    total_yielded=items_yielded,
                )
                break

            raw_bytes = str(features).encode()
            result = FetchResult(
                source="copernicus",
                timestamp=datetime.utcnow(),
                data=features,
                format=DataFormat.STAC,
                size_bytes=len(raw_bytes),
                checksum=self.compute_checksum(raw_bytes),
                metadata={
                    "collections": collections,
                    "page": page,
                    "returned": len(features),
                    "context": data.get("context", {}),
                },
            )
            yield result
            items_yielded += len(features)
            page += 1

        logger.info(
            "copernicus.fetch_complete",
            total_items=items_yielded,
            collections=collections,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, result: FetchResult) -> bool:
        """Validate that *result* contains well-formed STAC items.

        Checks:
        - Data is a non-empty list.
        - Each item has ``id``, ``type``, ``geometry``, and ``properties``.

        Args:
            result: A :class:`FetchResult` from :pymethod:`fetch`.

        Returns:
            ``True`` when all items pass structural validation.
        """
        if not isinstance(result.data, list) or len(result.data) == 0:
            logger.warning("copernicus.validate_empty", source=result.source)
            return False

        for item in result.data:
            required = {"id", "type", "geometry", "properties"}
            if not required.issubset(item.keys()):
                logger.warning(
                    "copernicus.validate_missing_keys",
                    item_id=item.get("id"),
                    missing=required - item.keys(),
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
        - ``cloud_cover``: Cloud cover percentage (if available)
        - ``assets``: Mapping of asset key → href
        - ``geometry``: GeoJSON geometry

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
                    "bbox": raw.get("bbox"),
                    "cloud_cover": props.get("eo:cloud_cover"),
                    "assets": assets,
                    "geometry": raw.get("geometry"),
                    "platform": props.get("platform", ""),
                    "gsd": props.get("gsd"),
                }
            )
        logger.info("copernicus.transform_complete", count=len(items))
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
        cloud_cover_max: float | None,
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        """Construct the STAC search POST body."""
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

        if cloud_cover_max is not None:
            payload.setdefault("query", {})
            payload["query"]["eo:cloud_cover"] = {"lte": cloud_cover_max}

        # Copernicus STAC uses page-based pagination via `page` param in body
        payload["page"] = page
        return payload

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

        Raises:
            httpx.HTTPStatusError: On non-2xx responses after retries.
        """
        async with self._rate_semaphore:
            logger.debug("copernicus.search_request", payload=payload)
            response = await client.post("/search", json=payload)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


__all__ = ["CopernicusSource", "COPERNICUS_COLLECTIONS"]
