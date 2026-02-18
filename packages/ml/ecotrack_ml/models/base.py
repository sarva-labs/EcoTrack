"""Base ML model abstractions for EcoTrack."""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Generic, TypeVar

import numpy as np
import torch
import torch.nn as nn

T_Input = TypeVar("T_Input")
T_Output = TypeVar("T_Output")


class ModelTask(str, Enum):
    """ML task types supported by the EcoTrack platform.

    Each task type corresponds to a distinct machine-learning paradigm
    used across the five EcoTrack domains (climate, biodiversity,
    health, food security, resource equity).
    """

    REGRESSION = "regression"
    CLASSIFICATION = "classification"
    SEGMENTATION = "segmentation"
    FORECASTING = "forecasting"
    ANOMALY_DETECTION = "anomaly_detection"
    OBJECT_DETECTION = "object_detection"


@dataclass
class ModelMetadata:
    """Model metadata for the registry and lineage tracking.

    Attributes:
        name: Human-readable model name (e.g. ``"climate_tcn_v2"``).
        version: Semantic version string.
        task: The ML task this model addresses.
        domain: EcoTrack domain (climate, biodiversity, …).
        description: Free-text description of the model.
        input_shape: Expected input tensor shape (*excluding* batch dim).
        output_shape: Expected output tensor shape (*excluding* batch dim).
        parameters_count: Trainable parameter count (populated at runtime).
        training_dataset: Name / URI of the training dataset.
        metrics: Evaluation metrics collected during training or eval.
        tags: Arbitrary key-value tags for filtering / search.
    """

    name: str
    version: str
    task: ModelTask
    domain: str
    description: str
    input_shape: tuple[int, ...] | None = None
    output_shape: tuple[int, ...] | None = None
    parameters_count: int = 0
    training_dataset: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class PredictionResult:
    """Standardized prediction output returned by all EcoTrack models.

    Attributes:
        predictions: Raw model output as a NumPy array.
        confidence: Optional confidence / probability scores.
        uncertainty: Optional uncertainty estimates (e.g. from MC Dropout).
        metadata: Extra information attached to this prediction batch.
        inference_time_ms: Wall-clock inference time in milliseconds.
    """

    predictions: np.ndarray
    confidence: np.ndarray | None = None
    uncertainty: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    inference_time_ms: float = 0.0


class EcoTrackModel(nn.Module, abc.ABC):
    """Abstract base for all EcoTrack PyTorch models.

    Every concrete model inherits from this class, which provides:

    * A unified ``predict`` method with automatic timing and numpy conversion.
    * Parameter counting utilities.
    * ONNX export helpers.
    * Checkpoint save / load.
    """

    def __init__(self, metadata: ModelMetadata) -> None:
        super().__init__()
        self.metadata = metadata

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass — must be implemented by every sub-class."""
        ...

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    def predict(self, x: torch.Tensor) -> PredictionResult:
        """Run inference with timing and uncertainty.

        The model is set to ``eval()`` mode and gradients are disabled
        for the duration of the call.

        Args:
            x: Input tensor (should already be on the correct device).

        Returns:
            A :class:`PredictionResult` containing numpy predictions.
        """
        self.eval()
        start = time.perf_counter()
        with torch.no_grad():
            output = self.forward(x)
        elapsed = (time.perf_counter() - start) * 1000
        return PredictionResult(
            predictions=output.cpu().numpy(),
            inference_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def count_parameters(self) -> int:
        """Count trainable parameters and update metadata."""
        count = sum(p.numel() for p in self.parameters() if p.requires_grad)
        self.metadata.parameters_count = count
        return count

    def export_onnx(self, path: Path, dummy_input: torch.Tensor) -> Path:
        """Export model to ONNX format.

        Args:
            path: Destination ``.onnx`` file path.
            dummy_input: A representative input tensor for tracing.

        Returns:
            The path that was written to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.onnx.export(
            self,
            dummy_input,
            str(path),
            opset_version=17,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={
                "input": {0: "batch_size"},
                "output": {0: "batch_size"},
            },
        )
        return path

    def save_checkpoint(self, path: Path) -> Path:
        """Save model checkpoint (state dict + metadata).

        Args:
            path: Destination ``.pt`` checkpoint path.

        Returns:
            The path that was written to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": self.state_dict(),
                "metadata": self.metadata,
            },
            path,
        )
        return path

    @classmethod
    def load_checkpoint(cls, path: Path, **kwargs: Any) -> "EcoTrackModel":
        """Load model from a previously saved checkpoint.

        Args:
            path: Path to the ``.pt`` checkpoint file.
            **kwargs: Extra keyword arguments forwarded to the constructor.

        Returns:
            An initialised model with restored weights.
        """
        checkpoint = torch.load(path, map_location="cpu")
        model = cls(metadata=checkpoint["metadata"], **kwargs)
        model.load_state_dict(checkpoint["model_state_dict"])
        return model


__all__ = [
    "EcoTrackModel",
    "ModelMetadata",
    "ModelTask",
    "PredictionResult",
    "T_Input",
    "T_Output",
]
