"""EcoTrack Causal — Causal inference for environmental analysis."""
from __future__ import annotations

__version__ = "0.1.0"

from .discovery import (
    CausalDiscovery,
    CausalEdge,
    CausalGraph,
    DiscoveryAlgorithm,
)
from .inference import CausalInference, TreatmentEffect
from .counterfactual import (
    CounterfactualAnalyzer,
    CounterfactualResult,
    CounterfactualScenario,
)
from .environmental import (
    ClimateImpactModel,
    DeforestationImpactModel,
    PollutionHealthModel,
)

__all__ = [
    "__version__",
    # Discovery
    "DiscoveryAlgorithm",
    "CausalEdge",
    "CausalGraph",
    "CausalDiscovery",
    # Inference
    "TreatmentEffect",
    "CausalInference",
    # Counterfactual
    "CounterfactualScenario",
    "CounterfactualResult",
    "CounterfactualAnalyzer",
    # Environmental models
    "ClimateImpactModel",
    "DeforestationImpactModel",
    "PollutionHealthModel",
]
