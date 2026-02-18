"""EcoTrack RL — Reinforcement learning for environmental policy optimization."""
from __future__ import annotations

from ecotrack_rl.agents.dqn import DQNAgent, DQNConfig
from ecotrack_rl.agents.ppo import PPOAgent, PPOConfig
from ecotrack_rl.envs.base import BaseEnvironmentEnv
from ecotrack_rl.envs.carbon_trading import CarbonTradingEnv
from ecotrack_rl.envs.conservation import ConservationPlanningEnv
from ecotrack_rl.envs.water_allocation import WaterAllocationEnv
from ecotrack_rl.policies.policy_evaluator import PolicyEvaluator, PolicyMetrics
from ecotrack_rl.policies.reward_shaping import (
    CompositeReward,
    EquityReward,
    SustainabilityReward,
    ThresholdPenalty,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Environments
    "BaseEnvironmentEnv",
    "WaterAllocationEnv",
    "CarbonTradingEnv",
    "ConservationPlanningEnv",
    # Agents
    "DQNAgent",
    "DQNConfig",
    "PPOAgent",
    "PPOConfig",
    # Policies
    "PolicyEvaluator",
    "PolicyMetrics",
    "EquityReward",
    "SustainabilityReward",
    "ThresholdPenalty",
    "CompositeReward",
]
