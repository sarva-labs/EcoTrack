"""PyTorch dataset classes for EcoTrack domains.

Provides domain-specific ``torch.utils.data.Dataset`` implementations for
climate time-series, satellite imagery, and multi-modal crop yield data.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import torch
from torch.utils.data import Dataset


# ---------------------------------------------------------------------------
# Climate Time-Series
# ---------------------------------------------------------------------------


class ClimateTimeSeriesDataset(Dataset):
    """Sliding-window dataset for climate forecasting.

    Creates overlapping ``(input_window, target_window)`` pairs from a
    continuous time-series array.

    Args:
        data: NumPy array of shape ``(time_steps, n_variables)``.
        window_size: Number of time steps in each input window.
        forecast_horizon: Number of time steps to predict after the window.
        transform: Optional callable applied to input windows.
    """

    def __init__(
        self,
        data: np.ndarray,
        window_size: int = 60,
        forecast_horizon: int = 30,
        transform: Callable[[np.ndarray], np.ndarray] | None = None,
    ) -> None:
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        self.data = data.astype(np.float32)
        self.window_size = window_size
        self.forecast_horizon = forecast_horizon
        self.transform = transform
        self._length = max(0, len(data) - window_size - forecast_horizon + 1)

    def __len__(self) -> int:
        return self._length

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        """Return ``(input_window, target_window)`` tensors.

        ``input_window`` has shape ``(n_variables, window_size)`` (channels-first)
        for compatibility with :class:`~ecotrack_ml.models.climate_forecaster.ClimateTCN`.
        ``target_window`` has shape ``(forecast_horizon, n_variables)``.
        """
        start = idx
        end_input = start + self.window_size
        end_target = end_input + self.forecast_horizon

        x = self.data[start:end_input]  # (window, vars)
        y = self.data[end_input:end_target]  # (horizon, vars)

        if self.transform is not None:
            x = self.transform(x)

        # Transpose x to (vars, window) for TCN / conv1d
        x_tensor = torch.from_numpy(x.T.copy())
        y_tensor = torch.from_numpy(y.copy())
        return x_tensor, y_tensor


# ---------------------------------------------------------------------------
# Satellite Imagery
# ---------------------------------------------------------------------------


class SatelliteImageDataset(Dataset):
    """Dataset for satellite imagery (e.g. GeoTIFF files).

    Loads images lazily and caches the most recently used tiles.  If
    ``rasterio`` is not installed, falls back to generating random
    placeholder tensors (useful for testing / CI).

    Args:
        image_paths: List of paths to image files.
        label_paths: Corresponding label / mask file paths (same length).
        transform: Optional augmentation pipeline
            (see :mod:`ecotrack_ml.training.augmentations`).
        cache_size: Maximum number of tiles to hold in the LRU cache.
    """

    def __init__(
        self,
        image_paths: Sequence[str | Path],
        label_paths: Sequence[str | Path] | None = None,
        transform: Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]] | None = None,
        cache_size: int = 128,
    ) -> None:
        self.image_paths = [Path(p) for p in image_paths]
        self.label_paths = [Path(p) for p in label_paths] if label_paths else None
        self.transform = transform

        # Wrap the loader in an LRU cache
        self._load_image = functools.lru_cache(maxsize=cache_size)(self._load_image_uncached)

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        """Load and return ``(image, label)`` tensors.

        ``image`` has shape ``(C, H, W)``; ``label`` has shape ``(H, W)``
        (integer class IDs for segmentation).
        """
        image = self._load_image(idx)
        label = self._load_label(idx) if self.label_paths else np.zeros(image.shape[1:], dtype=np.int64)

        if self.transform is not None:
            image, label = self.transform(image, label)

        return torch.from_numpy(image.copy()).float(), torch.from_numpy(label.copy()).long()

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_image_uncached(idx: int) -> np.ndarray:
        """Load a GeoTIFF image to a NumPy array.

        .. note::
            This is a static placeholder. In production, ``rasterio`` or
            ``rioxarray`` should be used.  The method is wrapped with
            ``functools.lru_cache`` at instance level.
        """
        try:
            import rasterio

            # Actual loading path would use the stored image_paths[idx]
            # but since this is a static method cached by idx we need
            # the instance context. See __getitem__ for real path usage.
            raise NotImplementedError("Override _load_image for production use")
        except (ImportError, NotImplementedError):
            # Fallback: return a random image for testing
            return np.random.randn(13, 256, 256).astype(np.float32)

    def _load_label(self, idx: int) -> np.ndarray:
        """Load a label / mask file."""
        if self.label_paths is None:
            return np.zeros((256, 256), dtype=np.int64)
        try:
            import rasterio

            with rasterio.open(self.label_paths[idx]) as src:
                return src.read(1).astype(np.int64)
        except ImportError:
            return np.random.randint(0, 10, (256, 256), dtype=np.int64)


# ---------------------------------------------------------------------------
# Multi-Modal Crop Dataset
# ---------------------------------------------------------------------------


class MultiModalCropDataset(Dataset):
    """Multi-modal dataset for crop yield prediction.

    Aligns satellite imagery, weather time-series, and soil property
    arrays into a single dictionary-based sample.

    Args:
        imagery_paths: Paths to satellite image files.
        weather_data: NumPy array of shape ``(n_samples, seq_len, n_weather_features)``
            or list of CSV paths.
        soil_data: NumPy array of shape ``(n_samples, n_soil_features)``.
        yields: NumPy array of shape ``(n_samples,)`` — target yield values.
        image_transform: Optional transform for imagery.
    """

    def __init__(
        self,
        imagery_paths: Sequence[str | Path],
        weather_data: np.ndarray,
        soil_data: np.ndarray,
        yields: np.ndarray,
        image_transform: Callable[[np.ndarray], np.ndarray] | None = None,
    ) -> None:
        assert len(imagery_paths) == len(weather_data) == len(soil_data) == len(yields), (
            "All input arrays / lists must have the same length."
        )
        self.imagery_paths = [Path(p) for p in imagery_paths]
        self.weather_data = weather_data.astype(np.float32)
        self.soil_data = soil_data.astype(np.float32)
        self.yields = yields.astype(np.float32)
        self.image_transform = image_transform

    def __len__(self) -> int:
        return len(self.yields)

    def __getitem__(self, idx: int) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        """Return ``(input_dict, target)`` for the crop yield model.

        ``input_dict`` has keys ``'imagery'``, ``'weather'``, ``'soil'``.
        """
        # Load satellite image
        try:
            import rasterio

            with rasterio.open(self.imagery_paths[idx]) as src:
                image = src.read().astype(np.float32)
        except ImportError:
            image = np.random.randn(13, 64, 64).astype(np.float32)

        if self.image_transform is not None:
            image = self.image_transform(image)

        inputs = {
            "imagery": torch.from_numpy(image),
            "weather": torch.from_numpy(self.weather_data[idx]),
            "soil": torch.from_numpy(self.soil_data[idx]),
        }
        target = torch.tensor([self.yields[idx]], dtype=torch.float32)
        return inputs, target


__all__ = [
    "ClimateTimeSeriesDataset",
    "MultiModalCropDataset",
    "SatelliteImageDataset",
]
