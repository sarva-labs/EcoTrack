"""Unified model evaluation pipeline.

Provides :class:`ModelEvaluator` which runs a model on a test set,
computes domain-appropriate metrics, and optionally performs Monte-Carlo
Dropout uncertainty estimation and calibration analysis.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ecotrack_ml.evaluation.metrics import (
    ClassificationMetrics,
    ForecastMetrics,
    RegressionMetrics,
    SegmentationMetrics,
)
from ecotrack_ml.models.base import ModelTask

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]


@dataclass
class EvaluationReport:
    """Result of :meth:`ModelEvaluator.evaluate`.

    Attributes:
        metrics: Dictionary of computed metric values.
        predictions: All model predictions concatenated.
        ground_truth: All ground truth values concatenated.
        uncertainty_estimates: Per-sample uncertainty (if MC Dropout used).
        calibration_data: Binned reliability-diagram data (if computed).
    """

    metrics: dict[str, Any] = field(default_factory=dict)
    predictions: np.ndarray | None = None
    ground_truth: np.ndarray | None = None
    uncertainty_estimates: np.ndarray | None = None
    calibration_data: dict[str, Any] | None = None


class ModelEvaluator:
    """Evaluate EcoTrack models on test sets.

    Args:
        device: Torch device for inference.  Auto-detected when ``None``.
    """

    def __init__(self, device: torch.device | None = None) -> None:
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        model: nn.Module,
        dataloader: DataLoader,
        task_type: ModelTask | str,
        *,
        mc_dropout_samples: int = 0,
        n_classes: int | None = None,
    ) -> EvaluationReport:
        """Evaluate *model* on *dataloader*.

        Args:
            model: A trained :class:`~ecotrack_ml.models.base.EcoTrackModel`.
            dataloader: Test data loader yielding ``(inputs, targets)``
                batches.
            task_type: ML task type that determines which metrics to compute.
            mc_dropout_samples: If > 0, run MC Dropout for uncertainty
                estimation (keeps dropout active for *n* forward passes).
            n_classes: Number of classes (required for segmentation /
                classification metrics).

        Returns:
            :class:`EvaluationReport` with metrics and raw predictions.
        """
        task_type = ModelTask(task_type) if isinstance(task_type, str) else task_type
        model = model.to(self.device)

        # Collect predictions
        all_preds, all_targets = self._collect_predictions(model, dataloader)

        report = EvaluationReport(
            predictions=all_preds,
            ground_truth=all_targets,
        )

        # Uncertainty via MC Dropout
        if mc_dropout_samples > 0:
            report.uncertainty_estimates = self._mc_dropout_uncertainty(
                model, dataloader, mc_dropout_samples
            )

        # Compute metrics based on task
        report.metrics = self._compute_metrics(
            task_type, all_targets, all_preds, n_classes=n_classes
        )

        logger.info(
            "Evaluation complete",
            task=task_type.value,
            n_samples=len(all_targets),
            metrics={k: round(v, 4) if isinstance(v, float) else v for k, v in report.metrics.items()},
        )
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_predictions(
        self, model: nn.Module, dataloader: DataLoader
    ) -> tuple[np.ndarray, np.ndarray]:
        """Run the model in eval mode and collect all outputs."""
        model.eval()
        preds_list: list[np.ndarray] = []
        targets_list: list[np.ndarray] = []

        with torch.no_grad():
            for batch in dataloader:
                inputs, targets = self._unpack_batch(batch)
                outputs = model(inputs)
                preds_list.append(outputs.cpu().numpy())
                targets_list.append(
                    targets.cpu().numpy() if isinstance(targets, torch.Tensor) else np.array(targets)
                )

        return np.concatenate(preds_list, axis=0), np.concatenate(targets_list, axis=0)

    def _mc_dropout_uncertainty(
        self,
        model: nn.Module,
        dataloader: DataLoader,
        n_samples: int,
    ) -> np.ndarray:
        """Estimate uncertainty via Monte-Carlo Dropout.

        Enables dropout at test time and runs *n_samples* forward passes
        per batch, then computes per-sample standard deviation.
        """
        # Enable dropout
        _enable_dropout(model)

        all_stds: list[np.ndarray] = []
        with torch.no_grad():
            for batch in dataloader:
                inputs, _ = self._unpack_batch(batch)
                samples = []
                for _ in range(n_samples):
                    out = model(inputs)
                    samples.append(out.cpu().numpy())
                stacked = np.stack(samples, axis=0)  # (n_samples, batch, ...)
                std = np.std(stacked, axis=0)
                all_stds.append(std)

        model.eval()  # restore eval mode
        return np.concatenate(all_stds, axis=0)

    def _compute_metrics(
        self,
        task_type: ModelTask,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        *,
        n_classes: int | None = None,
    ) -> dict[str, Any]:
        """Route to the correct metric class."""
        if task_type == ModelTask.REGRESSION:
            return RegressionMetrics(y_true, y_pred).compute_all()

        if task_type == ModelTask.CLASSIFICATION:
            # Assume logits → argmax
            if y_pred.ndim > 1 and y_pred.shape[-1] > 1:
                y_pred_cls = np.argmax(y_pred, axis=-1)
            else:
                y_pred_cls = y_pred.ravel()
            return ClassificationMetrics(y_true, y_pred_cls, n_classes).compute_all()

        if task_type == ModelTask.SEGMENTATION:
            if y_pred.ndim > 3:
                # (B, C, H, W) → argmax along class axis
                y_pred_seg = np.argmax(y_pred, axis=1)
            else:
                y_pred_seg = y_pred
            nc = n_classes or 10
            return SegmentationMetrics(y_true, y_pred_seg, nc).compute_all()

        if task_type == ModelTask.FORECASTING:
            return ForecastMetrics(y_true, y_pred).compute_all()

        if task_type == ModelTask.ANOMALY_DETECTION:
            # Anomaly detection uses reconstruction error as a regression proxy
            return RegressionMetrics(y_true, y_pred).compute_all()

        return RegressionMetrics(y_true, y_pred).compute_all()

    def _unpack_batch(
        self, batch: Any
    ) -> tuple[torch.Tensor | dict[str, torch.Tensor], torch.Tensor]:
        """Move batch tensors to the evaluation device."""
        if isinstance(batch, (list, tuple)) and len(batch) == 2:
            inputs, targets = batch
            if isinstance(inputs, dict):
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            else:
                inputs = inputs.to(self.device)
            targets = targets.to(self.device)
            return inputs, targets
        raise ValueError(f"Unsupported batch format: {type(batch)}")


def _enable_dropout(model: nn.Module) -> None:
    """Set all Dropout layers to training mode for MC Dropout."""
    for m in model.modules():
        if isinstance(m, (nn.Dropout, nn.Dropout2d, nn.Dropout3d)):
            m.train()


__all__ = ["EvaluationReport", "ModelEvaluator"]
