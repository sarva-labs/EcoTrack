"""Public health API request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Air Quality
# ---------------------------------------------------------------------------

class PollutantReading(BaseModel):
    """Individual pollutant measurement."""

    pollutant: str = Field(description="Pollutant name (PM2.5, PM10, O3, NO2, SO2, CO)")
    value: float = Field(description="Concentration value")
    unit: str = Field(default="µg/m³", description="Measurement unit")
    aqi_contribution: int = Field(description="AQI contribution from this pollutant")


class AirQualityResponse(BaseModel):
    """Current air quality reading for a location."""

    station_id: str | None = Field(default=None, description="Monitoring station ID")
    latitude: float
    longitude: float
    aqi: int = Field(ge=0, description="Overall Air Quality Index")
    category: str = Field(description="AQI category: Good, Moderate, Unhealthy for Sensitive Groups, Unhealthy, Very Unhealthy, Hazardous")
    dominant_pollutant: str = Field(description="Primary contributing pollutant")
    pollutants: list[PollutantReading]
    measured_at: datetime
    source: str = Field(description="Data source (e.g. OpenAQ, EPA)")


class AirQualityQueryParams(BaseModel):
    """Query parameters for air quality data."""

    min_lon: float = Field(default=-180, ge=-180, le=180)
    min_lat: float = Field(default=-90, ge=-90, le=90)
    max_lon: float = Field(default=180, ge=-180, le=180)
    max_lat: float = Field(default=90, ge=-90, le=90)
    pollutant: str | None = Field(default=None, description="Filter by specific pollutant")
    min_aqi: int | None = Field(default=None, ge=0, description="Minimum AQI threshold")


class AirQualityForecastPoint(BaseModel):
    """A single air quality forecast timestep."""

    timestamp: datetime
    aqi: int
    category: str
    dominant_pollutant: str


class AirQualityForecastResponse(BaseModel):
    """Air quality forecast for a location."""

    latitude: float
    longitude: float
    generated_at: datetime
    forecast_hours: int
    forecast_points: list[AirQualityForecastPoint]


# ---------------------------------------------------------------------------
# Disease Vector Risk
# ---------------------------------------------------------------------------

class DiseaseVectorDetail(BaseModel):
    """Risk detail for a specific disease vector."""

    disease: str = Field(description="Disease name")
    vector: str = Field(description="Vector organism (e.g. Aedes aegypti)")
    risk_score: float = Field(ge=0, le=1, description="Risk score 0-1")
    risk_level: str = Field(description="Risk level: low, moderate, high, very_high")
    contributing_factors: list[str]


class DiseaseVectorRiskResponse(BaseModel):
    """Disease vector risk assessment for a location."""

    latitude: float
    longitude: float
    overall_risk: float = Field(ge=0, le=1, description="Overall vector-borne disease risk")
    risk_level: str
    diseases: list[DiseaseVectorDetail]
    environmental_factors: dict[str, float] = Field(
        description="Contributing environmental factors and their weights"
    )
    assessed_at: datetime
    valid_until: datetime


# ---------------------------------------------------------------------------
# Heat Vulnerability
# ---------------------------------------------------------------------------

class HeatVulnerabilityResponse(BaseModel):
    """Heat vulnerability index for a location or region."""

    latitude: float
    longitude: float
    region_name: str | None = None
    vulnerability_index: float = Field(ge=0, le=1, description="Heat vulnerability index 0-1")
    vulnerability_level: str = Field(description="Level: low, moderate, high, extreme")
    current_temperature_c: float | None = Field(default=None, description="Current temperature °C")
    heat_index_c: float | None = Field(default=None, description="Heat index °C")
    exposure_score: float = Field(ge=0, le=1, description="Heat exposure score")
    sensitivity_score: float = Field(ge=0, le=1, description="Population sensitivity score")
    adaptive_capacity_score: float = Field(ge=0, le=1, description="Adaptive capacity score")
    assessed_at: datetime
    recommendations: list[str] = Field(description="Heat safety recommendations")


# ---------------------------------------------------------------------------
# Water Quality
# ---------------------------------------------------------------------------

class WaterQualityParameter(BaseModel):
    """Individual water quality measurement."""

    parameter: str = Field(description="Parameter name (pH, dissolved_oxygen, turbidity, etc.)")
    value: float
    unit: str
    status: str = Field(description="Status: excellent, good, fair, poor, critical")


class WaterQualityResponse(BaseModel):
    """Water quality index for a location."""

    latitude: float
    longitude: float
    water_body: str | None = Field(default=None, description="Name of the water body")
    wqi: float = Field(ge=0, le=100, description="Water Quality Index 0-100")
    category: str = Field(description="Quality: excellent, good, fair, marginal, poor")
    parameters: list[WaterQualityParameter]
    measured_at: datetime
    source: str
