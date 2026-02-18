"""Ensemble methods for improved predictions.

Provides :class:`EnsemblePredictor` supporting weighted-averaging and
stacking ensemble strategies with automatic uncertainty estimation from
model disagreement.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import torch
import torch.nn as nn

from ecotrack_ml.models.base import PredictionResult

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]


@dataclass
class _ModelEntry:
    """Internal model entry in the ensemble."""

    model: nn.Module
    weight: float = 1.0


class EnsemblePredictor:
    """Ensemble predictor combining multiple models.

    Supports two ensemble strategies:

    * **weighted** — Weighted average of individual predictions.
    * **stacking** — A lightweight meta-learner trained on base model
      outputs.  The meta-learner is a simple linear layer registered when
      :meth:`fit_stacking` is called.

    Uncertainty is automatically estimated as the weighted standard
    deviation across member predictions.

    Args:
        strategy: Ensemble combination strategy.
        device: Torch device.  Auto-detected when ``None``.
    """

    def __init__(
        self,
        strategy: Literal["weighted", "stacking"] = "weighted",
        device: torch.device | None = None,
    ) -> None:
        self.strategy = strategy
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._models: list[_ModelEntry] = []
        self._meta_learner: nn.Module | None = None

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def add_model(self, model: nn.Module, weight: float = 1.0) -> None:
        """Add a model to the ensemble.

        Args:
            model: A trained model (will be moved to the ensemble device).
            weight: Relative weight for weighted averaging.
        """
        model = model.to(self.device).eval()
        self._models.append(_ModelEntry(model=model, weight=weight))
        logger.info("Model added to ensemble", n_models=len(self._models), weight=weight)

    @property
    def n_models(self) -> int:
        """Number of models in the ensemble."""
        return len(self._models)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, inputs: torch.Tensor | np.ndarray) -> PredictionResult:
        """Run ensemble inference.

        Args:
            inputs: Input tensor or array.

        Returns:
            :class:`PredictionResult` with ensemble prediction and
            uncertainty from model disagreement.
        """
        if not self._models:
            raise RuntimeError("No models in the ensemble. Use add_model() first.")

        tensor = self._to_tensor(inputs).to(self.device)
        start = time.perf_counter()

        member_preds = self._get_member_predictions(tensor)

        if self.strategy == "stacking" and self._meta_learner is not None:
            combined = self._stacking_combine(member_preds)
        else:
            combined = self._weighted_combine(member_preds)

        elapsed = (time.perf_counter() - start) * 1000

        # Uncertainty = weighted std across members
        uncertainty = self._compute_uncertainty(member_preds)

        return PredictionResult(
            predictions=combined,
            uncertainty=uncertainty,
            inference_time_ms=elapsed,
            metadata={
                "n_models": len(self._models),
                "strategy": self.strategy,
            },
        )

    # ------------------------------------------------------------------
    # Stacking
    # ------------------------------------------------------------------

    def fit_stacking(
        self,
        inputs: torch.Tensor,
        targets: torch.Tensor,
        epochs: int = 50,
        lr: float = 1e-3,
    ) -> None:
        """Train a stacking meta-learner on base model outputs.

        Args:
            inputs: Training inputs.
            targets: Training targets.
            epochs: Meta-learner training epochs.
            lr: Learning rate.
        """
        if not self._models:
            raise RuntimeError("Add base models before fitting the stacking layer.")

        inputs = inputs.to(self.device)
        targets = targets.to(self.device)

        member_preds = self._get_member_predictions(inputs)
        # Stack member predictions as features: (N, n_models * out_dim)
        stacked = np.concatenate(
            [p.reshape(p.shape[0], -1) for p in member_preds], axis=1
        )
        stacked_tensor = torch.from_numpy(stacked).float().to(self.device)

        in_dim = stacked_tensor.shape[1]
        out_dim = int(np.prod(targets.shape[1:])) if targets.ndim > 1 else 1

        self._meta_learner = nn.Linear(in_dim, out_dim).to(self.device)
        optimizer = torch.optim.Adam(self._meta_learner.parameters(), lr=lr)
        criterion = nn.MSELoss()

        target_flat = targets.view(targets.size(0), -1).float()
        self._meta_learner.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            pred = self._meta_learner(stacked_tensor)
            loss = criterion(pred, target_flat)
            loss.backward()
            optimizer.step()

        self._meta_learner.eval()
        logger.info("Stacking meta-learner trained", epochs=epochs, final_loss=loss.item())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_member_predictions(self, tensor: torch.Tensor) -> list[np.ndarray]:
        """Run each member model and return a list of numpy predictions."""
        preds: list[np.ndarray] = []
        for entry in self._models:
            entry.model.eval()
            with torch.no_grad():
                out = entry.model(tensor)
            preds.append(out.cpu().numpy())
        return preds

    def _weighted_combine(self, member_preds: list[np.ndarray]) -> np.ndarray:
        """Compute weighted average of member predictions."""
        weights = np.array([e.weight for e in self._models])
        weights = weights / weights.sum()

        combined = np.zeros_like(member_preds[0])
        for w, pred in zip(weights, member_preds):
            combined += w * pred
        return combined

    def _stacking_combine(self, member_preds: list[np.ndarray]) -> np.ndarray:
        """Combine via stacking meta-learner."""
        assert self._meta_learner is not None
        stacked = np.concatenate(
            [p.reshape(p.shape[0], -1) for p in member_preds], axis=1
        )
        stacked_tensor = torch.from_numpy(stacked).float().to(self.device)
        with torch.no_grad():
            out = self._meta_learner(stacked_tensor)
        return out.cpu().numpy()

    def _compute_uncertainty(self, member_preds: list[np.ndarray]) -> np.ndarray:
        """Compute weighted standard deviation across member predictions."""
        weights = np.array([e.weight for e in self._models])
        weights = weights / weights.sum()

        stacked = np.stack(member_preds, axis=0)  # (n_models, N, ...)
        mean = np.average(stacked, axis=0, weights=weights)

        # Weighted variance
        variance = np.average((stacked - mean[np.newaxis]) ** 2, axis=0, weights=weights)
        return np.sqrt(variance)

    def _to_tensor(self, inputs: np.ndarray | torch.Tensor) -> torch.Tensor:
        if isinstance(inputs, np.ndarray):
            return torch.from_numpy(inputs).float()
        return inputs.float()


__all__ = ["EnsemblePredictor"]
