"""EcoTrack domain models."""
from __future__ import annotations

from .base import Domain, EcoTrackModel, Severity
from .biodiversity import (
    ConservationStatus,
    EcosystemHealthIndex,
    Species,
    SpeciesObservation,
    TaxonomicRank,
)
from .climate import (
    ClimateAnomaly,
    ClimateForecast,
    ClimateObservation,
    ClimateVariable,
)
from .food_security import (
    CropType,
    CropYieldPrediction,
    DroughtAlert,
    DroughtSeverity,
    FoodSecurityIndex,
)
from .geospatial import (
    BoundingBox,
    GeoPoint,
    GeoRegion,
    SpatioTemporalExtent,
)
from .health import (
    AirQualityReading,
    DiseaseVectorRisk,
    HealthMetric,
    HeatVulnerabilityIndex,
)
from .resources import (
    EnvironmentalJusticeScore,
    ResourceAllocation,
    ResourceType,
    WaterStressIndex,
)

__all__ = [
    # Base
    "Domain",
    "EcoTrackModel",
    "Severity",
    # Geospatial
    "BoundingBox",
    "GeoPoint",
    "GeoRegion",
    "SpatioTemporalExtent",
    # Climate
    "ClimateVariable",
    "ClimateObservation",
    "ClimateAnomaly",
    "ClimateForecast",
    # Biodiversity
    "TaxonomicRank",
    "ConservationStatus",
    "Species",
    "SpeciesObservation",
    "EcosystemHealthIndex",
    # Health
    "HealthMetric",
    "AirQualityReading",
    "DiseaseVectorRisk",
    "HeatVulnerabilityIndex",
    # Food Security
    "CropType",
    "DroughtSeverity",
    "CropYieldPrediction",
    "DroughtAlert",
    "FoodSecurityIndex",
    # Resources
    "ResourceType",
    "WaterStressIndex",
    "EnvironmentalJusticeScore",
    "ResourceAllocation",
]
