"""Climate API request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

class ClimateObservationResponse(BaseModel):
    """Serialisable representation of a single climate observation."""

    id: str = Field(description="Unique observation identifier")
    variable: str = Field(description="Climate variable name (e.g. temperature, precipitation)")
    value: float = Field(description="Observed value")
    unit: str = Field(description="Measurement unit")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float | None = Field(default=None, description="Elevation in metres")
    timestamp: datetime = Field(description="Observation timestamp (UTC)")
    source: str = Field(description="Data source identifier (e.g. ERA5, NOAA)")
    quality_flag: str = Field(default="good", description="Quality flag: good, suspect, bad")


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

class ClimateQueryParams(BaseModel):
    """Combined spatial, temporal, and variable filter for climate data."""

    variable: str | None = Field(default=None, description="Climate variable filter")
    min_lon: float = Field(default=-180, ge=-180, le=180)
    min_lat: float = Field(default=-90, ge=-90, le=90)
    max_lon: float = Field(default=180, ge=-180, le=180)
    max_lat: float = Field(default=90, ge=-90, le=90)
    start_time: datetime | None = Field(default=None, description="Start of time window")
    end_time: datetime | None = Field(default=None, description="End of time window")
    source: str | None = Field(default=None, description="Data source filter")


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class ClimateForecastRequest(BaseModel):
    """Request body for generating a climate forecast."""

    variable: str = Field(description="Climate variable to forecast")
    min_lon: float = Field(ge=-180, le=180, description="Bounding box min longitude")
    min_lat: float = Field(ge=-90, le=90, description="Bounding box min latitude")
    max_lon: float = Field(ge=-180, le=180, description="Bounding box max longitude")
    max_lat: float = Field(ge=-90, le=90, description="Bounding box max latitude")
    forecast_horizon_hours: int = Field(default=72, ge=1, le=720, description="Forecast horizon in hours")
    model: str = Field(default="ensemble", description="Model to use: ensemble, gfs, ecmwf")


class ForecastPoint(BaseModel):
    """A single forecast timestep."""

    timestamp: datetime
    value: float
    lower_ci: float = Field(description="Lower 95% confidence bound")
    upper_ci: float = Field(description="Upper 95% confidence bound")


class ClimateForecastResponse(BaseModel):
    """Forecast results with confidence intervals."""

    forecast_id: str = Field(description="Unique forecast identifier")
    variable: str
    unit: str
    model_used: str
    generated_at: datetime
    horizon_hours: int
    bbox: dict[str, float] = Field(description="Bounding box used for the forecast")
    forecast_points: list[ForecastPoint]
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Anomaly
# ---------------------------------------------------------------------------

class ClimateAnomalyResponse(BaseModel):
    """Detected climate anomaly."""

    id: str = Field(description="Anomaly identifier")
    variable: str
    observed_value: float
    expected_value: float
    deviation: float = Field(description="Standard deviations from mean")
    severity: str = Field(description="Severity: info, low, medium, high, critical")
    latitude: float
    longitude: float
    detected_at: datetime
    description: str = Field(description="Human-readable anomaly description")


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------

class TrendDataPoint(BaseModel):
    """A single data point in a trend series."""

    year: int
    value: float
    anomaly: float = Field(description="Departure from baseline")


class ClimateTrendResponse(BaseModel):
    """Long-term climate trend analysis."""

    variable: str
    unit: str
    bbox: dict[str, float]
    period_years: int
    trend_direction: str = Field(description="Direction: increasing, decreasing, stable")
    trend_rate_per_decade: float = Field(description="Rate of change per decade")
    r_squared: float = Field(ge=0, le=1, description="Goodness of fit")
    p_value: float = Field(ge=0, le=1, description="Statistical significance")
    data_points: list[TrendDataPoint]
    summary: str = Field(description="Plain-English trend summary")
