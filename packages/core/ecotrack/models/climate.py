"""Climate domain models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from .base import Domain, EcoTrackModel, Severity
from .geospatial import BoundingBox, GeoPoint


class ClimateVariable(str, Enum):
    """Standard climate variables."""

    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    HUMIDITY = "humidity"
    WIND_SPEED = "wind_speed"
    PRESSURE = "pressure"
    CO2 = "co2"
    SEA_LEVEL = "sea_level"
    NDVI = "ndvi"
    SEA_SURFACE_TEMP = "sea_surface_temp"
    SOIL_MOISTURE = "soil_moisture"


class ClimateObservation(EcoTrackModel):
    """A single climate measurement."""

    domain: Domain = Domain.CLIMATE
    variable: ClimateVariable
    value: float
    unit: str
    location: GeoPoint
    timestamp: datetime
    source: str
    quality_flag: int = 0
    uncertainty: float | None = None


class ClimateAnomaly(EcoTrackModel):
    """Detected climate anomaly."""

    domain: Domain = Domain.CLIMATE
    variable: ClimateVariable
    severity: Severity
    bbox: BoundingBox
    detected_at: datetime
    baseline_mean: float
    observed_value: float
    deviation_sigma: float
    description: str


class ClimateForecast(EcoTrackModel):
    """Climate forecast for a region."""

    domain: Domain = Domain.CLIMATE
    variable: ClimateVariable
    bbox: BoundingBox
    forecast_time: datetime
    lead_hours: int
    predicted_value: float
    prediction_interval_lower: float
    prediction_interval_upper: float
    model_name: str
    confidence: float = Field(ge=0, le=1)


__all__ = [
    "ClimateVariable",
    "ClimateObservation",
    "ClimateAnomaly",
    "ClimateForecast",
]
