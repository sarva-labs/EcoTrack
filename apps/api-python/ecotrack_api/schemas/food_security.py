"""Food security API request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Crop Yield
# ---------------------------------------------------------------------------

class CropYieldPredictionResponse(BaseModel):
    """Crop yield prediction for a specific crop and region."""

    prediction_id: str = Field(description="Unique prediction identifier")
    crop_type: str = Field(description="Crop type (e.g. wheat, rice, maize)")
    region_name: str
    latitude: float
    longitude: float
    predicted_yield_tonnes_ha: float = Field(description="Predicted yield in tonnes per hectare")
    yield_lower_ci: float = Field(description="Lower 95% confidence bound")
    yield_upper_ci: float = Field(description="Upper 95% confidence bound")
    historical_avg_yield: float = Field(description="Historical average for comparison")
    yield_change_pct: float = Field(description="Percentage change from historical average")
    growing_season: str = Field(description="Growing season (e.g. 2026-kharif, 2026-rabi)")
    model_used: str = Field(description="ML model used for prediction")
    key_factors: dict[str, float] = Field(
        default_factory=dict, description="Key contributing factors and weights"
    )
    predicted_at: datetime


class CropYieldRequest(BaseModel):
    """Request body for crop yield prediction."""

    crop_type: str = Field(description="Crop type to predict")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    area_hectares: float = Field(gt=0, description="Area in hectares")
    planting_date: datetime | None = Field(default=None, description="Planting date")
    irrigation_type: str = Field(default="rainfed", description="Irrigation: rainfed, irrigated, mixed")
    soil_type: str | None = Field(default=None, description="Soil classification")


# ---------------------------------------------------------------------------
# Drought Alerts
# ---------------------------------------------------------------------------

class DroughtAlertResponse(BaseModel):
    """Active drought alert."""

    alert_id: str
    region_name: str
    latitude: float
    longitude: float
    severity: str = Field(description="Drought severity: D0 (abnormally dry) - D4 (exceptional)")
    drought_index: float = Field(description="Standardised Precipitation Index (SPI)")
    area_affected_km2: float
    population_affected: int | None = None
    onset_date: datetime
    expected_duration_weeks: int | None = None
    precipitation_deficit_pct: float = Field(description="Precipitation deficit as percentage")
    soil_moisture_percentile: float = Field(ge=0, le=100)
    impacts: list[str] = Field(description="Observed and expected impacts")
    updated_at: datetime


# ---------------------------------------------------------------------------
# Food Security Index
# ---------------------------------------------------------------------------

class FoodSecurityDimension(BaseModel):
    """Score for a single food security dimension."""

    dimension: str = Field(description="Dimension: availability, access, utilisation, stability")
    score: float = Field(ge=0, le=1)
    trend: str = Field(description="Trend: improving, stable, worsening")


class FoodSecurityIndexResponse(BaseModel):
    """Composite food security index for a region."""

    region_name: str
    latitude: float
    longitude: float
    overall_index: float = Field(ge=0, le=1, description="Composite food security index 0-1")
    classification: str = Field(
        description="IPC Phase: minimal, stressed, crisis, emergency, famine"
    )
    dimensions: list[FoodSecurityDimension]
    population: int | None = Field(default=None, description="Estimated population in region")
    food_insecure_population: int | None = None
    key_drivers: list[str] = Field(description="Primary food insecurity drivers")
    assessed_at: datetime


# ---------------------------------------------------------------------------
# Crop Types
# ---------------------------------------------------------------------------

class CropTypeInfo(BaseModel):
    """Information about an available crop type."""

    crop_type: str
    common_name: str
    category: str = Field(description="Category: cereal, legume, fruit, vegetable, oilseed, other")
    growing_regions: list[str]
    typical_growing_season_months: int
    data_available: bool = True
