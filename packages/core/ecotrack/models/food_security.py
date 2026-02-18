"""Food security domain models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from .base import Domain, EcoTrackModel, Severity
from .geospatial import BoundingBox, GeoPoint


class CropType(str, Enum):
    """Major crop types."""

    WHEAT = "wheat"
    RICE = "rice"
    MAIZE = "maize"
    SOYBEAN = "soybean"
    COTTON = "cotton"
    SUGARCANE = "sugarcane"
    OTHER = "other"


class DroughtSeverity(str, Enum):
    """US Drought Monitor severity levels."""

    ABNORMALLY_DRY = "D0"
    MODERATE = "D1"
    SEVERE = "D2"
    EXTREME = "D3"
    EXCEPTIONAL = "D4"


class CropYieldPrediction(EcoTrackModel):
    """Crop yield prediction for a region."""

    domain: Domain = Domain.FOOD_SECURITY
    crop_type: CropType
    bbox: BoundingBox
    prediction_date: datetime
    harvest_date: datetime
    predicted_yield_tons_per_ha: float
    yield_lower_bound: float
    yield_upper_bound: float
    historical_avg_yield: float
    model_name: str
    confidence: float = Field(ge=0, le=1)


class DroughtAlert(EcoTrackModel):
    """Drought early warning."""

    domain: Domain = Domain.FOOD_SECURITY
    severity: DroughtSeverity
    bbox: BoundingBox
    onset_date: datetime
    expected_duration_days: int
    affected_area_km2: float
    soil_moisture_percentile: float
    precipitation_deficit_mm: float
    affected_crops: list[CropType] = Field(default_factory=list)


class FoodSecurityIndex(EcoTrackModel):
    """Composite food security index."""

    domain: Domain = Domain.FOOD_SECURITY
    bbox: BoundingBox
    timestamp: datetime
    availability_score: float = Field(ge=0, le=1)
    access_score: float = Field(ge=0, le=1)
    utilization_score: float = Field(ge=0, le=1)
    stability_score: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    population_affected: int | None = None


__all__ = [
    "CropType",
    "DroughtSeverity",
    "CropYieldPrediction",
    "DroughtAlert",
    "FoodSecurityIndex",
]
