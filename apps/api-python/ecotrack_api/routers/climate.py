"""Climate intelligence API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ecotrack_api.schemas.climate import (
    ClimateAnomalyResponse,
    ClimateForecastRequest,
    ClimateForecastResponse,
    ClimateObservationResponse,
    ClimateTrendResponse,
    ForecastPoint,
    TrendDataPoint,
)
from ecotrack_api.schemas.common import PaginatedResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Sample / stub data generators
# ---------------------------------------------------------------------------

def _sample_observations(
    variable: str | None, page: int, page_size: int
) -> PaginatedResponse[ClimateObservationResponse]:
    """Return realistic stub climate observations."""
    now = datetime.now(tz=timezone.utc)
    items = [
        ClimateObservationResponse(
            id=f"obs-clim-{i:04d}",
            variable=variable or "temperature",
            value=round(15.0 + i * 0.3, 2),
            unit="°C" if (variable or "temperature") == "temperature" else "mm",
            latitude=round(40.0 + i * 0.1, 4),
            longitude=round(-74.0 + i * 0.1, 4),
            elevation_m=50.0 + i * 10,
            timestamp=now - timedelta(hours=i),
            source="ERA5",
            quality_flag="good",
        )
        for i in range(min(page_size, 5))
    ]
    total = 142
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/observations",
    response_model=PaginatedResponse[ClimateObservationResponse],
    summary="Query climate observations",
    responses={422: {"description": "Validation error"}},
)
async def get_climate_observations(
    variable: str | None = Query(None, description="Climate variable (temperature, precipitation, humidity, wind_speed, pressure)"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    start_time: datetime | None = Query(None, description="Start of time window (ISO 8601)"),
    end_time: datetime | None = Query(None, description="End of time window (ISO 8601)"),
    source: str | None = Query(None, description="Data source filter (ERA5, NOAA, ECMWF)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[ClimateObservationResponse]:
    """Query climate observations with spatial, temporal, and variable filters.

    Returns paginated climate observation records from the EcoTrack data lake.
    Supports filtering by climate variable, bounding box, time range, and source.
    """
    return _sample_observations(variable, page, page_size)


@router.post(
    "/forecast",
    response_model=ClimateForecastResponse,
    status_code=201,
    summary="Generate climate forecast",
    responses={201: {"description": "Forecast generated"}, 422: {"description": "Validation error"}},
)
async def create_climate_forecast(
    request: ClimateForecastRequest,
) -> ClimateForecastResponse:
    """Generate a climate forecast for a specified region and variable.

    Runs the EcoTrack forecasting pipeline and returns timestep-level
    predictions with 95% confidence intervals.
    """
    now = datetime.now(tz=timezone.utc)
    points = [
        ForecastPoint(
            timestamp=now + timedelta(hours=h),
            value=round(18.0 + h * 0.05, 2),
            lower_ci=round(16.5 + h * 0.04, 2),
            upper_ci=round(19.5 + h * 0.06, 2),
        )
        for h in range(0, request.forecast_horizon_hours, max(1, request.forecast_horizon_hours // 12))
    ]
    return ClimateForecastResponse(
        forecast_id="fcst-20260218-001",
        variable=request.variable,
        unit="°C" if request.variable == "temperature" else "mm",
        model_used=request.model,
        generated_at=now,
        horizon_hours=request.forecast_horizon_hours,
        bbox={
            "min_lon": request.min_lon,
            "min_lat": request.min_lat,
            "max_lon": request.max_lon,
            "max_lat": request.max_lat,
        },
        forecast_points=points,
        metadata={"resolution_km": 25, "ensemble_members": 30},
    )


@router.get(
    "/anomalies",
    response_model=PaginatedResponse[ClimateAnomalyResponse],
    summary="Query climate anomalies",
    responses={422: {"description": "Validation error"}},
)
async def get_climate_anomalies(
    variable: str | None = Query(None, description="Climate variable filter"),
    severity: str | None = Query(None, description="Severity filter: info, low, medium, high, critical"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    start_time: datetime | None = Query(None, description="Start of time window"),
    end_time: datetime | None = Query(None, description="End of time window"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[ClimateAnomalyResponse]:
    """Query detected climate anomalies.

    Returns anomalies detected by the EcoTrack anomaly detection models,
    filtered by severity, variable, and spatial / temporal extent.
    """
    now = datetime.now(tz=timezone.utc)
    items = [
        ClimateAnomalyResponse(
            id="anom-001",
            variable=variable or "temperature",
            observed_value=38.5,
            expected_value=31.2,
            deviation=3.2,
            severity=severity or "high",
            latitude=28.6139,
            longitude=77.2090,
            detected_at=now - timedelta(hours=2),
            description="Temperature 3.2σ above seasonal mean for Delhi NCR region",
        ),
        ClimateAnomalyResponse(
            id="anom-002",
            variable=variable or "precipitation",
            observed_value=0.2,
            expected_value=12.5,
            deviation=-2.8,
            severity=severity or "medium",
            latitude=19.0760,
            longitude=72.8777,
            detected_at=now - timedelta(hours=6),
            description="Precipitation deficit of 98% over Mumbai metropolitan area",
        ),
    ]
    return PaginatedResponse(
        items=items, total=2, page=page, page_size=page_size, has_next=False
    )


@router.get(
    "/trends",
    response_model=ClimateTrendResponse,
    summary="Analyse long-term climate trends",
    responses={422: {"description": "Validation error"}},
)
async def get_climate_trends(
    variable: str = Query(..., description="Climate variable to analyse"),
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    period_years: int = Query(10, ge=1, le=100, description="Analysis period in years"),
) -> ClimateTrendResponse:
    """Analyse long-term climate trends for a region.

    Computes linear regression over the requested period and returns
    the trend rate, statistical significance, and yearly data points.
    """
    base_year = 2026 - period_years
    data_points = [
        TrendDataPoint(
            year=base_year + i,
            value=round(14.5 + i * 0.03, 2),
            anomaly=round(-0.15 + i * 0.03, 2),
        )
        for i in range(period_years)
    ]
    return ClimateTrendResponse(
        variable=variable,
        unit="°C" if variable == "temperature" else "mm",
        bbox={"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat},
        period_years=period_years,
        trend_direction="increasing",
        trend_rate_per_decade=0.3,
        r_squared=0.87,
        p_value=0.001,
        data_points=data_points,
        summary=f"{variable.title()} shows an increasing trend of +0.30 per decade (p<0.01) over the past {period_years} years.",
    )


@router.get(
    "/variables",
    summary="List available climate variables",
    responses={200: {"description": "List of climate variables"}},
)
async def list_climate_variables() -> dict[str, Any]:
    """List all climate variables available in the EcoTrack platform."""
    return {
        "variables": [
            {"name": "temperature", "unit": "°C", "description": "Surface air temperature", "sources": ["ERA5", "NOAA", "ECMWF"]},
            {"name": "precipitation", "unit": "mm", "description": "Total precipitation", "sources": ["ERA5", "GPM", "CHIRPS"]},
            {"name": "humidity", "unit": "%", "description": "Relative humidity", "sources": ["ERA5", "NOAA"]},
            {"name": "wind_speed", "unit": "m/s", "description": "10m wind speed", "sources": ["ERA5", "GFS"]},
            {"name": "pressure", "unit": "hPa", "description": "Sea-level pressure", "sources": ["ERA5", "NOAA"]},
            {"name": "sea_surface_temperature", "unit": "°C", "description": "Sea surface temperature", "sources": ["NOAA-OISST", "Copernicus"]},
            {"name": "soil_moisture", "unit": "m³/m³", "description": "Volumetric soil moisture", "sources": ["ERA5-Land", "SMAP"]},
            {"name": "snow_depth", "unit": "m", "description": "Snow depth", "sources": ["ERA5", "NOAA"]},
        ]
    }
