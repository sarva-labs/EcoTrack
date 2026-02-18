"""EcoTrack Federated — Privacy-preserving federated learning.

This package provides a complete federated learning infrastructure
for distributed environmental model training across regional nodes.

Core components
---------------

* :class:`FederatedClient` — Local training client with optional
  differential privacy.
* :class:`FederatedServer` — Central coordinator for multi-round FL.
* Aggregation strategies: :class:`FedAvg`, :class:`FedProx`,
  :class:`FedMedian`, :class:`FedTrimmedMean`.
* :class:`PrivacyAccountant` — RDP-based cumulative privacy tracking.
* :class:`SecureAggregation` — Additive-masking demonstration.
"""
from __future__ import annotations

__version__ = "0.1.0"

from ecotrack_federated.client import ClientConfig, ClientUpdate, FederatedClient
from ecotrack_federated.privacy import (
    PrivacyAccountant,
    PrivacyBudgetExhausted,
    SecureAggregation,
)
from ecotrack_federated.server import FederatedServer, RoundResult, ServerConfig
from ecotrack_federated.strategies import (
    AggregationStrategy,
    FedAvg,
    FedMedian,
    FedProx,
    FedTrimmedMean,
)

__all__ = [
    "__version__",
    # Client
    "ClientConfig",
    "ClientUpdate",
    "FederatedClient",
    # Server
    "FederatedServer",
    "RoundResult",
    "ServerConfig",
    # Strategies
    "AggregationStrategy",
    "FedAvg",
    "FedMedian",
    "FedProx",
    "FedTrimmedMean",
    # Privacy
    "PrivacyAccountant",
    "PrivacyBudgetExhausted",
    "SecureAggregation",
]
