"""Public health domain models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from .base import Domain, EcoTrackModel, Severity
from .geospatial import BoundingBox, GeoPoint


class HealthMetric(str, Enum):
    """Public health measurement types."""

    AIR_QUALITY_INDEX = "aqi"
    PM25 = "pm25"
    PM10 = "pm10"
    OZONE = "ozone"
    WATER_QUALITY_INDEX = "wqi"
    HEAT_INDEX = "heat_index"
    UV_INDEX = "uv_index"
    DISEASE_VECTOR_RISK = "disease_vector_risk"


class AirQualityReading(EcoTrackModel):
    """Air quality measurement."""

    domain: Domain = Domain.HEALTH
    location: GeoPoint
    timestamp: datetime
    aqi: int = Field(ge=0, le=500)
    pm25: float | None = None
    pm10: float | None = None
    ozone: float | None = None
    no2: float | None = None
    so2: float | None = None
    co: float | None = None
    source: str = ""


class DiseaseVectorRisk(EcoTrackModel):
    """Disease vector risk assessment."""

    domain: Domain = Domain.HEALTH
    disease: str
    vector: str
    bbox: BoundingBox
    timestamp: datetime
    risk_score: float = Field(ge=0, le=1)
    severity: Severity
    contributing_factors: list[str] = Field(default_factory=list)
    population_at_risk: int | None = None


class HeatVulnerabilityIndex(EcoTrackModel):
    """Heat vulnerability assessment for a region."""

    domain: Domain = Domain.HEALTH
    bbox: BoundingBox
    timestamp: datetime
    temperature_c: float
    heat_index_c: float
    vulnerability_score: float = Field(ge=0, le=1)
    urban_heat_island_effect: float | None = None
    at_risk_population: int | None = None


__all__ = [
    "HealthMetric",
    "AirQualityReading",
    "DiseaseVectorRisk",
    "HeatVulnerabilityIndex",
]
