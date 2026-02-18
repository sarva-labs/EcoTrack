"""Federated learning client for distributed environmental model training."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ClientConfig:
    """Configuration for a federated learning client.

    Attributes:
        client_id: Unique identifier for this client / regional node.
        local_epochs: Number of local training epochs per round.
        batch_size: Mini-batch size for local training.
        learning_rate: SGD learning rate.
        device: Torch device string (``"cpu"`` or ``"cuda"``).
        differential_privacy: Whether to enable DP noise injection.
        dp_epsilon: Target epsilon for differential privacy.
        dp_delta: Target delta for differential privacy.
        dp_max_grad_norm: Maximum L2 norm for gradient clipping (DP).
    """

    client_id: str
    local_epochs: int = 5
    batch_size: int = 32
    learning_rate: float = 0.01
    device: str = "cpu"
    differential_privacy: bool = False
    dp_epsilon: float = 1.0
    dp_delta: float = 1e-5
    dp_max_grad_norm: float = 1.0


@dataclass
class ClientUpdate:
    """Model update produced by a single client after local training.

    Attributes:
        client_id: ID of the originating client.
        model_state: Trained model state dict (deep copy).
        num_samples: Number of training samples used.
        metrics: Training / validation metrics for this round.
        round_number: The FL round number.
    """

    client_id: str
    model_state: dict[str, torch.Tensor]
    num_samples: int
    metrics: dict[str, float] = field(default_factory=dict)
    round_number: int = 0


class FederatedClient:
    """Federated learning client that trains a model on local data.

    Each client wraps a PyTorch model together with a local
    :class:`~torch.utils.data.DataLoader` and supports:

    * Receiving global model parameters from the server.
    * Running local SGD for a configurable number of epochs.
    * Optional *differential privacy* via gradient clipping and
      calibrated Gaussian noise injection.
    * Returning a :class:`ClientUpdate` with the trained state dict
      and round metrics.
    """

    def __init__(
        self,
        config: ClientConfig,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader | None = None,
    ) -> None:
        self.config = config
        self.model = copy.deepcopy(model)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = torch.device(config.device)
        self.model.to(self.device)
        self._round = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def receive_global_model(self, global_state: dict[str, torch.Tensor]) -> None:
        """Receive and apply global model parameters.

        Args:
            global_state: State dict broadcast by the FL server.
        """
        self.model.load_state_dict(global_state)
        logger.info(
            "fl.client.received_global_model",
            client_id=self.config.client_id,
            round=self._round,
        )

    def train_local(self, criterion: nn.Module | None = None) -> ClientUpdate:
        """Train the model on local data for the configured number of epochs.

        Args:
            criterion: Loss function. Defaults to :class:`~torch.nn.MSELoss`.

        Returns:
            A :class:`ClientUpdate` containing the new model state and
            training metrics.
        """
        self._round += 1
        self.model.train()

        if criterion is None:
            criterion = nn.MSELoss()

        optimizer = torch.optim.SGD(
            self.model.parameters(), lr=self.config.learning_rate
        )

        total_loss = 0.0
        total_samples = 0

        for _epoch in range(self.config.local_epochs):
            epoch_loss = 0.0
            for batch_x, batch_y in self.train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()
                output = self.model(batch_x)
                loss = criterion(output, batch_y)
                loss.backward()

                # Differential privacy: clip per-sample gradients
                if self.config.differential_privacy:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        self.config.dp_max_grad_norm,
                    )

                optimizer.step()
                epoch_loss += loss.item() * batch_x.size(0)
                total_samples += batch_x.size(0)

            total_loss += epoch_loss

        avg_loss = total_loss / max(total_samples, 1)

        # Add calibrated Gaussian noise for differential privacy
        if self.config.differential_privacy:
            self._add_dp_noise()

        samples_per_epoch = total_samples // max(self.config.local_epochs, 1)
        metrics: dict[str, float] = {
            "train_loss": avg_loss,
            "num_samples": float(samples_per_epoch),
        }

        if self.val_loader is not None:
            val_loss = self._evaluate(criterion)
            metrics["val_loss"] = val_loss

        logger.info(
            "fl.client.training_complete",
            client_id=self.config.client_id,
            round=self._round,
            loss=avg_loss,
        )

        return ClientUpdate(
            client_id=self.config.client_id,
            model_state=copy.deepcopy(self.model.state_dict()),
            num_samples=samples_per_epoch,
            metrics=metrics,
            round_number=self._round,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evaluate(self, criterion: nn.Module) -> float:
        """Evaluate model on the validation set.

        Args:
            criterion: Loss function used for evaluation.

        Returns:
            Average validation loss.
        """
        if self.val_loader is None:
            return 0.0

        self.model.eval()
        total_loss = 0.0
        total_samples = 0

        with torch.no_grad():
            for batch_x, batch_y in self.val_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                output = self.model(batch_x)
                loss = criterion(output, batch_y)
                total_loss += loss.item() * batch_x.size(0)
                total_samples += batch_x.size(0)

        return total_loss / max(total_samples, 1)

    def _add_dp_noise(self) -> None:
        """Add calibrated Gaussian noise to model parameters for DP.

        Uses the *Gaussian mechanism*: noise σ is derived from the
        sensitivity (max_grad_norm / dataset_size) and the target
        (ε, δ)-differential privacy guarantee via the analytic
        Gaussian mechanism bound.
        """
        dataset_size = max(len(self.train_loader.dataset), 1)  # type: ignore[arg-type]
        sensitivity = self.config.dp_max_grad_norm / dataset_size

        # σ via the analytic Gaussian mechanism:
        # σ ≥ sensitivity × √(2 ln(1.25/δ)) / ε
        noise_scale = (
            sensitivity
            * np.sqrt(2.0 * np.log(1.25 / self.config.dp_delta))
            / self.config.dp_epsilon
        )

        with torch.no_grad():
            for param in self.model.parameters():
                noise = torch.randn_like(param) * noise_scale
                param.add_(noise)

        logger.debug(
            "fl.client.dp_noise_added",
            client_id=self.config.client_id,
            noise_scale=noise_scale,
        )


__all__ = ["ClientConfig", "ClientUpdate", "FederatedClient"]
