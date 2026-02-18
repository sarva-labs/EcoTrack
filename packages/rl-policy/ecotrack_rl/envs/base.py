"""Base environment for EcoTrack RL policy optimization.

Provides a Gymnasium-compatible base class with common utilities
shared by all EcoTrack reinforcement-learning environments.
"""
from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class BaseEnvironmentEnv(gym.Env):
    """Base Gymnasium environment for environmental policy optimisation.

    Subclasses should define specific environmental domains such as
    water resource allocation, carbon trading, or conservation planning.

    This base provides:
    * Standard metadata and render-mode handling.
    * Helper methods for reward normalisation and constraint checking.
    * Structured logging via *structlog*.
    """

    metadata: dict[str, Any] = {"render_modes": ["human", "rgb_array"]}

    def __init__(self, render_mode: str | None = None) -> None:
        """Initialize the base environment.

        Args:
            render_mode: Rendering mode (``None``, ``'human'``, ``'rgb_array'``).
        """
        super().__init__()
        self.render_mode = render_mode
        self._log = logger.bind(env=self.__class__.__name__)

    # ------------------------------------------------------------------
    # Gymnasium interface (to be overridden)
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment to an initial state.

        Args:
            seed: Random seed for reproducibility.
            options: Additional reset options.

        Returns:
            Tuple of ``(observation, info)``.
        """
        super().reset(seed=seed)
        raise NotImplementedError("Subclasses must implement reset().")

    def step(
        self, action: Any
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Execute one environment step.

        Args:
            action: The action to take.

        Returns:
            Tuple of ``(observation, reward, terminated, truncated, info)``.
        """
        raise NotImplementedError("Subclasses must implement step().")

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalise_reward(reward: float, low: float, high: float) -> float:
        """Normalise a reward to the ``[0, 1]`` range.

        Args:
            reward: Raw reward value.
            low: Minimum possible reward.
            high: Maximum possible reward.

        Returns:
            Normalised reward clipped to ``[0, 1]``.
        """
        if high == low:
            return 0.5
        return float(np.clip((reward - low) / (high - low), 0.0, 1.0))

    @staticmethod
    def check_constraint(
        value: float,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        """Return a penalty (≥0) for constraint violations.

        Args:
            value: The value to check.
            minimum: Lower bound (penalty if *value* < *minimum*).
            maximum: Upper bound (penalty if *value* > *maximum*).

        Returns:
            Non-negative penalty magnitude.
        """
        penalty = 0.0
        if minimum is not None and value < minimum:
            penalty += minimum - value
        if maximum is not None and value > maximum:
            penalty += value - maximum
        return penalty

    @staticmethod
    def softmax_allocation(raw: np.ndarray) -> np.ndarray:
        """Convert raw action values to a valid allocation via softmax.

        Ensures all values are positive and sum to 1.

        Args:
            raw: Raw action array.

        Returns:
            Normalised allocation array summing to 1.
        """
        exp = np.exp(raw - np.max(raw))
        return exp / exp.sum()


__all__ = ["BaseEnvironmentEnv"]
