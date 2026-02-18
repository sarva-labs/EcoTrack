"""Conservation area planning environment.

A grid-based environment where the agent selects land parcels to
protect or restore, maximising biodiversity coverage and habitat
connectivity within a fixed budget constraint.
"""
from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import structlog

from ecotrack_rl.envs.base import BaseEnvironmentEnv

logger = structlog.get_logger(__name__)

# Per-parcel feature indices
_BIODIVERSITY = 0
_LAND_USE = 1      # 0 = unprotected, 1 = protected
_COST = 2
_CONNECTIVITY = 3
_THREAT = 4
_N_FEATURES = 5


class ConservationPlanningEnv(BaseEnvironmentEnv):
    """Gymnasium environment for conservation area planning.

    The world is a ``grid_size × grid_size`` grid of land parcels.
    Each parcel has attributes for biodiversity value, current land-use,
    protection cost, connectivity to neighbouring protected areas, and
    threat level.

    **Observation space** (``Box(grid_size * grid_size * 5,)``):
        Flattened grid where each parcel has 5 features:
        ``[biodiversity_value, land_use, cost, connectivity, threat_level]``.

    **Action space** (``Discrete(grid_size * grid_size)``):
        Index of the parcel to protect / restore.

    **Reward** (per step):
        * Biodiversity gained from the newly protected parcel.
        * Connectivity bonus (adjacency to other protected parcels).
        * Threat mitigation bonus (higher reward for protecting
          high-threat parcels).
        * Budget penalty when the budget is exhausted.

    **Termination**: budget exhausted **or** all parcels protected.
    **Truncation**: after ``max_steps`` steps.
    """

    metadata: dict[str, Any] = {"render_modes": ["human"]}

    def __init__(
        self,
        render_mode: str | None = None,
        grid_size: int = 10,
        initial_budget: float = 5.0,
        max_steps: int = 50,
    ) -> None:
        """Initialise the conservation planning environment.

        Args:
            render_mode: Rendering mode.
            grid_size: Width and height of the grid.
            initial_budget: Total conservation budget.
            max_steps: Maximum steps before truncation.
        """
        super().__init__(render_mode=render_mode)
        self.grid_size = grid_size
        self.n_parcels = grid_size * grid_size
        self.initial_budget = initial_budget
        self.max_steps = max_steps

        obs_dim = self.n_parcels * _N_FEATURES
        self.observation_space = gym.spaces.Box(
            low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32,
        )
        self.action_space = gym.spaces.Discrete(self.n_parcels)

        # Internal state (set in reset)
        self._grid: np.ndarray = np.zeros(
            (self.grid_size, self.grid_size, _N_FEATURES), dtype=np.float32,
        )
        self._budget: float = 0.0
        self._step_count: int = 0
        self._total_biodiversity: float = 0.0
        self._protected_count: int = 0

    # ------------------------------------------------------------------
    # Gymnasium interface
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset environment with a randomly generated landscape.

        Args:
            seed: Random seed.
            options: Unused.

        Returns:
            ``(observation, info)`` tuple.
        """
        super(BaseEnvironmentEnv, self).reset(seed=seed)
        rng = self.np_random

        self._step_count = 0
        self._budget = self.initial_budget
        self._total_biodiversity = 0.0
        self._protected_count = 0

        # Generate random landscape
        grid = np.zeros(
            (self.grid_size, self.grid_size, _N_FEATURES), dtype=np.float32,
        )
        grid[:, :, _BIODIVERSITY] = rng.uniform(0.0, 1.0, (self.grid_size, self.grid_size)).astype(np.float32)
        grid[:, :, _LAND_USE] = 0.0  # all unprotected initially
        grid[:, :, _COST] = rng.uniform(0.05, 0.3, (self.grid_size, self.grid_size)).astype(np.float32)
        grid[:, :, _CONNECTIVITY] = 0.0  # updated dynamically
        grid[:, :, _THREAT] = rng.uniform(0.0, 1.0, (self.grid_size, self.grid_size)).astype(np.float32)

        self._grid = grid
        self._update_connectivity()

        return self._get_observation(), self._get_info()

    def step(
        self, action: int,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Protect a parcel at the given grid index.

        Args:
            action: Flat index of the parcel to protect.

        Returns:
            ``(observation, reward, terminated, truncated, info)`` tuple.
        """
        self._step_count += 1
        action = int(action) % self.n_parcels
        row, col = divmod(action, self.grid_size)

        reward = 0.0
        already_protected = self._grid[row, col, _LAND_USE] > 0.5

        if already_protected:
            # Penalty for wasting a step on already-protected parcel
            reward = -0.1
        else:
            cost = float(self._grid[row, col, _COST])
            if self._budget >= cost:
                # Protect the parcel
                self._budget -= cost
                self._grid[row, col, _LAND_USE] = 1.0
                self._protected_count += 1

                # Biodiversity reward
                bio_value = float(self._grid[row, col, _BIODIVERSITY])
                reward += bio_value

                # Connectivity bonus: adjacent protected parcels
                connectivity_bonus = self._count_protected_neighbours(row, col) * 0.15
                reward += connectivity_bonus

                # Threat mitigation bonus
                threat = float(self._grid[row, col, _THREAT])
                reward += threat * 0.3  # more reward for protecting threatened parcels

                self._total_biodiversity += bio_value
                self._update_connectivity()
            else:
                # Cannot afford — small penalty
                reward = -0.05

        # Termination conditions
        all_protected = self._protected_count >= self.n_parcels
        budget_exhausted = self._budget < float(self._grid[:, :, _COST][self._grid[:, :, _LAND_USE] < 0.5].min()) if self._protected_count < self.n_parcels else True
        terminated = all_protected or budget_exhausted
        truncated = self._step_count >= self.max_steps and not terminated

        obs = self._get_observation()
        info = self._get_info()
        info["action_row"] = row
        info["action_col"] = col
        info["already_protected"] = already_protected
        info["reward"] = reward
        return obs, float(reward), terminated, truncated, info

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_observation(self) -> np.ndarray:
        """Flatten the grid into a 1-D observation vector."""
        return self._grid.reshape(-1).copy()

    def _get_info(self) -> dict[str, Any]:
        """Return episode info."""
        return {
            "step": self._step_count,
            "budget_remaining": self._budget,
            "protected_count": self._protected_count,
            "total_parcels": self.n_parcels,
            "total_biodiversity": self._total_biodiversity,
            "protection_fraction": self._protected_count / self.n_parcels,
        }

    def _count_protected_neighbours(self, row: int, col: int) -> int:
        """Count protected parcels adjacent (4-connected) to ``(row, col)``."""
        count = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                if self._grid[nr, nc, _LAND_USE] > 0.5:
                    count += 1
        return count

    def _update_connectivity(self) -> None:
        """Recompute the connectivity feature for every parcel.

        Connectivity is the fraction of 4-connected neighbours that
        are protected.
        """
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                neighbours = 0
                protected_neighbours = 0
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                        neighbours += 1
                        if self._grid[nr, nc, _LAND_USE] > 0.5:
                            protected_neighbours += 1
                self._grid[r, c, _CONNECTIVITY] = (
                    protected_neighbours / neighbours if neighbours > 0 else 0.0
                )


__all__ = ["ConservationPlanningEnv"]
