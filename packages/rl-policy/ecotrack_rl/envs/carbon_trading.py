"""Carbon credit trading and allocation environment.

A carbon market simulation where the agent manages a portfolio of
emission credits, balancing economic output against emission reduction
targets.  The agent decides how much to buy/sell on the market, how
much to invest in emission reduction technology, and how much to
invest in renewable energy capacity.
"""
from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import structlog

from ecotrack_rl.envs.base import BaseEnvironmentEnv

logger = structlog.get_logger(__name__)


class CarbonTradingEnv(BaseEnvironmentEnv):
    """Gymnasium environment for carbon credit trading and allocation.

    **Observation space** (``Box(8,)``):
        0. ``carbon_price``       — Current market price per tonne CO₂ [0, 1]
        1. ``total_emissions``    — Current total emissions (normalised) [0, 1]
        2. ``emission_cap``       — Regulatory cap for the period [0, 1]
        3. ``credits_held``       — Number of credits the agent holds [0, 1]
        4. ``market_demand``      — Aggregate market demand for credits [0, 1]
        5. ``renewable_fraction`` — Fraction of energy from renewables [0, 1]
        6. ``gdp_growth``         — Normalised GDP growth rate [0, 1]
        7. ``season``             — Cyclic season indicator [0, 1]

    **Action space** (``Box(3,)``):
        0. ``buy_sell_amount``              — Positive = buy, negative = sell  [-1, 1]
        1. ``emission_reduction_investment``— Fraction of budget to invest     [0, 1]
        2. ``renewable_investment``         — Fraction of budget to invest     [0, 1]

    **Reward**:
        Maximize economic output while staying under the emission cap.
        Combines:
        - Economic productivity bonus
        - Emission reduction bonus
        - Penalty for exceeding the emission cap
        - Trading profit / loss

    **Episode length**: 52 steps (weekly decisions over one year).
    """

    metadata: dict[str, Any] = {"render_modes": ["human"]}

    def __init__(
        self,
        render_mode: str | None = None,
        max_steps: int = 52,
        initial_budget: float = 1.0,
    ) -> None:
        """Initialise the carbon trading environment.

        Args:
            render_mode: Rendering mode.
            max_steps: Steps per episode (default 52 weeks).
            initial_budget: Starting budget (normalised).
        """
        super().__init__(render_mode=render_mode)
        self.max_steps = max_steps
        self.initial_budget = initial_budget

        self.observation_space = gym.spaces.Box(
            low=0.0, high=1.0, shape=(8,), dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0, 0.0, 0.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )

        # Internal state (set in reset)
        self._step_count: int = 0
        self._carbon_price: float = 0.0
        self._total_emissions: float = 0.0
        self._emission_cap: float = 0.0
        self._credits_held: float = 0.0
        self._market_demand: float = 0.0
        self._renewable_fraction: float = 0.0
        self._gdp_growth: float = 0.0
        self._budget: float = 0.0
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
        """Reset the environment.

        Args:
            seed: Random seed.
            options: Unused.

        Returns:
            ``(observation, info)`` tuple.
        """
        super(BaseEnvironmentEnv, self).reset(seed=seed)
        rng = self.np_random

        self._step_count = 0
        self._carbon_price = float(rng.uniform(0.3, 0.6))
        self._total_emissions = float(rng.uniform(0.5, 0.8))
        self._emission_cap = float(rng.uniform(0.4, 0.7))
        self._credits_held = float(rng.uniform(0.2, 0.5))
        self._market_demand = float(rng.uniform(0.3, 0.7))
        self._renewable_fraction = float(rng.uniform(0.1, 0.3))
        self._gdp_growth = float(rng.uniform(0.4, 0.6))
        self._budget = self.initial_budget
        self._cumulative_reward = 0.0

        return self._get_observation(), self._get_info()

    def step(
        self, action: np.ndarray,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Execute one weekly trading / investment step.

        Args:
            action: Array of shape ``(3,)`` — [buy_sell, emission_invest, renew_invest].

        Returns:
            ``(observation, reward, terminated, truncated, info)`` tuple.
        """
        self._step_count += 1
        rng = self.np_random

        act = np.clip(np.asarray(action, dtype=np.float32), self.action_space.low, self.action_space.high)
        buy_sell = float(act[0])            # [-1, 1]
        emission_invest = float(act[1])     # [0, 1]
        renewable_invest = float(act[2])    # [0, 1]

        # --- trading ------------------------------------------------------
        trade_volume = buy_sell * 0.1  # scale to reasonable volume
        trade_cost = trade_volume * self._carbon_price
        self._credits_held = float(np.clip(self._credits_held + trade_volume, 0.0, 1.0))
        self._budget -= trade_cost

        # --- investments --------------------------------------------------
        invest_total = emission_invest + renewable_invest
        if invest_total > 0:
            # Scale investments to available budget fraction
            invest_budget = min(0.1 * self._budget, 0.05)  # cap at 5% per step
            if invest_budget > 0:
                em_spend = invest_budget * (emission_invest / invest_total)
                re_spend = invest_budget * (renewable_invest / invest_total)
                # Emission reduction effect
                self._total_emissions = float(np.clip(
                    self._total_emissions - em_spend * 0.5, 0.0, 1.0,
                ))
                # Renewable capacity growth
                self._renewable_fraction = float(np.clip(
                    self._renewable_fraction + re_spend * 0.3, 0.0, 1.0,
                ))
                self._budget -= (em_spend + re_spend)

        # --- market dynamics ----------------------------------------------
        # Price elasticity: higher demand → higher price
        price_delta = rng.normal(0, 0.02)
        demand_effect = (self._market_demand - 0.5) * 0.01
        self._carbon_price = float(np.clip(
            self._carbon_price + price_delta + demand_effect, 0.05, 1.0,
        ))

        # Market demand evolves
        self._market_demand = float(np.clip(
            self._market_demand + rng.normal(0, 0.03), 0.1, 0.9,
        ))

        # GDP growth with small drift
        self._gdp_growth = float(np.clip(
            self._gdp_growth + rng.normal(0, 0.01), 0.2, 0.8,
        ))

        # Emissions natural growth from economic activity
        self._total_emissions = float(np.clip(
            self._total_emissions + self._gdp_growth * 0.005 - self._renewable_fraction * 0.003,
            0.0, 1.0,
        ))

        # Emission cap tightens slightly over time
        self._emission_cap = float(np.clip(
            self._emission_cap - 0.002, 0.1, 1.0,
        ))

        # --- reward -------------------------------------------------------
        # Economic productivity: higher GDP growth is good
        economic_reward = self._gdp_growth * 0.3

        # Emission reduction reward: staying below cap
        emission_gap = self._emission_cap - self._total_emissions
        emission_reward = 0.0
        if emission_gap >= 0:
            emission_reward = emission_gap * 2.0  # bonus for being under cap
        else:
            emission_reward = emission_gap * 5.0  # heavy penalty for exceeding

        # Renewable transition bonus
        renewable_reward = self._renewable_fraction * 0.2

        # Trading profit/loss (credits are an asset)
        portfolio_value = self._credits_held * self._carbon_price
        trading_reward = portfolio_value * 0.1

        reward = economic_reward + emission_reward + renewable_reward + trading_reward
        self._cumulative_reward += reward

        terminated = False
        truncated = self._step_count >= self.max_steps

        obs = self._get_observation()
        info = self._get_info()
        info["reward_components"] = {
            "economic": economic_reward,
            "emission": emission_reward,
            "renewable": renewable_reward,
            "trading": trading_reward,
        }
        info["actions"] = {
            "buy_sell": buy_sell,
            "emission_invest": emission_invest,
            "renewable_invest": renewable_invest,
        }
        return obs, float(reward), terminated, truncated, info

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_observation(self) -> np.ndarray:
        """Build observation vector."""
        season = float((self._step_count % 52) / 52.0)
        return np.array([
            self._carbon_price,
            self._total_emissions,
            self._emission_cap,
            self._credits_held,
            self._market_demand,
            self._renewable_fraction,
            self._gdp_growth,
            season,
        ], dtype=np.float32)

    def _get_info(self) -> dict[str, Any]:
        """Return episode info dict."""
        return {
            "step": self._step_count,
            "budget": self._budget,
            "cumulative_reward": self._cumulative_reward,
            "emission_gap": self._emission_cap - self._total_emissions,
        }


__all__ = ["CarbonTradingEnv"]
