"""EcoTrack ML training pipeline."""
from __future__ import annotations

from ecotrack_ml.training.augmentations import (
    Compose,
    GaussianNoise,
    RandomFlip,
    RandomRotation90,
    SpectralJitter,
)
from ecotrack_ml.training.datasets import (
    ClimateTimeSeriesDataset,
    MultiModalCropDataset,
    SatelliteImageDataset,
)
from ecotrack_ml.training.trainer import EcoTrackTrainer, TrainerConfig, TrainingResult

__all__ = [
    "ClimateTimeSeriesDataset",
    "Compose",
    "EcoTrackTrainer",
    "GaussianNoise",
    "MultiModalCropDataset",
    "RandomFlip",
    "RandomRotation90",
    "SatelliteImageDataset",
    "SpectralJitter",
    "TrainerConfig",
    "TrainingResult",
]
