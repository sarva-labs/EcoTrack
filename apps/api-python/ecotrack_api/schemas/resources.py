"""Resource equity API request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Water Stress
# ---------------------------------------------------------------------------

class WaterStressResponse(BaseModel):
    """Water stress index for a region."""

    region_name: str
    latitude: float
    longitude: float
    stress_index: float = Field(ge=0, le=5, description="Water stress index 0-5 (Aqueduct scale)")
    stress_level: str = Field(description="Level: low, low-medium, medium-high, high, extremely_high")
    water_demand_m3_day: float = Field(description="Estimated daily water demand in m³")
    water_supply_m3_day: float = Field(description="Estimated daily water supply in m³")
    supply_demand_ratio: float
    groundwater_depletion_rate: float | None = Field(
        default=None, description="Groundwater depletion rate (mm/year)"
    )
    seasonal_variability: str = Field(description="Variability: low, moderate, high")
    drought_risk: str = Field(description="Drought risk level")
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Environmental Justice
# ---------------------------------------------------------------------------

class EnvironmentalJusticeIndicator(BaseModel):
    """Individual EJ indicator score."""

    indicator: str = Field(description="Indicator name")
    score: float = Field(ge=0, le=100, description="Percentile score 0-100")
    category: str = Field(description="Category: pollution, health, socioeconomic, climate")


class EnvironmentalJusticeResponse(BaseModel):
    """Environmental justice assessment for a region."""

    region_name: str
    latitude: float
    longitude: float
    ej_index: float = Field(ge=0, le=100, description="Composite EJ index percentile")
    classification: str = Field(description="Classification: low_concern, moderate, high, very_high, critical")
    indicators: list[EnvironmentalJusticeIndicator]
    demographic_data: dict[str, Any] = Field(
        default_factory=dict, description="Relevant demographic information"
    )
    nearby_pollution_sources: int = Field(description="Count of nearby pollution sources")
    health_disparity_score: float = Field(ge=0, le=100)
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Resource Allocation
# ---------------------------------------------------------------------------

class ResourceAllocationRequest(BaseModel):
    """Request body for resource allocation optimisation."""

    resource_type: str = Field(description="Resource: water, energy, funding, medical_supplies")
    region_ids: list[str] = Field(description="List of region identifiers to optimise across")
    total_budget: float = Field(gt=0, description="Total resource budget to allocate")
    optimisation_objective: str = Field(
        default="equity",
        description="Objective: equity, efficiency, need_based, hybrid",
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict, description="Additional allocation constraints"
    )


class RegionAllocation(BaseModel):
    """Allocation result for a single region."""

    region_id: str
    region_name: str
    allocated_amount: float
    allocation_pct: float
    need_score: float = Field(ge=0, le=1)
    equity_score: float = Field(ge=0, le=1)
    rationale: str


class ResourceAllocationResponse(BaseModel):
    """Optimised resource allocation across regions."""

    allocation_id: str
    resource_type: str
    total_budget: float
    objective: str
    allocations: list[RegionAllocation]
    overall_equity_score: float = Field(ge=0, le=1)
    overall_efficiency_score: float = Field(ge=0, le=1)
    generated_at: datetime


# ---------------------------------------------------------------------------
# Energy Distribution
# ---------------------------------------------------------------------------

class EnergyDistributionResponse(BaseModel):
    """Energy distribution equity for a region."""

    region_name: str
    latitude: float
    longitude: float
    access_rate_pct: float = Field(ge=0, le=100, description="Population with energy access (%)")
    renewable_share_pct: float = Field(ge=0, le=100, description="Renewable energy share (%)")
    per_capita_kwh: float = Field(description="Per-capita energy consumption (kWh/year)")
    equity_index: float = Field(ge=0, le=1, description="Energy equity index 0-1")
    grid_reliability_pct: float = Field(ge=0, le=100, description="Grid reliability (%)")
    energy_poverty_pct: float = Field(ge=0, le=100, description="Population in energy poverty (%)")
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Resource Types
# ---------------------------------------------------------------------------

class ResourceTypeInfo(BaseModel):
    """Information about an available resource type."""

    resource_type: str
    display_name: str
    unit: str
    description: str
    data_available: bool = True
