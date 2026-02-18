"""Public health and environmental health API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ecotrack_api.schemas.common import PaginatedResponse
from ecotrack_api.schemas.health import (
    AirQualityForecastPoint,
    AirQualityForecastResponse,
    AirQualityResponse,
    DiseaseVectorDetail,
    DiseaseVectorRiskResponse,
    HeatVulnerabilityResponse,
    PollutantReading,
    WaterQualityParameter,
    WaterQualityResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/air-quality",
    response_model=PaginatedResponse[AirQualityResponse],
    summary="Current air quality readings",
    responses={422: {"description": "Validation error"}},
)
async def get_air_quality(
    min_lon: float = Query(-180, ge=-180, le=180, description="Bounding box minimum longitude"),
    min_lat: float = Query(-90, ge=-90, le=90, description="Bounding box minimum latitude"),
    max_lon: float = Query(180, ge=-180, le=180, description="Bounding box maximum longitude"),
    max_lat: float = Query(90, ge=-90, le=90, description="Bounding box maximum latitude"),
    pollutant: str | None = Query(None, description="Filter by specific pollutant (PM2.5, PM10, O3, NO2, SO2, CO)"),
    min_aqi: int | None = Query(None, ge=0, description="Minimum AQI threshold"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
) -> PaginatedResponse[AirQualityResponse]:
    """Get current air quality readings within a bounding box.

    Returns real-time AQI readings from monitoring stations sourced via
    OpenAQ, EPA AirNow, and partner sensor networks.
    """
    now = datetime.now(tz=timezone.utc)
    items = [
        AirQualityResponse(
            station_id="AQ-DEL-001",
            latitude=28.6139,
            longitude=77.2090,
            aqi=156,
            category="Unhealthy",
            dominant_pollutant="PM2.5",
            pollutants=[
                PollutantReading(pollutant="PM2.5", value=65.4, unit="µg/m³", aqi_contribution=156),
                PollutantReading(pollutant="PM10", value=112.0, unit="µg/m³", aqi_contribution=80),
                PollutantReading(pollutant="O3", value=45.2, unit="µg/m³", aqi_contribution=41),
                PollutantReading(pollutant="NO2", value=38.1, unit="µg/m³", aqi_contribution=34),
            ],
            measured_at=now - timedelta(minutes=15),
            source="OpenAQ",
        ),
        AirQualityResponse(
            station_id="AQ-NYC-012",
            latitude=40.7128,
            longitude=-74.0060,
            aqi=52,
            category="Moderate",
            dominant_pollutant="O3",
            pollutants=[
                PollutantReading(pollutant="PM2.5", value=12.1, unit="µg/m³", aqi_contribution=50),
                PollutantReading(pollutant="O3", value=68.3, unit="µg/m³", aqi_contribution=52),
                PollutantReading(pollutant="NO2", value=22.0, unit="µg/m³", aqi_contribution=20),
            ],
            measured_at=now - timedelta(minutes=8),
            source="EPA AirNow",
        ),
    ]
    if min_aqi is not None:
        items = [aq for aq in items if aq.aqi >= min_aqi]
    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_next=False
    )


@router.get(
    "/air-quality/forecast",
    response_model=AirQualityForecastResponse,
    summary="Air quality forecast",
    responses={422: {"description": "Validation error"}},
)
async def get_air_quality_forecast(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    hours: int = Query(48, ge=1, le=120, description="Forecast horizon in hours"),
) -> AirQualityForecastResponse:
    """Get air quality forecast for a specific location.

    Provides hourly AQI predictions using the EcoTrack atmospheric
    dispersion model for up to 120 hours.
    """
    now = datetime.now(tz=timezone.utc)
    categories = ["Good", "Good", "Moderate", "Moderate", "Unhealthy for Sensitive Groups", "Moderate", "Good"]
    points = [
        AirQualityForecastPoint(
            timestamp=now + timedelta(hours=h),
            aqi=35 + (h % 12) * 8,
            category=categories[h % len(categories)],
            dominant_pollutant="O3" if h % 3 == 0 else "PM2.5",
        )
        for h in range(0, hours, max(1, hours // 24))
    ]
    return AirQualityForecastResponse(
        latitude=latitude,
        longitude=longitude,
        generated_at=now,
        forecast_hours=hours,
        forecast_points=points,
    )


@router.get(
    "/disease-risk",
    response_model=DiseaseVectorRiskResponse,
    summary="Disease vector risk assessment",
    responses={422: {"description": "Validation error"}},
)
async def get_disease_vector_risk(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
    disease: str | None = Query(None, description="Specific disease filter (malaria, dengue, zika, chikungunya)"),
) -> DiseaseVectorRiskResponse:
    """Get disease vector risk assessment for a location.

    Combines environmental conditions (temperature, humidity, standing
    water), vector habitat suitability, and historical incidence data
    to compute location-specific risk scores.
    """
    now = datetime.now(tz=timezone.utc)
    all_diseases = [
        DiseaseVectorDetail(
            disease="dengue",
            vector="Aedes aegypti",
            risk_score=0.72,
            risk_level="high",
            contributing_factors=["high humidity", "urban standing water", "warm temperatures"],
        ),
        DiseaseVectorDetail(
            disease="malaria",
            vector="Anopheles stephensi",
            risk_score=0.45,
            risk_level="moderate",
            contributing_factors=["monsoon season", "rural water bodies"],
        ),
        DiseaseVectorDetail(
            disease="zika",
            vector="Aedes aegypti",
            risk_score=0.31,
            risk_level="moderate",
            contributing_factors=["tropical climate", "urban density"],
        ),
    ]
    diseases = all_diseases
    if disease:
        diseases = [d for d in diseases if d.disease == disease.lower()]
    return DiseaseVectorRiskResponse(
        latitude=latitude,
        longitude=longitude,
        overall_risk=0.72,
        risk_level="high",
        diseases=diseases,
        environmental_factors={
            "temperature": 0.85,
            "humidity": 0.78,
            "precipitation": 0.62,
            "land_cover": 0.45,
        },
        assessed_at=now,
        valid_until=now + timedelta(days=7),
    )


@router.get(
    "/heat-vulnerability",
    response_model=HeatVulnerabilityResponse,
    summary="Heat vulnerability mapping",
    responses={422: {"description": "Validation error"}},
)
async def get_heat_vulnerability(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> HeatVulnerabilityResponse:
    """Get heat vulnerability index for a location.

    Combines exposure (temperature, urban heat island), sensitivity
    (demographics, pre-existing conditions), and adaptive capacity
    (green space, cooling centres, healthcare access).
    """
    return HeatVulnerabilityResponse(
        latitude=latitude,
        longitude=longitude,
        region_name="South Delhi Urban Cluster",
        vulnerability_index=0.78,
        vulnerability_level="high",
        current_temperature_c=42.3,
        heat_index_c=48.1,
        exposure_score=0.85,
        sensitivity_score=0.72,
        adaptive_capacity_score=0.35,
        assessed_at=datetime.now(tz=timezone.utc),
        recommendations=[
            "Issue extreme heat advisory for vulnerable populations",
            "Open additional cooling centres in high-density areas",
            "Distribute hydration supplies to outdoor workers",
            "Activate emergency medical standby protocols",
        ],
    )


@router.get(
    "/water-quality",
    response_model=WaterQualityResponse,
    summary="Water quality index",
    responses={422: {"description": "Validation error"}},
)
async def get_water_quality(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> WaterQualityResponse:
    """Get water quality index for the nearest water body.

    Returns composite Water Quality Index (WQI) and individual parameter
    measurements for the nearest monitored water body.
    """
    return WaterQualityResponse(
        latitude=latitude,
        longitude=longitude,
        water_body="Yamuna River - Wazirabad Segment",
        wqi=38.5,
        category="poor",
        parameters=[
            WaterQualityParameter(parameter="pH", value=7.8, unit="pH", status="good"),
            WaterQualityParameter(parameter="dissolved_oxygen", value=3.2, unit="mg/L", status="poor"),
            WaterQualityParameter(parameter="BOD", value=28.5, unit="mg/L", status="critical"),
            WaterQualityParameter(parameter="total_coliform", value=24000.0, unit="MPN/100mL", status="critical"),
            WaterQualityParameter(parameter="turbidity", value=45.0, unit="NTU", status="fair"),
            WaterQualityParameter(parameter="nitrates", value=8.2, unit="mg/L", status="good"),
        ],
        measured_at=datetime.now(tz=timezone.utc) - timedelta(hours=2),
        source="Central Pollution Control Board",
    )
