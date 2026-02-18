"""EcoTrack ML model zoo.

Re-exports all model classes for convenient access::

    from ecotrack_ml.models import ClimateTCN, UNetSegmentation
"""
from __future__ import annotations

from ecotrack_ml.models.base import (
    EcoTrackModel,
    ModelMetadata,
    ModelTask,
    PredictionResult,
)
from ecotrack_ml.models.anomaly_detector import EnvironmentalAutoencoder
from ecotrack_ml.models.climate_forecaster import ClimateTCN, ClimateTransformer
from ecotrack_ml.models.crop_yield import CropYieldPredictor
from ecotrack_ml.models.land_cover import LandCoverClasses, UNetSegmentation
from ecotrack_ml.models.species_detector import SpeciesClassifier

__all__ = [
    "ClimateTCN",
    "ClimateTransformer",
    "CropYieldPredictor",
    "EcoTrackModel",
    "EnvironmentalAutoencoder",
    "LandCoverClasses",
    "ModelMetadata",
    "ModelTask",
    "PredictionResult",
    "SpeciesClassifier",
    "UNetSegmentation",
]
