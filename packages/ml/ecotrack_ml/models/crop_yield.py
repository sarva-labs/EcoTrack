"""Crop yield prediction from multi-modal inputs.

Provides :class:`CropYieldPredictor`, a multi-branch neural network that
fuses satellite imagery, weather time-series, and soil properties to
produce a crop yield regression estimate.
"""
from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn

from ecotrack_ml.models.base import EcoTrackModel, ModelMetadata, ModelTask, PredictionResult


class _ImageBranch(nn.Module):
    """CNN feature extractor for satellite imagery.

    Three convolutional blocks, each: Conv2d → BatchNorm → ReLU → MaxPool,
    followed by adaptive average pooling and a linear projection.
    """

    def __init__(self, in_channels: int, hidden_dim: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            # Block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            # Block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.projection = nn.Linear(128, hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Extract features from satellite image.

        Args:
            x: ``(batch, in_channels, H, W)``

        Returns:
            ``(batch, hidden_dim)``
        """
        h = self.features(x)
        h = h.view(h.size(0), -1)  # flatten
        return self.projection(h)


class _WeatherBranch(nn.Module):
    """LSTM encoder for weather time-series.

    Processes a temporal sequence of weather variables and returns the
    final hidden state projected to the fusion dimension.
    """

    def __init__(
        self, n_features: int, hidden_dim: int, num_layers: int = 2
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2 if num_layers > 1 else 0.0,
        )
        self.projection = nn.Linear(hidden_dim, hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode weather time-series.

        Args:
            x: ``(batch, seq_len, n_features)``

        Returns:
            ``(batch, hidden_dim)``
        """
        _, (h_n, _) = self.lstm(x)
        return self.projection(h_n[-1])  # use last layer hidden state


class _SoilBranch(nn.Module):
    """MLP encoder for soil property vectors."""

    def __init__(self, n_features: int, hidden_dim: int) -> None:
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(n_features, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(64, hidden_dim),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode soil properties.

        Args:
            x: ``(batch, n_features)``

        Returns:
            ``(batch, hidden_dim)``
        """
        return self.mlp(x)


class CropYieldPredictor(EcoTrackModel):
    """Multi-input model for crop yield prediction.

    Fuses three modalities:

    1. **Satellite imagery** — processed by a lightweight CNN branch.
    2. **Weather time-series** — encoded by an LSTM branch.
    3. **Soil properties** — encoded by an MLP branch.

    The branch outputs are concatenated and passed through a regression
    head that produces a single scalar yield estimate per sample.

    Args:
        metadata: Model metadata for the registry.
        image_channels: Number of spectral bands in the satellite image.
        n_weather_features: Number of weather variables per time step.
        n_soil_features: Number of soil property features.
        hidden_dim: Common hidden dimension for all branches and the
            fusion layer.
        lstm_layers: Number of stacked LSTM layers in the weather branch.
    """

    def __init__(
        self,
        metadata: ModelMetadata | None = None,
        *,
        image_channels: int = 13,
        n_weather_features: int = 8,
        n_soil_features: int = 12,
        hidden_dim: int = 128,
        lstm_layers: int = 2,
    ) -> None:
        if metadata is None:
            metadata = ModelMetadata(
                name="crop_yield_predictor",
                version="0.1.0",
                task=ModelTask.REGRESSION,
                domain="food_security",
                description="Multi-modal crop yield prediction model",
            )
        super().__init__(metadata)

        self.image_branch = _ImageBranch(image_channels, hidden_dim)
        self.weather_branch = _WeatherBranch(n_weather_features, hidden_dim, lstm_layers)
        self.soil_branch = _SoilBranch(n_soil_features, hidden_dim)

        # Fusion + regression head
        self.fusion = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim * 2),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: dict[str, torch.Tensor] | torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: A dictionary with keys:
                - ``'imagery'``: ``(batch, C, H, W)``
                - ``'weather'``: ``(batch, seq_len, n_weather_features)``
                - ``'soil'``: ``(batch, n_soil_features)``

                Alternatively, for ONNX-export compatibility a single
                tensor may be passed (only imagery branch used in that
                case).

        Returns:
            ``(batch, 1)`` — predicted crop yield.
        """
        if isinstance(x, dict):
            img_feat = self.image_branch(x["imagery"])
            weather_feat = self.weather_branch(x["weather"])
            soil_feat = self.soil_branch(x["soil"])
        else:
            # Fallback for single tensor (e.g. tracing)
            img_feat = self.image_branch(x)
            weather_feat = torch.zeros(x.size(0), img_feat.size(1), device=x.device)
            soil_feat = torch.zeros(x.size(0), img_feat.size(1), device=x.device)

        fused = torch.cat([img_feat, weather_feat, soil_feat], dim=1)
        return self.fusion(fused)

    def predict(self, x: dict[str, torch.Tensor] | torch.Tensor) -> PredictionResult:
        """Run inference with timing.

        Args:
            x: Input dictionary (see :meth:`forward`).

        Returns:
            :class:`PredictionResult` with yield predictions.
        """
        import time

        self.eval()
        start = time.perf_counter()
        with torch.no_grad():
            output = self.forward(x)
        elapsed = (time.perf_counter() - start) * 1000
        return PredictionResult(
            predictions=output.cpu().numpy(),
            inference_time_ms=elapsed,
        )


__all__ = ["CropYieldPredictor"]
