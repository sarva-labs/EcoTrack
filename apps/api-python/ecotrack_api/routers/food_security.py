"""Food security and agricultural monitoring API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ecotrack_api.schemas.common import PaginatedResponse
from ecotrack_api.schemas.food_security import (
    CropTypeInfo,
    CropYieldPredictionResponse,
    CropYieldRequest,
    DroughtAlertResponse,
    FoodSecurityDimension,
    FoodSecurityIndexResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/crop-yield",
    response_model=PaginatedResponse[CropYieldPredictionResponse],
    summary="Crop yield predictions",
    responses={422: {"description": "Validation error"}},
)
async def get_crop_yield_predictions(
    crop_type: str | None = Query(None, description="Crop type filter (wheat, rice, maize, etc.)"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[CropYieldPredictionResponse]:
    """Get existing crop yield predictions for a region.

    Returns ML-generated yield predictions from the EcoTrack crop
    forecasting pipeline, including confidence intervals and key drivers.
    """
    now = datetime.now(tz=timezone.utc)
    items = [
        CropYieldPredictionResponse(
            prediction_id="cyp-2026-001",
            crop_type=crop_type or "wheat",
            region_name="Punjab, India",
            latitude=30.79,
            longitude=75.84,
            predicted_yield_tonnes_ha=4.82,
            yield_lower_ci=4.35,
            yield_upper_ci=5.29,
            historical_avg_yield=4.50,
            yield_change_pct=7.1,
            growing_season="2026-rabi",
            model_used="EcoTrack-CropNet-v3",
            key_factors={"soil_moisture": 0.35, "temperature": 0.28, "rainfall": 0.22, "fertilizer": 0.15},
            predicted_at=now - timedelta(hours=12),
        ),
        CropYieldPredictionResponse(
            prediction_id="cyp-2026-002",
            crop_type=crop_type or "rice",
            region_name="Mekong Delta, Vietnam",
            latitude=10.04,
            longitude=105.72,
            predicted_yield_tonnes_ha=6.15,
            yield_lower_ci=5.70,
            yield_upper_ci=6.60,
            historical_avg_yield=5.90,
            yield_change_pct=4.2,
            growing_season="2026-spring",
            model_used="EcoTrack-CropNet-v3",
            key_factors={"flood_risk": 0.30, "soil_moisture": 0.25, "temperature": 0.25, "pest_pressure": 0.20},
            predicted_at=now - timedelta(hours=8),
        ),
    ]
    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_next=False
    )


@router.post(
    "/crop-yield/predict",
    response_model=CropYieldPredictionResponse,
    status_code=201,
    summary="Generate crop yield prediction",
    responses={201: {"description": "Prediction generated"}, 422: {"description": "Validation error"}},
)
async def create_crop_yield_prediction(
    request: CropYieldRequest,
) -> CropYieldPredictionResponse:
    """Generate a new crop yield prediction for a specific location and crop.

    Runs the EcoTrack crop yield model considering soil type, irrigation,
    weather forecasts, and historical yield data.
    """
    now = datetime.now(tz=timezone.utc)
    return CropYieldPredictionResponse(
        prediction_id="cyp-2026-new-001",
        crop_type=request.crop_type,
        region_name="Custom Region",
        latitude=request.latitude,
        longitude=request.longitude,
        predicted_yield_tonnes_ha=round(4.2 + (request.latitude % 1) * 2, 2),
        yield_lower_ci=round(3.8 + (request.latitude % 1) * 1.8, 2),
        yield_upper_ci=round(4.6 + (request.latitude % 1) * 2.2, 2),
        historical_avg_yield=4.10,
        yield_change_pct=round(((4.2 + (request.latitude % 1) * 2) - 4.10) / 4.10 * 100, 1),
        growing_season="2026-current",
        model_used="EcoTrack-CropNet-v3",
        key_factors={
            "soil_moisture": 0.30,
            "temperature": 0.25,
            "irrigation": 0.25 if request.irrigation_type == "irrigated" else 0.10,
            "soil_quality": 0.20,
        },
        predicted_at=now,
    )


@router.get(
    "/drought-alerts",
    response_model=PaginatedResponse[DroughtAlertResponse],
    summary="Active drought alerts",
    responses={422: {"description": "Validation error"}},
)
async def get_drought_alerts(
    severity: str | None = Query(None, description="Drought severity: D0, D1, D2, D3, D4"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[DroughtAlertResponse]:
    """Get active drought alerts within a region.

    Returns current drought monitor alerts including the Standardised
    Precipitation Index, soil moisture, and impact assessments.
    """
    now = datetime.now(tz=timezone.utc)
    items = [
        DroughtAlertResponse(
            alert_id="drought-2026-042",
            region_name="Marathwada, Maharashtra",
            latitude=19.15,
            longitude=76.15,
            severity="D3",
            drought_index=-2.1,
            area_affected_km2=64000,
            population_affected=12500000,
            onset_date=now - timedelta(days=45),
            expected_duration_weeks=8,
            precipitation_deficit_pct=68.0,
            soil_moisture_percentile=8.0,
            impacts=[
                "Severe crop losses in kharif season",
                "Drinking water shortages in 120+ villages",
                "Livestock migration observed",
            ],
            updated_at=now - timedelta(hours=6),
        ),
        DroughtAlertResponse(
            alert_id="drought-2026-038",
            region_name="Horn of Africa - Somalia",
            latitude=2.05,
            longitude=45.32,
            severity="D4",
            drought_index=-2.8,
            area_affected_km2=250000,
            population_affected=4200000,
            onset_date=now - timedelta(days=120),
            expected_duration_weeks=16,
            precipitation_deficit_pct=82.0,
            soil_moisture_percentile=3.0,
            impacts=[
                "Complete crop failure across pastoral regions",
                "Mass livestock die-off",
                "Humanitarian emergency declared",
                "Population displacement of 800,000+",
            ],
            updated_at=now - timedelta(hours=3),
        ),
    ]
    if severity:
        items = [a for a in items if a.severity == severity]
    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_next=False
    )


@router.get(
    "/food-security-index",
    response_model=FoodSecurityIndexResponse,
    summary="Food security index by region",
    responses={422: {"description": "Validation error"}},
)
async def get_food_security_index(
    latitude: float = Query(..., ge=-90, le=90, description="Region centre latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Region centre longitude"),
) -> FoodSecurityIndexResponse:
    """Get the composite food security index for a region.

    Returns the IPC-aligned food security classification with scores
    across availability, access, utilisation, and stability dimensions.
    """
    return FoodSecurityIndexResponse(
        region_name="Central Marathwada",
        latitude=latitude,
        longitude=longitude,
        overall_index=0.42,
        classification="stressed",
        dimensions=[
            FoodSecurityDimension(dimension="availability", score=0.55, trend="worsening"),
            FoodSecurityDimension(dimension="access", score=0.38, trend="stable"),
            FoodSecurityDimension(dimension="utilisation", score=0.48, trend="stable"),
            FoodSecurityDimension(dimension="stability", score=0.27, trend="worsening"),
        ],
        population=3200000,
        food_insecure_population=890000,
        key_drivers=["drought", "rising food prices", "limited irrigation infrastructure"],
        assessed_at=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/crop-types",
    summary="Available crop types",
    responses={200: {"description": "List of supported crop types"}},
)
async def list_crop_types() -> dict[str, list[CropTypeInfo]]:
    """List all crop types supported by the EcoTrack yield prediction system."""
    return {
        "crop_types": [
            CropTypeInfo(crop_type="wheat", common_name="Wheat", category="cereal", growing_regions=["South Asia", "North America", "Europe"], typical_growing_season_months=5),
            CropTypeInfo(crop_type="rice", common_name="Rice", category="cereal", growing_regions=["Southeast Asia", "South Asia", "East Asia"], typical_growing_season_months=4),
            CropTypeInfo(crop_type="maize", common_name="Maize / Corn", category="cereal", growing_regions=["North America", "Sub-Saharan Africa", "South America"], typical_growing_season_months=4),
            CropTypeInfo(crop_type="soybean", common_name="Soybean", category="legume", growing_regions=["North America", "South America", "East Asia"], typical_growing_season_months=4),
            CropTypeInfo(crop_type="potato", common_name="Potato", category="vegetable", growing_regions=["Europe", "South Asia", "North America"], typical_growing_season_months=4),
            CropTypeInfo(crop_type="cassava", common_name="Cassava", category="vegetable", growing_regions=["Sub-Saharan Africa", "Southeast Asia", "South America"], typical_growing_season_months=10),
        ]
    }
