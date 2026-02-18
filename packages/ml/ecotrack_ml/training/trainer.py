"""EcoTrack model training pipeline.

Provides :class:`EcoTrackTrainer`, a self-contained training loop with
early stopping, cosine-annealing LR schedule, gradient clipping, and
checkpoint management.  Inspired by PyTorch Lightning but dependency-free.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.optim import Optimizer
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Configuration & result data-classes
# ---------------------------------------------------------------------------


@dataclass
class TrainerConfig:
    """Configuration for :class:`EcoTrackTrainer`.

    Attributes:
        max_epochs: Maximum number of training epochs.
        batch_size: Mini-batch size (informational; actual batch comes from DataLoader).
        learning_rate: Base learning rate.
        weight_decay: L2 weight-decay coefficient.
        early_stopping_patience: Number of epochs without improvement
            before training stops.
        gradient_clip_norm: Maximum gradient norm for clipping (0 = disabled).
        log_interval: Log training metrics every *n* batches.
        checkpoint_dir: Directory where checkpoints are written.
        experiment_name: Human-readable experiment name.
    """

    max_epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    early_stopping_patience: int = 10
    gradient_clip_norm: float = 1.0
    log_interval: int = 50
    checkpoint_dir: Path = field(default_factory=lambda: Path("checkpoints"))
    experiment_name: str = "ecotrack_experiment"


@dataclass
class TrainingResult:
    """Aggregate training result returned by :meth:`EcoTrackTrainer.fit`.

    Attributes:
        train_losses: Per-epoch average training loss.
        val_losses: Per-epoch average validation loss.
        best_epoch: Epoch index with the best validation loss.
        best_metrics: Metrics recorded at *best_epoch*.
        training_time_s: Total wall-clock training time in seconds.
    """

    train_losses: list[float] = field(default_factory=list)
    val_losses: list[float] = field(default_factory=list)
    best_epoch: int = 0
    best_metrics: dict[str, float] = field(default_factory=dict)
    training_time_s: float = 0.0


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------


class EcoTrackTrainer:
    """Unified training loop for all EcoTrack models.

    Args:
        model: The :class:`~ecotrack_ml.models.base.EcoTrackModel` to train.
        optimizer: A PyTorch optimizer (created externally so callers
            can customise parameter groups).
        criterion: Loss function.
        device: Target device (e.g. ``torch.device("cuda")``).
        config: Training hyper-parameters.
    """

    def __init__(
        self,
        model: nn.Module,
        optimizer: Optimizer,
        criterion: nn.Module,
        device: torch.device | None = None,
        config: TrainerConfig | None = None,
    ) -> None:
        self.config = config or TrainerConfig()
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.optimizer = optimizer
        self.criterion = criterion
        self.scheduler = CosineAnnealingLR(optimizer, T_max=self.config.max_epochs)

        # State
        self._best_val_loss = float("inf")
        self._patience_counter = 0
        self._best_state: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader | None = None,
    ) -> TrainingResult:
        """Run the full training loop.

        Args:
            train_loader: Training data loader.
            val_loader: Optional validation data loader.  If provided,
                early stopping and best-model checkpointing are enabled.

        Returns:
            A :class:`TrainingResult` with loss curves and timing.
        """
        result = TrainingResult()
        start = time.perf_counter()

        for epoch in range(1, self.config.max_epochs + 1):
            train_loss = self._train_epoch(train_loader, epoch)
            result.train_losses.append(train_loss)

            val_loss: float | None = None
            if val_loader is not None:
                val_loss = self._validate_epoch(val_loader)
                result.val_losses.append(val_loss)

                # Early stopping
                if val_loss < self._best_val_loss:
                    self._best_val_loss = val_loss
                    self._patience_counter = 0
                    result.best_epoch = epoch
                    result.best_metrics = {"val_loss": val_loss, "train_loss": train_loss}
                    self._best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                    self._save_checkpoint(epoch, val_loss)
                else:
                    self._patience_counter += 1
                    if self._patience_counter >= self.config.early_stopping_patience:
                        logger.info(
                            "Early stopping triggered",
                            epoch=epoch,
                            patience=self.config.early_stopping_patience,
                        )
                        break

            self.scheduler.step()

            logger.info(
                "Epoch complete",
                epoch=epoch,
                train_loss=round(train_loss, 6),
                val_loss=round(val_loss, 6) if val_loss is not None else None,
                lr=round(self.scheduler.get_last_lr()[0], 8),
            )

        # Restore best model weights
        if self._best_state is not None:
            self.model.load_state_dict(self._best_state)

        result.training_time_s = time.perf_counter() - start
        return result

    def evaluate(self, test_loader: DataLoader) -> dict[str, float]:
        """Evaluate the model on a test set.

        Args:
            test_loader: Test data loader.

        Returns:
            Dictionary with ``"test_loss"`` and ``"n_samples"``.
        """
        self.model.eval()
        total_loss = 0.0
        n_batches = 0
        n_samples = 0

        with torch.no_grad():
            for batch in test_loader:
                inputs, targets = self._unpack_batch(batch)
                outputs = self.model(inputs)
                loss = self.criterion(outputs, targets)
                total_loss += loss.item()
                n_batches += 1
                n_samples += targets.size(0) if isinstance(targets, torch.Tensor) else 1

        avg_loss = total_loss / max(n_batches, 1)
        return {"test_loss": avg_loss, "n_samples": n_samples}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _train_epoch(self, loader: DataLoader, epoch: int) -> float:
        """Run one training epoch."""
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        for batch_idx, batch in enumerate(loader):
            inputs, targets = self._unpack_batch(batch)

            self.optimizer.zero_grad()
            outputs = self.model(inputs)
            loss = self.criterion(outputs, targets)
            loss.backward()

            # Gradient clipping
            if self.config.gradient_clip_norm > 0:
                nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.gradient_clip_norm,
                )

            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

            if self.config.log_interval > 0 and (batch_idx + 1) % self.config.log_interval == 0:
                logger.debug(
                    "Training batch",
                    epoch=epoch,
                    batch=batch_idx + 1,
                    loss=round(loss.item(), 6),
                )

        return total_loss / max(n_batches, 1)

    def _validate_epoch(self, loader: DataLoader) -> float:
        """Run one validation epoch."""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        with torch.no_grad():
            for batch in loader:
                inputs, targets = self._unpack_batch(batch)
                outputs = self.model(inputs)
                loss = self.criterion(outputs, targets)
                total_loss += loss.item()
                n_batches += 1

        return total_loss / max(n_batches, 1)

    def _unpack_batch(
        self, batch: Any
    ) -> tuple[torch.Tensor | dict[str, torch.Tensor], torch.Tensor]:
        """Move batch data to device.

        Supports both ``(input, target)`` tuples and dictionaries.
        """
        if isinstance(batch, (list, tuple)) and len(batch) == 2:
            inputs, targets = batch
            if isinstance(inputs, dict):
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            else:
                inputs = inputs.to(self.device)
            targets = targets.to(self.device)
            return inputs, targets
        raise ValueError(
            f"Unsupported batch format: expected (inputs, targets) tuple, got {type(batch)}"
        )

    def _save_checkpoint(self, epoch: int, val_loss: float) -> None:
        """Save model checkpoint for the best epoch so far."""
        ckpt_dir = self.config.checkpoint_dir / self.config.experiment_name
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        path = ckpt_dir / f"best_epoch{epoch}_loss{val_loss:.4f}.pt"
        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "val_loss": val_loss,
            },
            path,
        )
        logger.info("Checkpoint saved", path=str(path))


__all__ = ["EcoTrackTrainer", "TrainerConfig", "TrainingResult"]
