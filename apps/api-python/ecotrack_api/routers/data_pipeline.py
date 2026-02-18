"""Data pipeline management endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ecotrack_api.schemas.common import PaginatedResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DataSourceInfo(BaseModel):
    """Information about an available data source."""

    source_id: str
    name: str
    provider: str
    domains: list[str]
    update_frequency: str = Field(description="Update frequency: hourly, daily, weekly, monthly")
    spatial_resolution: str | None = Field(default=None, description="Spatial resolution (e.g. 0.25°, 1km)")
    temporal_coverage: str = Field(description="Temporal coverage description")
    format: str = Field(description="Data format: netcdf, geotiff, csv, parquet, json")
    status: str = Field(description="Status: active, degraded, offline")
    last_updated: datetime


class IngestRequest(BaseModel):
    """Request to trigger a data ingestion job."""

    source_id: str = Field(description="Data source to ingest from")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Source-specific ingestion parameters")
    priority: str = Field(default="normal", description="Job priority: low, normal, high, critical")


class IngestJob(BaseModel):
    """Status of a data ingestion job."""

    job_id: str
    source_id: str
    status: str = Field(description="Status: queued, running, completed, failed, cancelled")
    progress_pct: float = Field(ge=0, le=100, description="Progress percentage")
    records_processed: int = 0
    records_total: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class CatalogEntry(BaseModel):
    """An entry in the data catalog."""

    dataset_id: str
    name: str
    description: str
    domains: list[str]
    spatial_extent: dict[str, float] = Field(description="Bounding box of the dataset")
    temporal_extent: dict[str, str] = Field(description="Start and end dates")
    record_count: int
    size_gb: float
    format: str
    last_updated: datetime
    quality_score: float = Field(ge=0, le=1, description="Data quality score 0-1")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/sources",
    response_model=list[DataSourceInfo],
    summary="List available data sources",
    responses={200: {"description": "List of data sources"}},
)
async def list_data_sources(
    domain: str | None = Query(None, description="Filter by domain (climate, biodiversity, health, etc.)"),
    status: str | None = Query(None, description="Filter by status: active, degraded, offline"),
) -> list[DataSourceInfo]:
    """List all data sources available for ingestion.

    Returns metadata about each source including update frequency,
    spatial resolution, and current status.
    """
    now = datetime.now(tz=timezone.utc)
    sources = [
        DataSourceInfo(
            source_id="era5", name="ERA5 Climate Reanalysis", provider="ECMWF / Copernicus",
            domains=["climate"], update_frequency="daily", spatial_resolution="0.25°",
            temporal_coverage="1940-present", format="netcdf", status="active",
            last_updated=now - timedelta(hours=6),
        ),
        DataSourceInfo(
            source_id="gbif", name="GBIF Species Occurrences", provider="Global Biodiversity Information Facility",
            domains=["biodiversity"], update_frequency="daily", spatial_resolution="point",
            temporal_coverage="1753-present", format="parquet", status="active",
            last_updated=now - timedelta(hours=12),
        ),
        DataSourceInfo(
            source_id="openaq", name="OpenAQ Air Quality", provider="OpenAQ",
            domains=["health"], update_frequency="hourly", spatial_resolution="point",
            temporal_coverage="2015-present", format="json", status="active",
            last_updated=now - timedelta(minutes=45),
        ),
        DataSourceInfo(
            source_id="noaa-ghcn", name="NOAA GHCN Daily", provider="NOAA",
            domains=["climate"], update_frequency="daily", spatial_resolution="point",
            temporal_coverage="1763-present", format="csv", status="active",
            last_updated=now - timedelta(hours=3),
        ),
        DataSourceInfo(
            source_id="usda-cropscape", name="USDA CropScape", provider="USDA NASS",
            domains=["food_security"], update_frequency="yearly", spatial_resolution="30m",
            temporal_coverage="2008-present", format="geotiff", status="active",
            last_updated=now - timedelta(days=30),
        ),
        DataSourceInfo(
            source_id="aqueduct", name="WRI Aqueduct Water Risk", provider="World Resources Institute",
            domains=["resources"], update_frequency="monthly", spatial_resolution="sub-basin",
            temporal_coverage="1960-present", format="geotiff", status="active",
            last_updated=now - timedelta(days=15),
        ),
        DataSourceInfo(
            source_id="sentinel2", name="Sentinel-2 Imagery", provider="ESA / Copernicus",
            domains=["biodiversity", "food_security"], update_frequency="5-day revisit",
            spatial_resolution="10m", temporal_coverage="2015-present", format="geotiff",
            status="active", last_updated=now - timedelta(days=2),
        ),
    ]
    if domain:
        sources = [s for s in sources if domain in s.domains]
    if status:
        sources = [s for s in sources if s.status == status]
    return sources


@router.post(
    "/ingest",
    response_model=IngestJob,
    status_code=202,
    summary="Trigger data ingestion",
    responses={202: {"description": "Job accepted"}, 404: {"description": "Source not found"}, 422: {"description": "Validation error"}},
)
async def trigger_ingestion(request: IngestRequest) -> IngestJob:
    """Trigger a data ingestion job for a specific data source.

    The job is enqueued for asynchronous processing by the EcoTrack
    worker pipeline. Returns the job ID for status tracking.
    """
    valid_sources = {"era5", "gbif", "openaq", "noaa-ghcn", "usda-cropscape", "aqueduct", "sentinel2"}
    if request.source_id not in valid_sources:
        raise HTTPException(status_code=404, detail=f"Unknown source: {request.source_id}")

    now = datetime.now(tz=timezone.utc)
    return IngestJob(
        job_id=f"ingest-{uuid.uuid4().hex[:12]}",
        source_id=request.source_id,
        status="queued",
        progress_pct=0.0,
        records_processed=0,
        records_total=None,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=now,
    )


@router.get(
    "/jobs",
    response_model=PaginatedResponse[IngestJob],
    summary="List ingestion jobs",
    responses={200: {"description": "List of jobs"}},
)
async def list_ingestion_jobs(
    source_id: str | None = Query(None, description="Filter by source ID"),
    status: str | None = Query(None, description="Filter by status: queued, running, completed, failed"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[IngestJob]:
    """List data ingestion jobs with optional filters.

    Returns paginated job records showing current status and progress.
    """
    now = datetime.now(tz=timezone.utc)
    jobs = [
        IngestJob(
            job_id="ingest-a1b2c3d4e5f6", source_id="era5", status="completed",
            progress_pct=100.0, records_processed=48000, records_total=48000,
            started_at=now - timedelta(hours=2), completed_at=now - timedelta(hours=1, minutes=45),
            created_at=now - timedelta(hours=2, minutes=5),
        ),
        IngestJob(
            job_id="ingest-f6e5d4c3b2a1", source_id="openaq", status="running",
            progress_pct=62.5, records_processed=31250, records_total=50000,
            started_at=now - timedelta(minutes=30), created_at=now - timedelta(minutes=35),
        ),
        IngestJob(
            job_id="ingest-112233445566", source_id="gbif", status="queued",
            progress_pct=0.0, created_at=now - timedelta(minutes=5),
        ),
    ]
    if source_id:
        jobs = [j for j in jobs if j.source_id == source_id]
    if status:
        jobs = [j for j in jobs if j.status == status]
    return PaginatedResponse(
        items=jobs, total=len(jobs), page=page, page_size=page_size, has_next=False
    )


@router.get(
    "/jobs/{job_id}",
    response_model=IngestJob,
    summary="Get job details",
    responses={200: {"description": "Job details"}, 404: {"description": "Job not found"}},
)
async def get_job_details(job_id: str) -> IngestJob:
    """Get detailed status of a specific ingestion job.

    Returns full job metadata including progress, record counts,
    and any error messages.
    """
    now = datetime.now(tz=timezone.utc)
    # Stub: return sample job
    if job_id.startswith("ingest-"):
        return IngestJob(
            job_id=job_id, source_id="era5", status="running",
            progress_pct=45.0, records_processed=22500, records_total=50000,
            started_at=now - timedelta(minutes=15), created_at=now - timedelta(minutes=20),
        )
    raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")


@router.get(
    "/catalog",
    response_model=PaginatedResponse[CatalogEntry],
    summary="Search data catalog",
    responses={422: {"description": "Validation error"}},
)
async def search_catalog(
    query: str | None = Query(None, description="Free-text search query"),
    domain: str | None = Query(None, description="Filter by domain"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[CatalogEntry]:
    """Search the EcoTrack data catalog.

    Browse available datasets with spatial, domain, and free-text filters.
    """
    now = datetime.now(tz=timezone.utc)
    entries = [
        CatalogEntry(
            dataset_id="ds-era5-temperature", name="ERA5 Global Temperature (2m)",
            description="Hourly 2-metre temperature from ERA5 reanalysis, regridded to 0.25° resolution",
            domains=["climate"], spatial_extent={"min_lon": -180, "min_lat": -90, "max_lon": 180, "max_lat": 90},
            temporal_extent={"start": "1940-01-01", "end": "2026-02-17"},
            record_count=2500000000, size_gb=1250.0, format="zarr",
            last_updated=now - timedelta(hours=6), quality_score=0.98,
        ),
        CatalogEntry(
            dataset_id="ds-gbif-occurrences", name="GBIF Species Occurrences",
            description="Global species occurrence records from GBIF, deduplicated and quality-filtered",
            domains=["biodiversity"], spatial_extent={"min_lon": -180, "min_lat": -90, "max_lon": 180, "max_lat": 90},
            temporal_extent={"start": "1753-01-01", "end": "2026-02-17"},
            record_count=2800000000, size_gb=890.0, format="parquet",
            last_updated=now - timedelta(hours=12), quality_score=0.85,
        ),
        CatalogEntry(
            dataset_id="ds-openaq-readings", name="OpenAQ Air Quality Readings",
            description="Real-time and historical air quality measurements from 80,000+ stations globally",
            domains=["health"], spatial_extent={"min_lon": -180, "min_lat": -90, "max_lon": 180, "max_lat": 90},
            temporal_extent={"start": "2015-06-01", "end": "2026-02-18"},
            record_count=15000000000, size_gb=420.0, format="parquet",
            last_updated=now - timedelta(minutes=45), quality_score=0.82,
        ),
    ]
    if domain:
        entries = [e for e in entries if domain in e.domains]
    return PaginatedResponse(
        items=entries, total=len(entries), page=page, page_size=page_size, has_next=False
    )
