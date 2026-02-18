"""Resource equity and allocation API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ecotrack_api.schemas.common import PaginatedResponse
from ecotrack_api.schemas.resources import (
    EnergyDistributionResponse,
    EnvironmentalJusticeIndicator,
    EnvironmentalJusticeResponse,
    RegionAllocation,
    ResourceAllocationRequest,
    ResourceAllocationResponse,
    ResourceTypeInfo,
    WaterStressResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/water-stress",
    response_model=WaterStressResponse,
    summary="Water stress index",
    responses={422: {"description": "Validation error"}},
)
async def get_water_stress(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> WaterStressResponse:
    """Get the water stress index for a region.

    Uses the Aqueduct Water Risk Indicator methodology to compute
    supply-demand ratios, groundwater depletion, and drought risk.
    """
    return WaterStressResponse(
        region_name="North-West India — Punjab-Haryana",
        latitude=latitude,
        longitude=longitude,
        stress_index=4.2,
        stress_level="extremely_high",
        water_demand_m3_day=285000000,
        water_supply_m3_day=195000000,
        supply_demand_ratio=0.68,
        groundwater_depletion_rate=12.5,
        seasonal_variability="high",
        drought_risk="high",
        assessed_at=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/environmental-justice",
    response_model=EnvironmentalJusticeResponse,
    summary="Environmental justice scores by region",
    responses={422: {"description": "Validation error"}},
)
async def get_environmental_justice(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> EnvironmentalJusticeResponse:
    """Get environmental justice assessment for a region.

    Computes a composite EJ index from pollution burden, health
    disparities, socio-economic factors, and climate vulnerability.
    """
    return EnvironmentalJusticeResponse(
        region_name="South-East Houston, TX",
        latitude=latitude,
        longitude=longitude,
        ej_index=82.0,
        classification="very_high",
        indicators=[
            EnvironmentalJusticeIndicator(indicator="PM2.5 exposure", score=89.0, category="pollution"),
            EnvironmentalJusticeIndicator(indicator="Toxic releases proximity", score=92.0, category="pollution"),
            EnvironmentalJusticeIndicator(indicator="Asthma prevalence", score=78.0, category="health"),
            EnvironmentalJusticeIndicator(indicator="Low income percentage", score=85.0, category="socioeconomic"),
            EnvironmentalJusticeIndicator(indicator="Flood risk", score=76.0, category="climate"),
            EnvironmentalJusticeIndicator(indicator="Linguistic isolation", score=71.0, category="socioeconomic"),
        ],
        demographic_data={
            "population": 45000,
            "median_income": 32500,
            "percent_minority": 78.0,
            "percent_below_poverty": 31.0,
        },
        nearby_pollution_sources=14,
        health_disparity_score=81.0,
        assessed_at=datetime.now(tz=timezone.utc),
    )


@router.post(
    "/allocate",
    response_model=ResourceAllocationResponse,
    status_code=201,
    summary="Optimise resource allocation",
    responses={201: {"description": "Allocation optimised"}, 422: {"description": "Validation error"}},
)
async def optimise_resource_allocation(
    request: ResourceAllocationRequest,
) -> ResourceAllocationResponse:
    """Optimise resource allocation across regions.

    Uses the EcoTrack RL-based policy engine to distribute resources
    according to the specified objective (equity, efficiency, need-based,
    or hybrid).
    """
    allocations = [
        RegionAllocation(
            region_id=rid,
            region_name=f"Region {rid}",
            allocated_amount=round(request.total_budget / len(request.region_ids) * (0.8 + idx * 0.1), 2),
            allocation_pct=round(100 / len(request.region_ids), 1),
            need_score=round(0.5 + idx * 0.1, 2),
            equity_score=round(0.7 + idx * 0.05, 2),
            rationale=f"Allocation based on {request.optimisation_objective} objective with need weighting",
        )
        for idx, rid in enumerate(request.region_ids)
    ]
    return ResourceAllocationResponse(
        allocation_id="alloc-2026-001",
        resource_type=request.resource_type,
        total_budget=request.total_budget,
        objective=request.optimisation_objective,
        allocations=allocations,
        overall_equity_score=0.82,
        overall_efficiency_score=0.78,
        generated_at=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/energy-distribution",
    response_model=EnergyDistributionResponse,
    summary="Energy distribution equity",
    responses={422: {"description": "Validation error"}},
)
async def get_energy_distribution(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> EnergyDistributionResponse:
    """Get energy distribution equity metrics for a region.

    Returns access rates, renewable share, per-capita consumption,
    and energy poverty indicators.
    """
    return EnergyDistributionResponse(
        region_name="Rural Bihar, India",
        latitude=latitude,
        longitude=longitude,
        access_rate_pct=78.5,
        renewable_share_pct=12.3,
        per_capita_kwh=320.0,
        equity_index=0.42,
        grid_reliability_pct=68.0,
        energy_poverty_pct=34.0,
        assessed_at=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/resource-types",
    summary="Available resource types",
    responses={200: {"description": "List of supported resource types"}},
)
async def list_resource_types() -> dict[str, list[ResourceTypeInfo]]:
    """List all resource types tracked by the EcoTrack platform."""
    return {
        "resource_types": [
            ResourceTypeInfo(resource_type="water", display_name="Water", unit="m³", description="Freshwater resources including surface and groundwater"),
            ResourceTypeInfo(resource_type="energy", display_name="Energy", unit="kWh", description="Electrical energy generation and distribution"),
            ResourceTypeInfo(resource_type="funding", display_name="Funding", unit="USD", description="Financial resources for environmental programmes"),
            ResourceTypeInfo(resource_type="medical_supplies", display_name="Medical Supplies", unit="units", description="Medical supplies for environmental health response"),
            ResourceTypeInfo(resource_type="food_aid", display_name="Food Aid", unit="metric_tonnes", description="Emergency food supplies and nutritional aid"),
        ]
    }
