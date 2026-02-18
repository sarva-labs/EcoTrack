"""Federated aggregation strategies for environmental models.

Provides pluggable aggregation algorithms used by
:class:`~ecotrack_federated.server.FederatedServer` to combine client
updates into a new global model.

Implemented strategies
----------------------

* :class:`FedAvg` — Weighted average (McMahan et al., 2017)
* :class:`FedProx` — FedAvg + proximal regularisation (Li et al., 2020)
* :class:`FedMedian` — Coordinate-wise median (Yin et al., 2018)
* :class:`FedTrimmedMean` — Trimmed-mean aggregation (Yin et al., 2018)
"""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections import OrderedDict

import torch

from ecotrack_federated.client import ClientUpdate


# ──────────────────────────────────────────────────────────────────────
#  Abstract base
# ──────────────────────────────────────────────────────────────────────


class AggregationStrategy(ABC):
    """Abstract base class for federated aggregation strategies."""

    @abstractmethod
    def aggregate(
        self, updates: list[ClientUpdate]
    ) -> dict[str, torch.Tensor]:
        """Aggregate client updates into a single global state dict.

        Args:
            updates: List of :class:`ClientUpdate` objects from
                participating clients.

        Returns:
            Aggregated model state dict.
        """
        ...


# ──────────────────────────────────────────────────────────────────────
#  FedAvg — Weighted averaging
# ──────────────────────────────────────────────────────────────────────


class FedAvg(AggregationStrategy):
    """Federated Averaging (McMahan et al., 2017).

    Computes a *weighted* average of client model parameters where
    each client is weighted proportionally to its number of local
    training samples::

        θ_global = Σ_k (n_k / N) · θ_k

    where ``n_k`` is ``ClientUpdate.num_samples`` and ``N = Σ n_k``.
    """

    def aggregate(
        self, updates: list[ClientUpdate]
    ) -> dict[str, torch.Tensor]:
        """Weighted average aggregation.

        Args:
            updates: Client updates with ``model_state`` and
                ``num_samples``.

        Returns:
            Aggregated state dict.

        Raises:
            ValueError: If *updates* is empty.
        """
        if not updates:
            raise ValueError("Cannot aggregate zero updates.")

        total_samples = sum(u.num_samples for u in updates)
        if total_samples == 0:
            total_samples = len(updates)  # fall back to equal weight

        keys = list(updates[0].model_state.keys())
        aggregated: dict[str, torch.Tensor] = {}

        for key in keys:
            aggregated[key] = torch.zeros_like(updates[0].model_state[key], dtype=torch.float32)
            for update in updates:
                weight = update.num_samples / total_samples
                aggregated[key] += weight * update.model_state[key].float()

        return aggregated


# ──────────────────────────────────────────────────────────────────────
#  FedProx — Proximal-term variant
# ──────────────────────────────────────────────────────────────────────


class FedProx(AggregationStrategy):
    """FedProx aggregation (Li et al., 2020).

    Identical to :class:`FedAvg` at the *aggregation* step — the
    proximal term (``μ/2 ‖w − w_global‖²``) is applied during *local
    training* on each client.  The ``mu`` parameter is exposed here so
    that the server can instruct clients to use it.

    This implementation performs FedAvg-style weighted averaging and
    stores ``mu`` for clients to query.

    Args:
        mu: Proximal term coefficient.  Larger values keep local
            models closer to the global model.
    """

    def __init__(self, mu: float = 0.01) -> None:
        self.mu = mu

    def aggregate(
        self, updates: list[ClientUpdate]
    ) -> dict[str, torch.Tensor]:
        """Weighted average aggregation (same as FedAvg).

        The proximal penalty is enforced client-side during local SGD.

        Args:
            updates: Client updates.

        Returns:
            Aggregated state dict.
        """
        if not updates:
            raise ValueError("Cannot aggregate zero updates.")

        total_samples = sum(u.num_samples for u in updates)
        if total_samples == 0:
            total_samples = len(updates)

        keys = list(updates[0].model_state.keys())
        aggregated: dict[str, torch.Tensor] = {}

        for key in keys:
            aggregated[key] = torch.zeros_like(updates[0].model_state[key], dtype=torch.float32)
            for update in updates:
                weight = update.num_samples / total_samples
                aggregated[key] += weight * update.model_state[key].float()

        return aggregated


# ──────────────────────────────────────────────────────────────────────
#  FedMedian — Byzantine-robust coordinate-wise median
# ──────────────────────────────────────────────────────────────────────


class FedMedian(AggregationStrategy):
    """Coordinate-wise median aggregation (Yin et al., 2018).

    For each parameter tensor, the aggregated value at every coordinate
    is the *median* across all client updates.  This is robust to up to
    ``(n-1)/2`` Byzantine (malicious) clients.
    """

    def aggregate(
        self, updates: list[ClientUpdate]
    ) -> dict[str, torch.Tensor]:
        """Coordinate-wise median aggregation.

        Args:
            updates: Client updates.

        Returns:
            Aggregated state dict where each parameter is the
            element-wise median across clients.

        Raises:
            ValueError: If *updates* is empty.
        """
        if not updates:
            raise ValueError("Cannot aggregate zero updates.")

        keys = list(updates[0].model_state.keys())
        aggregated: dict[str, torch.Tensor] = {}

        for key in keys:
            # Stack all client tensors for this parameter: shape (num_clients, *param_shape)
            stacked = torch.stack(
                [u.model_state[key].float() for u in updates], dim=0
            )
            aggregated[key] = torch.median(stacked, dim=0).values

        return aggregated


# ──────────────────────────────────────────────────────────────────────
#  FedTrimmedMean — Robust trimmed-mean aggregation
# ──────────────────────────────────────────────────────────────────────


class FedTrimmedMean(AggregationStrategy):
    """Trimmed-mean aggregation (Yin et al., 2018).

    For each coordinate, the top and bottom ``trim_fraction`` of client
    values are discarded and the remaining values are averaged.  This
    provides robustness against up to ``trim_fraction`` fraction of
    Byzantine clients.

    Args:
        trim_fraction: Fraction of values to trim from each end.
            Must be in ``[0, 0.5)``.  For example, ``0.1`` trims the
            lowest 10% and highest 10%.
    """

    def __init__(self, trim_fraction: float = 0.1) -> None:
        if not (0.0 <= trim_fraction < 0.5):
            raise ValueError("trim_fraction must be in [0, 0.5)")
        self.trim_fraction = trim_fraction

    def aggregate(
        self, updates: list[ClientUpdate]
    ) -> dict[str, torch.Tensor]:
        """Trimmed-mean aggregation.

        Args:
            updates: Client updates.

        Returns:
            Aggregated state dict.

        Raises:
            ValueError: If *updates* is empty.
        """
        if not updates:
            raise ValueError("Cannot aggregate zero updates.")

        n = len(updates)
        k = int(n * self.trim_fraction)  # number to trim from each end

        keys = list(updates[0].model_state.keys())
        aggregated: dict[str, torch.Tensor] = {}

        for key in keys:
            stacked = torch.stack(
                [u.model_state[key].float() for u in updates], dim=0
            )
            # Sort along the client dimension (dim=0)
            sorted_vals, _ = torch.sort(stacked, dim=0)

            if k > 0 and n > 2 * k:
                # Trim k from each end
                trimmed = sorted_vals[k : n - k]
            else:
                trimmed = sorted_vals

            aggregated[key] = trimmed.mean(dim=0)

        return aggregated


__all__ = [
    "AggregationStrategy",
    "FedAvg",
    "FedMedian",
    "FedProx",
    "FedTrimmedMean",
]
