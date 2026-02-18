"""Water resource allocation environment.

A multi-stakeholder water allocation problem where the agent must
distribute limited water resources across agricultural, industrial,
domestic, and environmental needs.

The agent observes hydrological state (reservoir level, rainfall
forecast, demand profiles, etc.) and outputs continuous allocation
fractions.  Episodes last 365 steps representing daily allocation
decisions for one year.
"""
from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import structlog

from ecotrack_rl.envs.base import BaseEnvironmentEnv

logger = structlog.get_logger(__name__)

# Sector indices
_AGRICULTURE = 0
_INDUSTRY = 1
_DOMESTIC = 2
_ENVIRONMENT = 3

_SECTOR_NAMES = ["agriculture", "industry", "domestic", "environment"]

# Minimum thresholds (fraction of demand that must be met)
_MIN_THRESHOLDS = np.array([0.30, 0.40, 0.60, 0.20], dtype=np.float32)

# Reward weights for demand satisfaction per sector
_SATISFACTION_WEIGHTS = np.array([0.30, 0.20, 0.30, 0.20], dtype=np.float32)


class WaterAllocationEnv(BaseEnvironmentEnv):
    """Gymnasium environment for multi-stakeholder water allocation.

    **Observation space** (``Box(10,)``):
        0. ``water_level``        — Current reservoir level [0, 1]
        1. ``rainfall_forecast``  — Predicted rainfall for the next day [0, 1]
        2. ``agricultural_demand``— Normalised ag demand [0, 1]
        3. ``industrial_demand``  — Normalised industrial demand [0, 1]
        4. ``domestic_demand``    — Normalised domestic demand [0, 1]
        5. ``environmental_flow`` — Required ecological minimum flow [0, 1]
        6. ``reservoir_capacity`` — Effective reservoir capacity [0, 1]
        7. ``season``             — Cyclic season indicator [0, 1]
        8. ``temperature``        — Normalised temperature [0, 1]
        9. ``soil_moisture``      — Normalised soil moisture [0, 1]

    **Action space** (``Box(4,)``):
        Continuous fractions in [0, 1] for each of the four sectors.
        The action is softmax-normalised so that allocations sum to 1.

    **Reward** (per step):
        Weighted satisfaction score minus penalties for:
        - Shortfall below minimum thresholds
        - Environmental damage from low ecological flow
        - Inequitable distribution (Gini penalty)
        - Water waste / overflow

    **Episode length**: 365 steps (one simulated year).
    """

    metadata: dict[str, Any] = {"render_modes": ["human"]}

    def __init__(
        self,
        render_mode: str | None = None,
        max_steps: int = 365,
        stochastic_rainfall: bool = True,
    ) -> None:
        """Initialise the water allocation environment.

        Args:
            render_mode: Rendering mode.
            max_steps: Maximum number of steps per episode.
            stochastic_rainfall: Whether rainfall follows a stochastic model.
        """
        super().__init__(render_mode=render_mode)
        self.max_steps = max_steps
        self.stochastic_rainfall = stochastic_rainfall

        # --- spaces -------------------------------------------------------
        self.observation_space = gym.spaces.Box(
            low=0.0, high=1.0, shape=(10,), dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=0.0, high=1.0, shape=(4,), dtype=np.float32,
        )

        # --- internal state (set in reset) --------------------------------
        self._step_count: int = 0
        self._water_level: float = 0.0
        self._demands: np.ndarray = np.zeros(4, dtype=np.float32)
        self._env_flow_requirement: float = 0.0
        self._temperature: float = 0.0
        self._soil_moisture: float = 0.0
        self._cumulative_reward: float = 0.0

    # ------------------------------------------------------------------
    # Gymnasium interface
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment to randomised initial conditions.

        Args:
            seed: Random seed for reproducibility.
            options: Additional reset options (unused).

        Returns:
            ``(observation, info)`` tuple.
        """
        super(BaseEnvironmentEnv, self).reset(seed=seed)
        rng = self.np_random

        self._step_count = 0
        self._water_level = float(rng.uniform(0.4, 0.8))
        self._demands = rng.uniform(0.2, 0.6, size=4).astype(np.float32)
        self._env_flow_requirement = float(rng.uniform(0.10, 0.25))
        self._temperature = float(rng.uniform(0.3, 0.7))
        self._soil_moisture = float(rng.uniform(0.3, 0.7))
        self._cumulative_reward = 0.0

        obs = self._get_observation()
        info = self._get_info()
        return obs, info

    def step(
        self, action: np.ndarray,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Execute one daily allocation step.

        Args:
            action: Raw allocation array of shape ``(4,)`` in ``[0, 1]``.

        Returns:
            ``(observation, reward, terminated, truncated, info)`` tuple.
        """
        self._step_count += 1
        rng = self.np_random

        # Normalise action to valid allocation via softmax
        allocation = self.softmax_allocation(np.asarray(action, dtype=np.float32))

        # Water available for distribution this step
        available_water = self._water_level

        # Compute per-sector allocation volumes
        volumes = allocation * available_water

        # --- reward computation -------------------------------------------
        satisfaction = np.zeros(4, dtype=np.float32)
        for i in range(4):
            if self._demands[i] > 0:
                satisfaction[i] = min(volumes[i] / self._demands[i], 1.0)
            else:
                satisfaction[i] = 1.0

        # Weighted satisfaction
        weighted_sat = float(np.dot(_SATISFACTION_WEIGHTS, satisfaction))

        # Penalty: shortfall below minimum thresholds
        shortfall_penalty = 0.0
        for i in range(4):
            if satisfaction[i] < _MIN_THRESHOLDS[i]:
                shortfall_penalty += (_MIN_THRESHOLDS[i] - satisfaction[i]) * 2.0

        # Penalty: environmental flow damage
        env_penalty = 0.0
        if volumes[_ENVIRONMENT] < self._env_flow_requirement:
            env_penalty = (self._env_flow_requirement - volumes[_ENVIRONMENT]) * 3.0

        # Penalty: inequitable distribution (Gini coefficient)
        gini = self._gini(satisfaction)
        equity_penalty = gini * 0.5

        # Penalty: overflow / waste (reservoir > 1.0 after inflow)
        waste_penalty = 0.0

        # Compose reward
        reward = weighted_sat - shortfall_penalty - env_penalty - equity_penalty - waste_penalty

        # --- state dynamics -----------------------------------------------
        # Water balance: inflow (rain) - outflow (allocation total)
        rainfall = self._sample_rainfall(rng)
        total_allocated = float(np.sum(volumes))
        self._water_level = float(np.clip(
            self._water_level - total_allocated + rainfall, 0.0, 1.0,
        ))

        # Evolve demands seasonally
        season_phase = (self._step_count / self.max_steps) * 2 * np.pi
        self._demands[_AGRICULTURE] = float(np.clip(
            0.4 + 0.2 * np.sin(season_phase), 0.1, 0.8,
        ))
        self._demands[_DOMESTIC] = float(np.clip(
            0.35 + 0.1 * np.sin(season_phase + np.pi / 2), 0.2, 0.6,
        ))
        self._demands[_INDUSTRY] = float(np.clip(
            0.3 + 0.05 * np.sin(season_phase + np.pi), 0.15, 0.5,
        ))
        self._demands[_ENVIRONMENT] = self._env_flow_requirement

        # Temperature and soil moisture drift
        self._temperature = float(np.clip(
            self._temperature + rng.normal(0, 0.02), 0.0, 1.0,
        ))
        self._soil_moisture = float(np.clip(
            self._soil_moisture + rainfall * 0.3 - 0.01, 0.0, 1.0,
        ))

        self._cumulative_reward += reward
        terminated = False
        truncated = self._step_count >= self.max_steps

        obs = self._get_observation()
        info = self._get_info()
        info["allocation"] = {
            _SECTOR_NAMES[i]: float(allocation[i]) for i in range(4)
        }
        info["satisfaction"] = {
            _SECTOR_NAMES[i]: float(satisfaction[i]) for i in range(4)
        }
        info["reward_components"] = {
            "weighted_satisfaction": weighted_sat,
            "shortfall_penalty": shortfall_penalty,
            "env_penalty": env_penalty,
            "equity_penalty": equity_penalty,
        }
        return obs, float(reward), terminated, truncated, info

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_observation(self) -> np.ndarray:
        """Build the current observation vector."""
        season = float((self._step_count % 365) / 365.0)
        return np.array([
            self._water_level,
            self._sample_rainfall_forecast(),
            self._demands[_AGRICULTURE],
            self._demands[_INDUSTRY],
            self._demands[_DOMESTIC],
            self._env_flow_requirement,
            min(self._water_level + 0.1, 1.0),  # effective capacity proxy
            season,
            self._temperature,
            self._soil_moisture,
        ], dtype=np.float32)

    def _get_info(self) -> dict[str, Any]:
        """Return episode info dict."""
        return {
            "step": self._step_count,
            "water_level": self._water_level,
            "cumulative_reward": self._cumulative_reward,
        }

    def _sample_rainfall(self, rng: np.random.Generator) -> float:
        """Sample daily rainfall amount ∈ [0, 0.3].

        Uses a seasonal sinusoidal base with stochastic noise.

        Args:
            rng: NumPy random generator.

        Returns:
            Rainfall value.
        """
        season_phase = (self._step_count / self.max_steps) * 2 * np.pi
        base = 0.08 + 0.06 * np.sin(season_phase + np.pi)  # wetter in winter
        if self.stochastic_rainfall:
            noise = rng.exponential(0.02)
        else:
            noise = 0.0
        return float(np.clip(base + noise, 0.0, 0.3))

    def _sample_rainfall_forecast(self) -> float:
        """Return a noisy rainfall forecast for the observation."""
        season_phase = (self._step_count / self.max_steps) * 2 * np.pi
        forecast = 0.08 + 0.06 * np.sin(season_phase + np.pi)
        return float(np.clip(forecast, 0.0, 1.0))

    @staticmethod
    def _gini(values: np.ndarray) -> float:
        """Compute the Gini coefficient for an array of values.

        The Gini coefficient measures inequality: 0 = perfect equality,
        1 = maximal inequality.

        .. math::

            G = \\frac{\\sum_i \\sum_j |x_i - x_j|}{2 n \\sum_i x_i}

        Args:
            values: 1-D array of non-negative values.

        Returns:
            Gini coefficient in [0, 1].
        """
        arr = np.asarray(values, dtype=np.float64)
        if arr.sum() == 0:
            return 0.0
        n = len(arr)
        diff_sum = float(np.sum(np.abs(arr[:, None] - arr[None, :])))
        return diff_sum / (2 * n * float(arr.sum()))


__all__ = ["WaterAllocationEnv"]
