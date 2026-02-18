"""Species detection from camera trap and satellite imagery.

Provides :class:`SpeciesClassifier`, a transfer-learning classification
model that uses a configurable ``timm`` backbone (e.g. ResNet-50,
EfficientNet-B3, ViT-Base) with a custom classification head.
"""
from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn

try:
    import timm
except ImportError:  # pragma: no cover – allow import without timm for docs
    timm = None  # type: ignore[assignment]

from ecotrack_ml.models.base import EcoTrackModel, ModelMetadata, ModelTask


class SpeciesClassifier(EcoTrackModel):
    """Transfer-learning species classifier.

    The model wraps a ``timm`` image-classification backbone, strips its
    original classifier head, and replaces it with a custom head consisting
    of global average pooling → dropout → linear projection.

    Supported backbones include (but are not limited to):

    * ``resnet50``
    * ``efficientnet_b3``
    * ``vit_base_patch16_224``

    Args:
        metadata: Model metadata for the registry.
        backbone_name: Name of the ``timm`` model to use as the feature
            extractor.
        n_species: Number of species classes to predict.
        pretrained: If ``True``, initialise the backbone with ImageNet
            weights.
        dropout: Dropout probability for the classification head.
    """

    def __init__(
        self,
        metadata: ModelMetadata | None = None,
        *,
        backbone_name: str = "resnet50",
        n_species: int = 100,
        pretrained: bool = True,
        dropout: float = 0.3,
    ) -> None:
        if metadata is None:
            metadata = ModelMetadata(
                name=f"species_{backbone_name}",
                version="0.1.0",
                task=ModelTask.CLASSIFICATION,
                domain="biodiversity",
                description=f"Species classifier using {backbone_name} backbone",
            )
        super().__init__(metadata)

        if timm is None:
            raise ImportError(
                "The 'timm' package is required for SpeciesClassifier. "
                "Install it with: pip install timm>=0.9"
            )

        # Create backbone with no classifier head
        self.backbone = timm.create_model(
            backbone_name,
            pretrained=pretrained,
            num_classes=0,  # removes the final classification head
        )

        # Determine feature dimension from the backbone
        with torch.no_grad():
            dummy = torch.randn(1, 3, 224, 224)
            feature_dim = self.backbone(dummy).shape[-1]

        # Custom classification head
        self.classifier = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(feature_dim, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout),
            nn.Linear(512, n_species),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: ``(batch, 3, H, W)`` — RGB images.

        Returns:
            ``(batch, n_species)`` — class logits.
        """
        features = self.backbone(x)  # (B, feature_dim)
        return self.classifier(features)  # (B, n_species)

    def freeze_backbone(self) -> None:
        """Freeze backbone parameters for fine-tuning only the head."""
        for param in self.backbone.parameters():
            param.requires_grad = False

    def unfreeze_backbone(self) -> None:
        """Unfreeze backbone parameters for end-to-end training."""
        for param in self.backbone.parameters():
            param.requires_grad = True


__all__ = ["SpeciesClassifier"]
