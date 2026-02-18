"""Reward shaping utilities for environmental RL.

Provides composable reward components that encode equity, sustainability,
threshold constraints, and multi-objective trade-offs into reward signals
for EcoTrack RL environments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class EquityReward:
    """Compute equity-aware rewards using the Gini coefficient.

    Penalises unequal resource distributions so that the RL agent
    learns to allocate resources fairly across stakeholders.

    The reward is:

    .. math::

        r_{\\text{equity}} = w \\cdot (1 - G(\\mathbf{x}))

    where *G* is the Gini coefficient and *w* is the weight.
    """

    def __init__(self, weight: float = 1.0) -> None:
        """Initialise the equity reward.

        Args:
            weight: Multiplicative weight for this reward component.
        """
        self.weight = weight

    def compute(self, allocations: np.ndarray) -> float:
        """Compute the equity reward.

        Args:
            allocations: 1-D array of allocations (one per stakeholder).

        Returns:
            Weighted equity reward (higher = more equitable).
        """
        gini = self._gini(allocations)
        return self.weight * (1.0 - gini)

    @staticmethod
    def _gini(values: np.ndarray) -> float:
        """Compute Gini coefficient.

        .. math::

            G = \\frac{\\sum_i \\sum_j |x_i - x_j|}{2 n \\sum_i x_i}

        Args:
            values: 1-D non-negative array.

        Returns:
            Gini coefficient in [0, 1].
        """
        arr = np.asarray(values, dtype=np.float64).flatten()
        total = arr.sum()
        if total == 0:
            return 0.0
        n = len(arr)
        diff_sum = float(np.sum(np.abs(arr[:, None] - arr[None, :])))
        return diff_sum / (2 * n * total)


class SustainabilityReward:
    """Multi-objective reward balancing economic, environmental, and social outcomes.

    Computes a weighted sum of three normalised objective scores:

    .. math::

        r = w_e \\cdot S_{\\text{econ}} + w_n \\cdot S_{\\text{env}} + w_s \\cdot S_{\\text{social}}

    Each score should be provided in [0, 1] (higher = better).
    """

    def __init__(
        self,
        economic_weight: float = 0.33,
        environmental_weight: float = 0.34,
        social_weight: float = 0.33,
    ) -> None:
        """Initialise the sustainability reward.

        Args:
            economic_weight: Weight for the economic objective.
            environmental_weight: Weight for the environmental objective.
            social_weight: Weight for the social objective.
        """
        total = economic_weight + environmental_weight + social_weight
        self.economic_weight = economic_weight / total
        self.environmental_weight = environmental_weight / total
        self.social_weight = social_weight / total

    def compute(
        self,
        economic_score: float,
        environmental_score: float,
        social_score: float,
    ) -> float:
        """Compute the multi-objective sustainability reward.

        Args:
            economic_score: Economic performance score in [0, 1].
            environmental_score: Environmental health score in [0, 1].
            social_score: Social well-being score in [0, 1].

        Returns:
            Weighted composite reward.
        """
        return (
            self.economic_weight * np.clip(economic_score, 0.0, 1.0)
            + self.environmental_weight * np.clip(environmental_score, 0.0, 1.0)
            + self.social_weight * np.clip(social_score, 0.0, 1.0)
        )


class ThresholdPenalty:
    """Penalty for violating environmental thresholds.

    Applies a smooth penalty when a value crosses a defined threshold:

    .. math::

        p = w \\cdot \\max(0, \\text{value} - \\text{threshold})^{\\alpha}

    for upper thresholds, or

    .. math::

        p = w \\cdot \\max(0, \\text{threshold} - \\text{value})^{\\alpha}

    for lower thresholds.

    The exponent α controls penalty curvature (1 = linear, 2 = quadratic).
    """

    def __init__(
        self,
        threshold: float,
        weight: float = 1.0,
        direction: str = "upper",
        exponent: float = 1.0,
    ) -> None:
        """Initialise the threshold penalty.

        Args:
            threshold: The threshold value.
            weight: Multiplicative penalty weight.
            direction: ``"upper"`` penalises values **above** threshold;
                       ``"lower"`` penalises values **below** threshold.
            exponent: Penalty curvature (1 = linear, 2 = quadratic).

        Raises:
            ValueError: If *direction* is not ``"upper"`` or ``"lower"``.
        """
        if direction not in ("upper", "lower"):
            raise ValueError(f"direction must be 'upper' or 'lower', got {direction!r}")
        self.threshold = threshold
        self.weight = weight
        self.direction = direction
        self.exponent = exponent

    def compute(self, value: float) -> float:
        """Compute the penalty for a given value.

        Args:
            value: The observed value to check against the threshold.

        Returns:
            Non-negative penalty (0 if the threshold is not violated).
        """
        if self.direction == "upper":
            violation = max(0.0, value - self.threshold)
        else:
            violation = max(0.0, self.threshold - value)
        return self.weight * (violation ** self.exponent)


@dataclass
class RewardComponent:
    """A named, weighted reward component for use in :class:`CompositeReward`.

    Attributes:
        name: Human-readable name.
        compute_fn: Callable that accepts ``**kwargs`` and returns a float reward.
        weight: Multiplicative weight.
    """

    name: str
    compute_fn: Any  # Callable[..., float]
    weight: float = 1.0


class CompositeReward:
    """Weighted combination of multiple reward components.

    Allows constructing complex, multi-objective reward functions by
    combining instances of :class:`EquityReward`, :class:`SustainabilityReward`,
    :class:`ThresholdPenalty`, or arbitrary callables.

    Example::

        composite = CompositeReward()
        composite.add("equity", equity_reward.compute, weight=0.3)
        composite.add("sustainability", sustainability_reward.compute, weight=0.5)
        composite.add("emission_penalty", emission_penalty.compute, weight=-0.2)
        total = composite.compute(
            equity={"allocations": alloc_array},
            sustainability={
                "economic_score": 0.7,
                "environmental_score": 0.8,
                "social_score": 0.6,
            },
            emission_penalty={"value": current_emissions},
        )
    """

    def __init__(self) -> None:
        """Initialise with no components."""
        self._components: list[RewardComponent] = []
        self._log = logger.bind(component="composite_reward")

    def add(
        self,
        name: str,
        compute_fn: Any,
        weight: float = 1.0,
    ) -> CompositeReward:
        """Register a reward component.

        Args:
            name: Unique name for the component.
            compute_fn: Callable that returns a scalar reward.
            weight: Multiplicative weight (negative for penalties).

        Returns:
            ``self`` for method chaining.
        """
        self._components.append(RewardComponent(name=name, compute_fn=compute_fn, weight=weight))
        return self

    def compute(self, **component_kwargs: dict[str, Any]) -> dict[str, Any]:
        """Compute the composite reward.

        Each keyword argument maps a component *name* to a dict of
        keyword arguments for that component's ``compute_fn``.

        Args:
            **component_kwargs: ``{component_name: {kwarg: value, ...}}``.

        Returns:
            Dictionary with ``total`` reward and per-component breakdown.
        """
        total = 0.0
        breakdown: dict[str, float] = {}

        for comp in self._components:
            kwargs = component_kwargs.get(comp.name, {})
            try:
                if isinstance(kwargs, dict):
                    value = float(comp.compute_fn(**kwargs))
                else:
                    value = float(comp.compute_fn(kwargs))
            except Exception as exc:
                self._log.warning(
                    "component_error", name=comp.name, error=str(exc),
                )
                value = 0.0

            weighted = comp.weight * value
            breakdown[comp.name] = round(weighted, 6)
            total += weighted

        return {
            "total": round(total, 6),
            "breakdown": breakdown,
            "n_components": len(self._components),
        }

    @property
    def component_names(self) -> list[str]:
        """Return names of all registered components."""
        return [c.name for c in self._components]

    def __len__(self) -> int:
        return len(self._components)

    def __repr__(self) -> str:
        names = ", ".join(c.name for c in self._components)
        return f"<CompositeReward(components=[{names}])>"


__all__ = [
    "EquityReward",
    "SustainabilityReward",
    "ThresholdPenalty",
    "CompositeReward",
    "RewardComponent",
]
