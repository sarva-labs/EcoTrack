"""Tests for EcoTrack core domain models."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from ecotrack.models.base import Domain, EcoTrackModel, Severity
from ecotrack.models.geospatial import BoundingBox, GeoPoint, GeoRegion, SpatioTemporalExtent
from ecotrack.models.climate import ClimateObservation, ClimateVariable, ClimateAnomaly, ClimateForecast
from ecotrack.models.biodiversity import Species, SpeciesObservation, ConservationStatus, EcosystemHealthIndex
from ecotrack.models.health import AirQualityReading, DiseaseVectorRisk, HeatVulnerabilityIndex
from ecotrack.models.food_security import CropYieldPrediction, CropType, DroughtAlert
from ecotrack.models.resources import WaterStressIndex, EnvironmentalJusticeScore, ResourceType


class TestBaseModels:
    def test_domain_enum_values(self) -> None:
        assert Domain.CLIMATE == "climate"
        assert Domain.BIODIVERSITY == "biodiversity"
        assert len(Domain) == 5

    def test_severity_enum_values(self) -> None:
        assert Severity.CRITICAL == "critical"
        assert len(Severity) == 5

    def test_ecotrack_model_defaults(self) -> None:
        model = EcoTrackModel()
        assert isinstance(model.id, uuid.UUID)
        assert isinstance(model.created_at, datetime)
        assert model.metadata == {}

    def test_ecotrack_model_custom_id(self) -> None:
        custom_id = uuid.uuid4()
        model = EcoTrackModel(id=custom_id)
        assert model.id == custom_id


class TestGeospatialModels:
    def test_bounding_box_valid(self) -> None:
        bbox = BoundingBox(min_lon=-122.5, min_lat=37.7, max_lon=-122.3, max_lat=37.9)
        assert bbox.as_tuple == (-122.5, 37.7, -122.3, 37.9)

    def test_bounding_box_invalid_lon(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(min_lon=-200, min_lat=37.7, max_lon=-122.3, max_lat=37.9)

    def test_geo_point_valid(self) -> None:
        point = GeoPoint(longitude=-122.4, latitude=37.8)
        assert point.longitude == -122.4
        assert point.latitude == 37.8

    def test_geo_point_invalid_lat(self) -> None:
        with pytest.raises(ValidationError):
            GeoPoint(longitude=0, latitude=91)

    def test_geo_point_with_elevation(self) -> None:
        point = GeoPoint(longitude=0, latitude=0, elevation_m=100.0)
        assert point.elevation_m == 100.0

    def test_geo_region(self) -> None:
        region = GeoRegion(
            name="Test Region",
            geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            area_km2=100.0,
        )
        assert region.name == "Test Region"

    def test_spatiotemporal_extent(self) -> None:
        extent = SpatioTemporalExtent(
            bbox=BoundingBox(min_lon=-180, min_lat=-90, max_lon=180, max_lat=90),
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 12, 31),
        )
        assert extent.spatial_resolution_m is None


class TestClimateModels:
    def test_climate_observation(self) -> None:
        obs = ClimateObservation(
            variable=ClimateVariable.TEMPERATURE,
            value=25.5,
            unit="°C",
            location=GeoPoint(longitude=-122.4, latitude=37.8),
            timestamp=datetime.utcnow(),
            source="NOAA",
        )
        assert obs.domain == Domain.CLIMATE
        assert obs.quality_flag == 0

    def test_climate_variable_enum(self) -> None:
        assert ClimateVariable.TEMPERATURE == "temperature"
        assert len(ClimateVariable) >= 10

    def test_climate_anomaly(self) -> None:
        anomaly = ClimateAnomaly(
            variable=ClimateVariable.TEMPERATURE,
            severity=Severity.HIGH,
            bbox=BoundingBox(min_lon=0, min_lat=0, max_lon=10, max_lat=10),
            detected_at=datetime.utcnow(),
            baseline_mean=20.0,
            observed_value=28.0,
            deviation_sigma=3.2,
            description="Heat wave detected",
        )
        assert anomaly.severity == Severity.HIGH

    def test_climate_forecast_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ClimateForecast(
                variable=ClimateVariable.TEMPERATURE,
                bbox=BoundingBox(min_lon=0, min_lat=0, max_lon=10, max_lat=10),
                forecast_time=datetime.utcnow(),
                lead_hours=24,
                predicted_value=25.0,
                prediction_interval_lower=23.0,
                prediction_interval_upper=27.0,
                model_name="test",
                confidence=1.5,  # Invalid: > 1
            )


class TestBiodiversityModels:
    def test_species(self) -> None:
        species = Species(
            scientific_name="Panthera tigris",
            common_name="Tiger",
            conservation_status=ConservationStatus.ENDANGERED,
        )
        assert species.domain == Domain.BIODIVERSITY
        assert species.conservation_status == ConservationStatus.ENDANGERED

    def test_species_observation(self) -> None:
        obs = SpeciesObservation(
            species_name="Panthera tigris",
            location=GeoPoint(longitude=80.0, latitude=20.0),
            observed_at=datetime.utcnow(),
            count=2,
            confidence=0.95,
        )
        assert obs.count == 2

    def test_ecosystem_health_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            EcosystemHealthIndex(
                bbox=BoundingBox(min_lon=0, min_lat=0, max_lon=10, max_lat=10),
                timestamp=datetime.utcnow(),
                species_richness_score=1.5,  # Invalid: > 1
                habitat_integrity_score=0.8,
                connectivity_score=0.7,
                threat_level_score=0.3,
                overall_score=0.7,
            )


class TestHealthModels:
    def test_air_quality_reading(self) -> None:
        reading = AirQualityReading(
            location=GeoPoint(longitude=-73.9, latitude=40.7),
            timestamp=datetime.utcnow(),
            aqi=75,
            pm25=18.5,
            source="OpenAQ",
        )
        assert reading.domain == Domain.HEALTH
        assert reading.aqi == 75

    def test_aqi_bounds(self) -> None:
        with pytest.raises(ValidationError):
            AirQualityReading(
                location=GeoPoint(longitude=0, latitude=0),
                timestamp=datetime.utcnow(),
                aqi=501,  # Max is 500
            )


class TestFoodSecurityModels:
    def test_crop_yield_prediction(self) -> None:
        pred = CropYieldPrediction(
            crop_type=CropType.WHEAT,
            bbox=BoundingBox(min_lon=0, min_lat=0, max_lon=10, max_lat=10),
            prediction_date=datetime.utcnow(),
            harvest_date=datetime(2024, 9, 1),
            predicted_yield_tons_per_ha=3.5,
            yield_lower_bound=3.0,
            yield_upper_bound=4.0,
            historical_avg_yield=3.2,
            model_name="crop_yield_v1",
            confidence=0.85,
        )
        assert pred.crop_type == CropType.WHEAT


class TestResourceModels:
    def test_water_stress_index(self) -> None:
        wsi = WaterStressIndex(
            bbox=BoundingBox(min_lon=0, min_lat=0, max_lon=10, max_lat=10),
            timestamp=datetime.utcnow(),
            demand_million_m3=500.0,
            supply_million_m3=400.0,
            stress_ratio=1.25,
            severity=Severity.HIGH,
        )
        assert wsi.stress_ratio == 1.25

    def test_environmental_justice_score(self) -> None:
        ej = EnvironmentalJusticeScore(
            bbox=BoundingBox(min_lon=0, min_lat=0, max_lon=10, max_lat=10),
            timestamp=datetime.utcnow(),
            pollution_burden_score=0.7,
            socioeconomic_vulnerability=0.8,
            health_disparity_score=0.6,
            resource_access_score=0.5,
            overall_ej_score=0.65,
        )
        assert ej.overall_ej_score == 0.65
