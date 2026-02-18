"""Resource equity domain models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from .base import Domain, EcoTrackModel, Severity
from .geospatial import BoundingBox


class ResourceType(str, Enum):
    """Natural resource types."""

    WATER = "water"
    ENERGY = "energy"
    LAND = "land"
    MINERALS = "minerals"
    FOREST = "forest"


class WaterStressIndex(EcoTrackModel):
    """Water stress assessment."""

    domain: Domain = Domain.RESOURCE_EQUITY
    bbox: BoundingBox
    timestamp: datetime
    demand_million_m3: float
    supply_million_m3: float
    stress_ratio: float = Field(ge=0)
    severity: Severity
    groundwater_depletion_rate: float | None = None
    population_affected: int | None = None


class EnvironmentalJusticeScore(EcoTrackModel):
    """Environmental justice assessment for a region."""

    domain: Domain = Domain.RESOURCE_EQUITY
    bbox: BoundingBox
    timestamp: datetime
    pollution_burden_score: float = Field(ge=0, le=1)
    socioeconomic_vulnerability: float = Field(ge=0, le=1)
    health_disparity_score: float = Field(ge=0, le=1)
    resource_access_score: float = Field(ge=0, le=1)
    overall_ej_score: float = Field(ge=0, le=1)
    demographic_indicators: dict[str, float] = Field(default_factory=dict)


class ResourceAllocation(EcoTrackModel):
    """Optimized resource allocation recommendation."""

    domain: Domain = Domain.RESOURCE_EQUITY
    resource_type: ResourceType
    bbox: BoundingBox
    timestamp: datetime
    current_allocation: float
    recommended_allocation: float
    efficiency_gain_pct: float
    equity_impact_score: float = Field(ge=0, le=1)
    rationale: str = ""


__all__ = [
    "ResourceType",
    "WaterStressIndex",
    "EnvironmentalJusticeScore",
    "ResourceAllocation",
]
