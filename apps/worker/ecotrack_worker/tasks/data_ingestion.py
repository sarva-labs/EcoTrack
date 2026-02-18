"""Data ingestion background tasks."""
from __future__ import annotations

from typing import Any

from ecotrack_worker.main import app


@app.task(name="data_ingestion.ingest_climate_data")
def ingest_climate_data(source: str, bbox: dict[str, float], **kwargs: Any) -> dict[str, Any]:
    """Ingest climate data from an external source.

    Args:
        source: Data source identifier.
        bbox: Bounding box as dict with min_lon, min_lat, max_lon, max_lat.
        **kwargs: Additional source-specific parameters.

    Returns:
        Ingestion result summary.
    """
    # TODO: Implement using ecotrack_data pipeline
    return {"status": "stub", "source": source, "records_ingested": 0}


@app.task(name="data_ingestion.ingest_biodiversity_data")
def ingest_biodiversity_data(source: str, **kwargs: Any) -> dict[str, Any]:
    """Ingest biodiversity observation data.

    Args:
        source: Data source identifier (e.g., 'gbif', 'inat').
        **kwargs: Additional parameters.

    Returns:
        Ingestion result summary.
    """
    # TODO: Implement using ecotrack_data pipeline
    return {"status": "stub", "source": source, "records_ingested": 0}


@app.task(name="data_ingestion.ingest_satellite_imagery")
def ingest_satellite_imagery(
    collection: str,
    bbox: dict[str, float],
    **kwargs: Any,
) -> dict[str, Any]:
    """Ingest satellite imagery from STAC catalogs.

    Args:
        collection: STAC collection identifier.
        bbox: Bounding box.
        **kwargs: Additional parameters.

    Returns:
        Ingestion result summary.
    """
    # TODO: Implement using pystac-client and planetary-computer
    return {"status": "stub", "collection": collection, "scenes_ingested": 0}
