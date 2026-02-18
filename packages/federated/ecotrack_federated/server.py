"""Federated learning server for coordinating distributed training."""
from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

import structlog

from ecotrack_federated.client import ClientUpdate, FederatedClient
from ecotrack_federated.strategies import AggregationStrategy

logger = structlog.get_logger(__name__)


@dataclass
class ServerConfig:
    """Configuration for the federated learning server.

    Attributes:
        num_rounds: Total number of federated training rounds.
        min_clients: Minimum number of clients required to start a round.
        fraction_fit: Fraction of registered clients to select for training
            each round (0.0–1.0).
        fraction_evaluate: Fraction of registered clients to select for
            evaluation each round (0.0–1.0).
        checkpoint_dir: Directory for saving model checkpoints.
    """

    num_rounds: int = 10
    min_clients: int = 2
    fraction_fit: float = 1.0
    fraction_evaluate: float = 1.0
    checkpoint_dir: Path | None = None


@dataclass
class RoundResult:
    """Result of a single federated training round.

    Attributes:
        round_number: 1-based round index.
        global_metrics: Metrics computed on the server's test set after
            aggregation (e.g. ``{"test_loss": 0.42}``).
        client_metrics: Per-client training metrics keyed by client ID.
        num_participating: Number of clients that participated.
    """

    round_number: int
    global_metrics: dict[str, float] = field(default_factory=dict)
    client_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    num_participating: int = 0


class FederatedServer:
    """Federated learning server that coordinates distributed training.

    The server maintains a *global model* and orchestrates training
    across a set of registered :class:`FederatedClient` instances.

    Each round proceeds as follows:

    1. **Select** a random subset of clients (controlled by
       ``fraction_fit``).
    2. **Distribute** the current global model to selected clients.
    3. **Collect** :class:`ClientUpdate` objects from each client
       after local training.
    4. **Aggregate** updates using the configured
       :class:`AggregationStrategy`.
    5. **Evaluate** the new global model on the server's test set
       (if provided).
    """

    def __init__(
        self,
        model: nn.Module,
        strategy: AggregationStrategy,
        config: ServerConfig | None = None,
    ) -> None:
        self.model = copy.deepcopy(model)
        self.strategy = strategy
        self.config = config or ServerConfig()
        self._clients: list[FederatedClient] = []
        self._round = 0
        self._history: list[RoundResult] = []

    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------

    def register_client(self, client: FederatedClient) -> None:
        """Register a client to participate in federated training.

        Args:
            client: The :class:`FederatedClient` instance to register.
        """
        self._clients.append(client)
        logger.info(
            "fl.server.client_registered",
            client_id=client.config.client_id,
            total_clients=len(self._clients),
        )

    @property
    def num_clients(self) -> int:
        """Return the number of registered clients."""
        return len(self._clients)

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------

    def run_round(self, criterion: nn.Module | None = None) -> RoundResult:
        """Execute a single federated training round.

        Args:
            criterion: Loss function forwarded to clients.  Defaults to
                :class:`~torch.nn.MSELoss`.

        Returns:
            A :class:`RoundResult` summarizing the round.

        Raises:
            RuntimeError: If fewer than ``min_clients`` are registered.
        """
        if len(self._clients) < self.config.min_clients:
            raise RuntimeError(
                f"Need at least {self.config.min_clients} clients, "
                f"but only {len(self._clients)} registered."
            )

        self._round += 1
        logger.info("fl.server.round_start", round=self._round)

        # 1. Select clients
        num_selected = max(
            self.config.min_clients,
            int(len(self._clients) * self.config.fraction_fit),
        )
        selected = random.sample(self._clients, min(num_selected, len(self._clients)))

        # 2. Distribute global model
        global_state = copy.deepcopy(self.model.state_dict())
        for client in selected:
            client.receive_global_model(global_state)

        # 3. Collect client updates
        updates: list[ClientUpdate] = []
        for client in selected:
            update = client.train_local(criterion=criterion)
            updates.append(update)

        # 4. Aggregate
        aggregated_state = self.strategy.aggregate(updates)
        self.model.load_state_dict(aggregated_state)

        # 5. Build result
        client_metrics: dict[str, dict[str, float]] = {
            u.client_id: u.metrics for u in updates
        }

        result = RoundResult(
            round_number=self._round,
            global_metrics={},
            client_metrics=client_metrics,
            num_participating=len(selected),
        )

        self._history.append(result)

        logger.info(
            "fl.server.round_complete",
            round=self._round,
            participants=len(selected),
        )

        return result

    def run_training(
        self,
        test_loader: DataLoader | None = None,
        criterion: nn.Module | None = None,
    ) -> list[RoundResult]:
        """Run the full federated training loop for ``num_rounds``.

        Args:
            test_loader: Optional server-side test set for evaluation
                after each round.
            criterion: Loss function forwarded to clients and used for
                server-side evaluation.

        Returns:
            List of :class:`RoundResult` for every round.
        """
        if criterion is None:
            criterion = nn.MSELoss()

        results: list[RoundResult] = []

        for _ in range(self.config.num_rounds):
            result = self.run_round(criterion=criterion)

            # Server-side evaluation
            if test_loader is not None:
                test_loss = self._evaluate(test_loader, criterion)
                result.global_metrics["test_loss"] = test_loss
                logger.info(
                    "fl.server.evaluation",
                    round=result.round_number,
                    test_loss=test_loss,
                )

            results.append(result)

        logger.info(
            "fl.server.training_complete",
            total_rounds=self.config.num_rounds,
        )
        return results

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def save_checkpoint(self, path: Path | str | None = None) -> Path:
        """Save the global model and training history to disk.

        Args:
            path: Destination file.  If *None*, uses
                ``checkpoint_dir/round_{N}.pt``.

        Returns:
            The path where the checkpoint was saved.
        """
        if path is None:
            base = self.config.checkpoint_dir or Path("checkpoints")
            base.mkdir(parents=True, exist_ok=True)
            path = base / f"round_{self._round}.pt"
        else:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            "round": self._round,
            "model_state_dict": self.model.state_dict(),
            "history": [
                {
                    "round_number": r.round_number,
                    "global_metrics": r.global_metrics,
                    "num_participating": r.num_participating,
                }
                for r in self._history
            ],
        }
        torch.save(checkpoint, path)
        logger.info("fl.server.checkpoint_saved", path=str(path), round=self._round)
        return path

    def load_checkpoint(self, path: Path | str) -> None:
        """Load a checkpoint from disk.

        Args:
            path: Path to the ``.pt`` checkpoint file.
        """
        path = Path(path)
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self._round = checkpoint.get("round", 0)
        logger.info("fl.server.checkpoint_loaded", path=str(path), round=self._round)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evaluate(self, test_loader: DataLoader, criterion: nn.Module) -> float:
        """Evaluate the global model on the server test set.

        Args:
            test_loader: Test data loader.
            criterion: Loss function.

        Returns:
            Average test loss.
        """
        self.model.eval()
        total_loss = 0.0
        total_samples = 0

        with torch.no_grad():
            for batch_x, batch_y in test_loader:
                output = self.model(batch_x)
                loss = criterion(output, batch_y)
                total_loss += loss.item() * batch_x.size(0)
                total_samples += batch_x.size(0)

        return total_loss / max(total_samples, 1)


__all__ = ["FederatedServer", "RoundResult", "ServerConfig"]
