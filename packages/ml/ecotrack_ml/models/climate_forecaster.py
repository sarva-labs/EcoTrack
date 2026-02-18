"""Climate forecasting models using temporal convolutional networks and transformers.

This module provides two complementary architectures for multi-variate
climate time-series forecasting:

* :class:`ClimateTCN` — Temporal Convolutional Network with dilated causal
  convolutions.  Best suited for fixed-horizon, uni-directional forecasting.
* :class:`ClimateTransformer` — Encoder-only transformer with sinusoidal
  positional encoding.  Best suited for multi-step, multi-variate forecasting.
"""
from __future__ import annotations

import math
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils import weight_norm

from ecotrack_ml.models.base import EcoTrackModel, ModelMetadata, ModelTask

# ---------------------------------------------------------------------------
# Temporal Convolutional Network
# ---------------------------------------------------------------------------


class _CausalConv1d(nn.Module):
    """Causal convolution that pads only on the left so future values cannot leak."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = weight_norm(
            nn.Conv1d(
                in_channels,
                out_channels,
                kernel_size,
                dilation=dilation,
                padding=self.padding,
            )
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply causal convolution.

        Args:
            x: Tensor of shape ``(batch, channels, time)``.

        Returns:
            Tensor of shape ``(batch, out_channels, time)``.
        """
        out = self.conv(x)
        # Trim the right side so that the output length equals the input length
        if self.padding > 0:
            out = out[:, :, : -self.padding]
        return self.dropout(F.relu(out))


class _ResidualBlock(nn.Module):
    """Residual block with two causal convolutions and a skip / residual path."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.conv1 = _CausalConv1d(in_channels, out_channels, kernel_size, dilation, dropout)
        self.conv2 = _CausalConv1d(out_channels, out_channels, kernel_size, dilation, dropout)
        self.downsample = (
            nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward through the residual block.

        Args:
            x: ``(batch, in_channels, time)``

        Returns:
            ``(batch, out_channels, time)``
        """
        residual = x if self.downsample is None else self.downsample(x)
        out = self.conv1(x)
        out = self.conv2(out)
        return F.relu(out + residual)


class ClimateTCN(EcoTrackModel):
    """Temporal Convolutional Network for climate time-series forecasting.

    Uses multi-scale dilated causal convolutions (dilations 1, 2, 4, 8, 16)
    with residual blocks and weight normalisation.

    Args:
        metadata: Model metadata for the registry.
        n_inputs: Number of input variables / channels.
        n_outputs: Number of output variables to predict.
        n_channels: List of channel widths for each residual block level.
            Defaults to ``[64, 64, 128, 128, 256]`` (five levels matching
            the five dilation factors).
        kernel_size: Temporal kernel size.  Defaults to ``3``.
        dropout: Dropout probability.  Defaults to ``0.2``.
    """

    def __init__(
        self,
        metadata: ModelMetadata | None = None,
        *,
        n_inputs: int = 6,
        n_outputs: int = 6,
        n_channels: list[int] | None = None,
        kernel_size: int = 3,
        dropout: float = 0.2,
    ) -> None:
        if metadata is None:
            metadata = ModelMetadata(
                name="climate_tcn",
                version="0.1.0",
                task=ModelTask.FORECASTING,
                domain="climate",
                description="Temporal Convolutional Network for climate forecasting",
            )
        super().__init__(metadata)

        if n_channels is None:
            n_channels = [64, 64, 128, 128, 256]

        dilations = [1, 2, 4, 8, 16]
        layers: list[nn.Module] = []
        in_ch = n_inputs
        for i, out_ch in enumerate(n_channels):
            dilation = dilations[i % len(dilations)]
            layers.append(_ResidualBlock(in_ch, out_ch, kernel_size, dilation, dropout))
            in_ch = out_ch

        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(n_channels[-1], n_outputs)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: ``(batch, channels, time_steps)``

        Returns:
            ``(batch, n_outputs)`` — point forecast for the next time step.
        """
        out = self.network(x)  # (B, C_last, T)
        out = out[:, :, -1]  # take the last time step
        return self.fc(out)  # (B, n_outputs)


# ---------------------------------------------------------------------------
# Transformer-based Climate Forecaster
# ---------------------------------------------------------------------------


class _SinusoidalPositionalEncoding(nn.Module):
    """Standard sinusoidal positional encoding for temporal positions."""

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Add positional encoding.

        Args:
            x: ``(batch, seq_len, d_model)``

        Returns:
            ``(batch, seq_len, d_model)`` with position info added.
        """
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class ClimateTransformer(EcoTrackModel):
    """Transformer encoder for multi-variate climate forecasting.

    Uses sinusoidal positional encoding, multi-head self-attention
    encoder layers, and a linear projection head.

    Args:
        metadata: Model metadata for the registry.
        d_model: Hidden dimension of the transformer.
        nhead: Number of attention heads.
        num_layers: Number of encoder layers.
        dim_feedforward: Dimension of the FFN inside each encoder layer.
        max_seq_len: Maximum sequence length for the positional encoding.
        n_variables: Number of input climate variables.
        forecast_horizon: Number of future time steps to predict.
        dropout: Dropout probability.
    """

    def __init__(
        self,
        metadata: ModelMetadata | None = None,
        *,
        d_model: int = 128,
        nhead: int = 8,
        num_layers: int = 4,
        dim_feedforward: int = 512,
        max_seq_len: int = 365,
        n_variables: int = 6,
        forecast_horizon: int = 30,
        dropout: float = 0.1,
    ) -> None:
        if metadata is None:
            metadata = ModelMetadata(
                name="climate_transformer",
                version="0.1.0",
                task=ModelTask.FORECASTING,
                domain="climate",
                description="Transformer for multi-variate climate forecasting",
            )
        super().__init__(metadata)

        self.n_variables = n_variables
        self.forecast_horizon = forecast_horizon

        # Project input variables into d_model
        self.input_projection = nn.Linear(n_variables, d_model)
        self.pos_encoder = _SinusoidalPositionalEncoding(d_model, max_seq_len, dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Output projection: map from d_model to (forecast_horizon * n_variables)
        self.output_projection = nn.Sequential(
            nn.Linear(d_model, dim_feedforward),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, forecast_horizon * n_variables),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: ``(batch, seq_len, n_variables)``

        Returns:
            ``(batch, forecast_horizon, n_variables)``
        """
        # Project and encode
        h = self.input_projection(x)  # (B, S, d_model)
        h = self.pos_encoder(h)
        h = self.transformer_encoder(h)  # (B, S, d_model)

        # Use the last encoder output for prediction
        h = h[:, -1, :]  # (B, d_model)
        out = self.output_projection(h)  # (B, forecast_horizon * n_variables)
        return out.view(-1, self.forecast_horizon, self.n_variables)


__all__ = ["ClimateTCN", "ClimateTransformer"]
