"""Land cover and land use classification from satellite imagery.

Provides a :class:`UNetSegmentation` model for pixel-wise land cover
classification of multi-spectral satellite images (e.g. Sentinel-2 with
13 bands) and a :class:`LandCoverClasses` enum for the target label set.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any

import torch
import torch.nn as nn

from ecotrack_ml.models.base import EcoTrackModel, ModelMetadata, ModelTask


class LandCoverClasses(IntEnum):
    """Standard land cover class taxonomy.

    Values are consecutive integers starting from 0 so they can be used
    directly as target indices for cross-entropy loss.
    """

    WATER = 0
    FOREST = 1
    GRASSLAND = 2
    CROPLAND = 3
    URBAN = 4
    BARREN = 5
    WETLAND = 6
    SHRUBLAND = 7
    SNOW_ICE = 8
    CLOUD = 9


# ---------------------------------------------------------------------------
# U-Net building blocks
# ---------------------------------------------------------------------------


class _DoubleConv(nn.Module):
    """Two consecutive (Conv2d → BatchNorm → ReLU) blocks."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class _DownBlock(nn.Module):
    """Encoder block: MaxPool → DoubleConv."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.pool_conv = nn.Sequential(
            nn.MaxPool2d(kernel_size=2, stride=2),
            _DoubleConv(in_channels, out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.pool_conv(x)


class _UpBlock(nn.Module):
    """Decoder block: TransposeConv → concat skip → DoubleConv."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
        self.conv = _DoubleConv(in_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        """Upsample *x*, concatenate with *skip*, then apply convolutions.

        Handles spatial size mismatches by center-cropping *skip* to match.
        """
        x = self.up(x)
        # Handle spatial size mismatch
        diff_h = skip.size(2) - x.size(2)
        diff_w = skip.size(3) - x.size(3)
        x = nn.functional.pad(x, [diff_w // 2, diff_w - diff_w // 2, diff_h // 2, diff_h - diff_h // 2])
        return self.conv(torch.cat([skip, x], dim=1))


# ---------------------------------------------------------------------------
# U-Net Segmentation Model
# ---------------------------------------------------------------------------


class UNetSegmentation(EcoTrackModel):
    """U-Net for semantic segmentation of satellite imagery.

    Architecture:
        * **Encoder** — 4 down-sampling blocks with double convolution
          followed by max-pooling.
        * **Bottleneck** — double convolution at the lowest resolution.
        * **Decoder** — 4 up-sampling blocks with transposed convolution
          and skip connections from the corresponding encoder stage.
        * **Head** — 1×1 convolution projecting to class logits.

    Args:
        metadata: Model metadata for the registry.
        in_channels: Number of input spectral bands (e.g. 13 for
            Sentinel-2).
        n_classes: Number of land cover classes.
        features: List of feature map widths for each encoder stage.
            Defaults to ``[64, 128, 256, 512]``.
    """

    def __init__(
        self,
        metadata: ModelMetadata | None = None,
        *,
        in_channels: int = 13,
        n_classes: int = 10,
        features: list[int] | None = None,
    ) -> None:
        if metadata is None:
            metadata = ModelMetadata(
                name="unet_land_cover",
                version="0.1.0",
                task=ModelTask.SEGMENTATION,
                domain="biodiversity",
                description="U-Net segmentation for land cover classification",
                input_shape=(in_channels, 256, 256),
                output_shape=(n_classes, 256, 256),
            )
        super().__init__(metadata)

        if features is None:
            features = [64, 128, 256, 512]

        # Encoder
        self.inc = _DoubleConv(in_channels, features[0])
        self.down1 = _DownBlock(features[0], features[1])
        self.down2 = _DownBlock(features[1], features[2])
        self.down3 = _DownBlock(features[2], features[3])

        # Bottleneck
        self.bottleneck = _DownBlock(features[3], features[3] * 2)

        # Decoder
        self.up1 = _UpBlock(features[3] * 2, features[3])
        self.up2 = _UpBlock(features[3], features[2])
        self.up3 = _UpBlock(features[2], features[1])
        self.up4 = _UpBlock(features[1], features[0])

        # Output head
        self.outc = nn.Conv2d(features[0], n_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: ``(batch, in_channels, H, W)``

        Returns:
            ``(batch, n_classes, H, W)`` — per-pixel class logits.
        """
        # Encoder
        s1 = self.inc(x)  # (B, f0, H, W)
        s2 = self.down1(s1)  # (B, f1, H/2, W/2)
        s3 = self.down2(s2)  # (B, f2, H/4, W/4)
        s4 = self.down3(s3)  # (B, f3, H/8, W/8)

        # Bottleneck
        b = self.bottleneck(s4)  # (B, f3*2, H/16, W/16)

        # Decoder with skip connections
        d1 = self.up1(b, s4)  # (B, f3, H/8, W/8)
        d2 = self.up2(d1, s3)  # (B, f2, H/4, W/4)
        d3 = self.up3(d2, s2)  # (B, f1, H/2, W/2)
        d4 = self.up4(d3, s1)  # (B, f0, H, W)

        return self.outc(d4)  # (B, n_classes, H, W)


__all__ = ["LandCoverClasses", "UNetSegmentation"]
