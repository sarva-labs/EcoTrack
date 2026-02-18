"""Biodiversity API request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Species & Observations
# ---------------------------------------------------------------------------

class SpeciesObservationResponse(BaseModel):
    """A single species observation record."""

    id: str = Field(description="Observation identifier")
    species_name: str = Field(description="Scientific name")
    common_name: str | None = Field(default=None, description="Common name")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observed_at: datetime
    observer: str | None = Field(default=None, description="Observer or data source")
    count: int | None = Field(default=None, description="Number of individuals observed")
    conservation_status: str | None = Field(default=None, description="IUCN Red-List status")
    habitat_type: str | None = Field(default=None, description="Habitat classification")
    source: str = Field(description="Data source (e.g. GBIF, iNaturalist)")


class SpeciesSearchParams(BaseModel):
    """Search parameters for species queries."""

    name: str | None = Field(default=None, description="Species name (scientific or common)")
    conservation_status: str | None = Field(default=None, description="IUCN status filter")
    min_lon: float = Field(default=-180, ge=-180, le=180)
    min_lat: float = Field(default=-90, ge=-90, le=90)
    max_lon: float = Field(default=180, ge=-180, le=180)
    max_lat: float = Field(default=90, ge=-90, le=90)
    start_date: datetime | None = Field(default=None, description="Observation date range start")
    end_date: datetime | None = Field(default=None, description="Observation date range end")


class SpeciesSummary(BaseModel):
    """Summary info for a species."""

    species_name: str
    common_name: str | None = None
    conservation_status: str | None = None
    observation_count: int = 0
    last_observed: datetime | None = None
    range_description: str | None = None


# ---------------------------------------------------------------------------
# Ecosystem Health
# ---------------------------------------------------------------------------

class EcosystemHealthResponse(BaseModel):
    """Ecosystem health index for a region."""

    region_name: str = Field(description="Region or ecosystem name")
    latitude: float
    longitude: float
    health_index: float = Field(ge=0, le=1, description="Composite health score 0-1")
    species_richness: int = Field(description="Number of species recorded")
    shannon_diversity: float = Field(description="Shannon diversity index")
    threatened_species_count: int
    invasive_species_count: int
    habitat_integrity: float = Field(ge=0, le=1, description="Habitat integrity score")
    trend: str = Field(description="Trend: improving, stable, declining")
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Hotspots
# ---------------------------------------------------------------------------

class BiodiversityHotspotResponse(BaseModel):
    """Identified biodiversity hotspot."""

    id: str
    name: str = Field(description="Hotspot name")
    latitude: float
    longitude: float
    area_km2: float = Field(description="Area in square kilometres")
    species_count: int
    endemic_species_count: int
    threat_level: str = Field(description="Threat level: low, medium, high, critical")
    primary_threats: list[str] = Field(description="List of primary threats")
    conservation_priority: str = Field(description="Priority: low, medium, high, critical")


# ---------------------------------------------------------------------------
# Conservation Status Summary
# ---------------------------------------------------------------------------

class ConservationStatusSummary(BaseModel):
    """Summary of conservation statuses in a region."""

    region_name: str
    total_species: int
    least_concern: int = 0
    near_threatened: int = 0
    vulnerable: int = 0
    endangered: int = 0
    critically_endangered: int = 0
    extinct_in_wild: int = 0
    data_deficient: int = 0
    not_evaluated: int = 0
    assessed_at: datetime
