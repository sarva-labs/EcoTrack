"""Biodiversity monitoring and assessment API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ecotrack_api.schemas.biodiversity import (
    BiodiversityHotspotResponse,
    ConservationStatusSummary,
    EcosystemHealthResponse,
    SpeciesObservationResponse,
    SpeciesSummary,
)
from ecotrack_api.schemas.common import PaginatedResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/species",
    response_model=PaginatedResponse[SpeciesSummary],
    summary="Search species",
    responses={422: {"description": "Validation error"}},
)
async def search_species(
    name: str | None = Query(None, description="Species name (scientific or common)"),
    conservation_status: str | None = Query(None, description="IUCN Red-List status filter (e.g. VU, EN, CR)"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[SpeciesSummary]:
    """Search species with spatial and conservation status filters.

    Returns paginated species summaries from the EcoTrack biodiversity database.
    """
    now = datetime.now(tz=timezone.utc)
    items = [
        SpeciesSummary(
            species_name="Panthera tigris",
            common_name="Bengal Tiger",
            conservation_status="EN",
            observation_count=1247,
            last_observed=now - timedelta(days=3),
            range_description="South and Southeast Asia",
        ),
        SpeciesSummary(
            species_name="Ailuropoda melanoleuca",
            common_name="Giant Panda",
            conservation_status="VU",
            observation_count=832,
            last_observed=now - timedelta(days=7),
            range_description="Central China mountain forests",
        ),
        SpeciesSummary(
            species_name="Gorilla beringei",
            common_name="Mountain Gorilla",
            conservation_status="EN",
            observation_count=612,
            last_observed=now - timedelta(days=1),
            range_description="Virunga Mountains, Bwindi Impenetrable Forest",
        ),
    ]
    if name:
        items = [s for s in items if name.lower() in s.species_name.lower() or (s.common_name and name.lower() in s.common_name.lower())]
    if conservation_status:
        items = [s for s in items if s.conservation_status == conservation_status]
    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_next=False
    )


@router.get(
    "/species/{species_name}/observations",
    response_model=PaginatedResponse[SpeciesObservationResponse],
    summary="Get observations for a species",
    responses={404: {"description": "Species not found"}},
)
async def get_species_observations(
    species_name: str,
    start_date: datetime | None = Query(None, description="Observation date range start"),
    end_date: datetime | None = Query(None, description="Observation date range end"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[SpeciesObservationResponse]:
    """Get observation records for a specific species.

    Returns paginated sighting / detection records sourced from GBIF,
    iNaturalist, and partner research networks.
    """
    now = datetime.now(tz=timezone.utc)
    items = [
        SpeciesObservationResponse(
            id=f"obs-bio-{i:04d}",
            species_name=species_name,
            common_name="Bengal Tiger" if "tigris" in species_name else species_name,
            latitude=round(27.5 + i * 0.2, 4),
            longitude=round(88.3 + i * 0.15, 4),
            observed_at=now - timedelta(days=i * 5),
            observer="EcoTrack Camera Trap Network",
            count=1 + i,
            conservation_status="EN",
            habitat_type="tropical_moist_forest",
            source="GBIF",
        )
        for i in range(min(page_size, 4))
    ]
    return PaginatedResponse(
        items=items, total=23, page=page, page_size=page_size, has_next=page == 1
    )


@router.get(
    "/observations",
    response_model=PaginatedResponse[SpeciesObservationResponse],
    summary="Query species observations by region",
    responses={422: {"description": "Validation error"}},
)
async def query_observations(
    species_name: str | None = Query(None, description="Filter by species name"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    start_date: datetime | None = Query(None, description="Observation start date"),
    end_date: datetime | None = Query(None, description="Observation end date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[SpeciesObservationResponse]:
    """Query all species observations within a bounding box and time range.

    Returns paginated observation records across all species for the
    specified spatial and temporal extent.
    """
    now = datetime.now(tz=timezone.utc)
    items = [
        SpeciesObservationResponse(
            id="obs-bio-0100",
            species_name="Panthera tigris",
            common_name="Bengal Tiger",
            latitude=27.49,
            longitude=88.35,
            observed_at=now - timedelta(days=2),
            observer="Camera Trap Station CT-042",
            count=1,
            conservation_status="EN",
            habitat_type="tropical_moist_forest",
            source="GBIF",
        ),
        SpeciesObservationResponse(
            id="obs-bio-0101",
            species_name="Rhinoceros unicornis",
            common_name="Indian Rhinoceros",
            latitude=26.58,
            longitude=93.17,
            observed_at=now - timedelta(days=1),
            observer="Kaziranga Monitoring Team",
            count=3,
            conservation_status="VU",
            habitat_type="grassland",
            source="iNaturalist",
        ),
    ]
    return PaginatedResponse(
        items=items, total=2, page=page, page_size=page_size, has_next=False
    )


@router.get(
    "/ecosystem-health",
    response_model=EcosystemHealthResponse,
    summary="Get ecosystem health index",
    responses={422: {"description": "Validation error"}},
)
async def get_ecosystem_health(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude of the region centre"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude of the region centre"),
    radius_km: float = Query(50, gt=0, le=500, description="Analysis radius in kilometres"),
) -> EcosystemHealthResponse:
    """Get the composite ecosystem health index for a region.

    Combines species richness, diversity indices, threat assessments,
    and habitat integrity into a single normalised score.
    """
    return EcosystemHealthResponse(
        region_name="Western Ghats Biodiversity Hotspot",
        latitude=latitude,
        longitude=longitude,
        health_index=0.72,
        species_richness=1842,
        shannon_diversity=4.31,
        threatened_species_count=187,
        invasive_species_count=23,
        habitat_integrity=0.68,
        trend="declining",
        assessed_at=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/hotspots",
    response_model=PaginatedResponse[BiodiversityHotspotResponse],
    summary="Identify biodiversity hotspots",
    responses={422: {"description": "Validation error"}},
)
async def get_biodiversity_hotspots(
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    threat_level: str | None = Query(None, description="Filter by threat level: low, medium, high, critical"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[BiodiversityHotspotResponse]:
    """Identify and list biodiversity hotspots within a region.

    Hotspots are areas with exceptionally high species richness and
    endemism that face significant habitat loss threats.
    """
    items = [
        BiodiversityHotspotResponse(
            id="hs-001",
            name="Western Ghats & Sri Lanka",
            latitude=10.5,
            longitude=76.5,
            area_km2=189611,
            species_count=7402,
            endemic_species_count=3049,
            threat_level="high",
            primary_threats=["deforestation", "urbanization", "agriculture expansion"],
            conservation_priority="critical",
        ),
        BiodiversityHotspotResponse(
            id="hs-002",
            name="Sundaland",
            latitude=0.5,
            longitude=110.0,
            area_km2=1500000,
            species_count=25000,
            endemic_species_count=15000,
            threat_level="critical",
            primary_threats=["palm oil plantations", "logging", "mining"],
            conservation_priority="critical",
        ),
    ]
    if threat_level:
        items = [h for h in items if h.threat_level == threat_level]
    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_next=False
    )


@router.get(
    "/conservation-status",
    response_model=ConservationStatusSummary,
    summary="Get conservation status summary",
    responses={422: {"description": "Validation error"}},
)
async def get_conservation_status(
    latitude: float = Query(..., ge=-90, le=90, description="Region centre latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Region centre longitude"),
    radius_km: float = Query(100, gt=0, le=500, description="Analysis radius in kilometres"),
) -> ConservationStatusSummary:
    """Get a summary of IUCN conservation statuses for species in a region.

    Breaks down the number of species by conservation category for the
    specified area.
    """
    return ConservationStatusSummary(
        region_name="Central Western Ghats",
        total_species=1842,
        least_concern=1200,
        near_threatened=210,
        vulnerable=187,
        endangered=132,
        critically_endangered=45,
        extinct_in_wild=2,
        data_deficient=56,
        not_evaluated=10,
        assessed_at=datetime.now(tz=timezone.utc),
    )
