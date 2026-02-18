"""GBIF (Global Biodiversity Information Facility) data source.

Provides access to species occurrence records from the world's
largest biodiversity database.

Endpoint: https://api.gbif.org/v1
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator

import httpx
from ecotrack.logging import get_logger
from ecotrack.models.biodiversity import SpeciesObservation
from ecotrack.models.geospatial import GeoPoint
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import DataFormat, DataSource, DataSourceConfig, FetchResult

logger = get_logger(__name__)

#: Common GBIF basis-of-record values.
GBIF_BASIS_OF_RECORD: list[str] = [
    "HUMAN_OBSERVATION",
    "MACHINE_OBSERVATION",
    "PRESERVED_SPECIMEN",
    "FOSSIL_SPECIMEN",
    "MATERIAL_SAMPLE",
    "LIVING_SPECIMEN",
    "OCCURRENCE",
]

_DEFAULT_GBIF_URL = "https://api.gbif.org/v1"
_PAGE_LIMIT = 300  # GBIF max per request


def _default_config() -> DataSourceConfig:
    """Build a default :class:`DataSourceConfig` for GBIF."""
    return DataSourceConfig(
        name="gbif",
        base_url=_DEFAULT_GBIF_URL,
        api_key=None,  # GBIF public API requires no key for occurrences
        rate_limit_per_second=10.0,
        timeout_seconds=30.0,
        max_retries=3,
        formats=[DataFormat.JSON],
    )


class GBIFSource(DataSource[SpeciesObservation]):
    """GBIF occurrence API connector.

    Queries the GBIF REST API for species occurrence records and
    transforms them into :class:`SpeciesObservation` domain models.

    GBIF's occurrence search endpoint is public and does not require
    authentication for read-only access, though registering for API
    credentials is recommended for higher rate limits.

    Example::

        async with GBIFSource() as src:
            async for result in src.fetch(
                bbox=(-10, 35, 5, 45),
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 6, 30),
                taxon_key=212,  # Aves (birds)
            ):
                observations = await src.transform(result)
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
        taxon_key: int | None = None,
        country: str | None = None,
        basis_of_record: str | None = None,
        has_coordinate: bool = True,
        has_geospatial_issue: bool = False,
        max_items: int = 5000,
        **kwargs: Any,
    ) -> AsyncIterator[FetchResult]:
        """Fetch species occurrence records from the GBIF API.

        Args:
            bbox: Bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
                Translated to a GBIF ``geometry`` WKT polygon.
            start_time: Temporal range start (year resolution in GBIF).
            end_time: Temporal range end.
            taxon_key: GBIF backbone taxonomy key to filter by.
            country: ISO 3166-1 alpha-2 country code.
            basis_of_record: Filter by evidence type (e.g. ``HUMAN_OBSERVATION``).
            has_coordinate: Only return georeferenced records (default ``True``).
            has_geospatial_issue: Exclude records with geospatial issues (default ``False``).
            max_items: Maximum total records to retrieve.
            **kwargs: Extra query parameters forwarded to the API.

        Yields:
            :class:`FetchResult` containing a list of occurrence dicts.
        """
        client = await self._get_client()
        offset = 0
        items_yielded = 0

        while items_yielded < max_items:
            limit = min(_PAGE_LIMIT, max_items - items_yielded)
            params = self._build_query_params(
                bbox=bbox,
                start_time=start_time,
                end_time=end_time,
                taxon_key=taxon_key,
                country=country,
                basis_of_record=basis_of_record,
                has_coordinate=has_coordinate,
                has_geospatial_issue=has_geospatial_issue,
                offset=offset,
                limit=limit,
            )
            params.update(kwargs)

            data = await self._do_request(client, "/occurrence/search", params)
            results: list[dict[str, Any]] = data.get("results", [])
            end_of_records: bool = data.get("endOfRecords", True)

            if not results:
                logger.info(
                    "gbif.fetch_exhausted",
                    offset=offset,
                    total_yielded=items_yielded,
                )
                break

            raw_bytes = str(results).encode()
            result = FetchResult(
                source="gbif",
                timestamp=datetime.utcnow(),
                data=results,
                format=DataFormat.JSON,
                size_bytes=len(raw_bytes),
                checksum=self.compute_checksum(raw_bytes),
                metadata={
                    "offset": offset,
                    "returned": len(results),
                    "total_count": data.get("count", 0),
                    "end_of_records": end_of_records,
                },
            )
            yield result
            items_yielded += len(results)
            offset += len(results)

            if end_of_records:
                break

        logger.info(
            "gbif.fetch_complete",
            total_items=items_yielded,
            taxon_key=taxon_key,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self, result: FetchResult) -> bool:
        """Validate that *result* contains well-formed GBIF occurrence records.

        Each record must have ``species``, ``decimalLatitude``,
        ``decimalLongitude``, and ``eventDate``.

        Args:
            result: A :class:`FetchResult` from :pymethod:`fetch`.

        Returns:
            ``True`` when all records pass validation.
        """
        if not isinstance(result.data, list) or len(result.data) == 0:
            logger.warning("gbif.validate_empty", source=result.source)
            return False

        for record in result.data:
            if "decimalLatitude" not in record or "decimalLongitude" not in record:
                logger.warning(
                    "gbif.validate_missing_coords",
                    gbif_id=record.get("gbifID"),
                )
                return False
            if "species" not in record and "scientificName" not in record:
                logger.warning(
                    "gbif.validate_missing_species",
                    gbif_id=record.get("gbifID"),
                )
                return False
        return True

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    async def transform(self, result: FetchResult) -> list[SpeciesObservation]:
        """Transform GBIF occurrence records into :class:`SpeciesObservation` models.

        Args:
            result: Validated :class:`FetchResult`.

        Returns:
            List of :class:`SpeciesObservation` instances.
        """
        observations: list[SpeciesObservation] = []

        for record in result.data:
            try:
                obs = self._record_to_observation(record)
                if obs is not None:
                    observations.append(obs)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "gbif.transform_record_failed",
                    error=str(exc),
                    gbif_id=record.get("gbifID"),
                )

        logger.info("gbif.transform_complete", count=len(observations))
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
        taxon_key: int | None,
        country: str | None,
        basis_of_record: str | None,
        has_coordinate: bool,
        has_geospatial_issue: bool,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        """Build query parameters for ``/occurrence/search``."""
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
            "hasCoordinate": str(has_coordinate).lower(),
            "hasGeospatialIssue": str(has_geospatial_issue).lower(),
        }
        if bbox is not None:
            # GBIF uses a WKT polygon for geometry filter
            min_lon, min_lat, max_lon, max_lat = bbox
            wkt = (
                f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},"
                f"{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
            )
            params["geometry"] = wkt
        if start_time and end_time:
            params["eventDate"] = (
                f"{start_time.strftime('%Y-%m-%d')},"
                f"{end_time.strftime('%Y-%m-%d')}"
            )
        elif start_time:
            params["eventDate"] = start_time.strftime("%Y-%m-%d")
        if taxon_key is not None:
            params["taxonKey"] = taxon_key
        if country:
            params["country"] = country
        if basis_of_record:
            params["basisOfRecord"] = basis_of_record
        return params

    @staticmethod
    def _record_to_observation(record: dict[str, Any]) -> SpeciesObservation | None:
        """Convert a single GBIF occurrence record to a domain model.

        Args:
            record: A single GBIF occurrence dict.

        Returns:
            A :class:`SpeciesObservation` or ``None`` if essential data is missing.
        """
        lat = record.get("decimalLatitude")
        lon = record.get("decimalLongitude")
        if lat is None or lon is None:
            return None

        species_name = record.get("species") or record.get("scientificName", "")
        if not species_name:
            return None

        # Parse event date
        event_date_str = record.get("eventDate", "")
        if not event_date_str:
            return None

        try:
            # GBIF dates can be partial (e.g. "2024-06")
            if len(event_date_str) == 4:
                observed_at = datetime(int(event_date_str), 1, 1)
            elif len(event_date_str) == 7:
                observed_at = datetime.strptime(event_date_str, "%Y-%m")
            elif "T" in event_date_str:
                observed_at = datetime.fromisoformat(
                    event_date_str.replace("Z", "+00:00")
                )
            else:
                observed_at = datetime.strptime(event_date_str[:10], "%Y-%m-%d")
        except (ValueError, IndexError):
            return None

        count = record.get("individualCount", 1) or 1

        return SpeciesObservation(
            species_name=species_name,
            location=GeoPoint(
                latitude=lat,
                longitude=lon,
                elevation_m=record.get("elevation"),
            ),
            observed_at=observed_at,
            observer=record.get("recordedBy"),
            count=max(1, count),
            evidence_type=record.get("basisOfRecord", "HUMAN_OBSERVATION").lower(),
            confidence=_occurrence_confidence(record),
            source_dataset=f"gbif:{record.get('datasetKey', '')}",
            metadata={
                "gbif_id": record.get("gbifID"),
                "taxon_key": record.get("taxonKey"),
                "kingdom": record.get("kingdom", ""),
                "phylum": record.get("phylum", ""),
                "class": record.get("class", ""),
                "order": record.get("order", ""),
                "family": record.get("family", ""),
                "genus": record.get("genus", ""),
                "issues": record.get("issues", []),
                "institution_code": record.get("institutionCode", ""),
            },
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
        """Execute a GET request to the GBIF API with retry logic.

        Args:
            client: The HTTP client.
            path: API path.
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        async with self._rate_semaphore:
            logger.debug("gbif.request", path=path, params=params)
            response = await client.get(path, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


def _occurrence_confidence(record: dict[str, Any]) -> float:
    """Estimate a confidence score for a GBIF occurrence record.

    Heuristic based on coordinate uncertainty, number of issues, and
    presence of multimedia evidence.

    Args:
        record: A single GBIF occurrence dict.

    Returns:
        Confidence between 0.0 and 1.0.
    """
    score = 1.0

    # Penalise for coordinate uncertainty
    uncertainty = record.get("coordinateUncertaintyInMeters")
    if uncertainty is not None:
        if uncertainty > 10000:
            score -= 0.3
        elif uncertainty > 1000:
            score -= 0.1

    # Penalise for quality issues
    issues = record.get("issues", [])
    if issues:
        score -= min(0.3, len(issues) * 0.05)

    # Reward for multimedia evidence
    if record.get("media"):
        score += 0.05

    return max(0.0, min(1.0, score))


__all__ = ["GBIFSource", "GBIF_BASIS_OF_RECORD"]
