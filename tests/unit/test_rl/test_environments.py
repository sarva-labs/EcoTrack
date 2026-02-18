"""Tests for RL environments."""
from __future__ import annotations

import numpy as np
import pytest

from ecotrack_rl.envs.water_allocation import WaterAllocationEnv
from ecotrack_rl.envs.carbon_trading import CarbonTradingEnv
from ecotrack_rl.envs.conservation import ConservationPlanningEnv


class TestWaterAllocationEnv:
    def test_reset(self) -> None:
        env = WaterAllocationEnv()
        obs, info = env.reset()
        assert obs.shape == env.observation_space.shape
        assert env.observation_space.contains(obs)

    def test_step(self) -> None:
        env = WaterAllocationEnv()
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert obs.shape == env.observation_space.shape
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)

    def test_episode_length(self) -> None:
        env = WaterAllocationEnv()
        env.reset()
        steps = 0
        done = False
        while not done:
            action = env.action_space.sample()
            _, _, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            steps += 1
            if steps > 400:
                break
        assert steps <= 366  # ~365 days


class TestCarbonTradingEnv:
    def test_reset(self) -> None:
        env = CarbonTradingEnv()
        obs, info = env.reset()
        assert env.observation_space.contains(obs)

    def test_step(self) -> None:
        env = CarbonTradingEnv()
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(reward, float)


class TestConservationPlanningEnv:
    def test_reset(self) -> None:
        env = ConservationPlanningEnv()
        obs, info = env.reset()
        assert env.observation_space.contains(obs)

    def test_step(self) -> None:
        env = ConservationPlanningEnv()
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(reward, float)
