"""Policy evaluation and comparison framework.

Provides tools for evaluating trained RL policies, comparing multiple
agents, and computing fairness/equity metrics for resource allocation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PolicyMetrics:
    """Aggregate metrics from policy evaluation.

    Attributes:
        mean_reward: Mean total episode reward.
        std_reward: Standard deviation of episode rewards.
        min_reward: Minimum episode reward observed.
        max_reward: Maximum episode reward observed.
        mean_episode_length: Mean number of steps per episode.
        success_rate: Fraction of episodes meeting the success criterion.
    """

    mean_reward: float
    std_reward: float
    min_reward: float
    max_reward: float
    mean_episode_length: float
    success_rate: float


class PolicyEvaluator:
    """Evaluate and compare RL policies across EcoTrack environments.

    Supports single-agent evaluation, multi-agent comparison,
    training-curve visualisation, and fairness metric computation.
    """

    def __init__(self, success_threshold: float | None = None) -> None:
        """Initialise the evaluator.

        Args:
            success_threshold: Reward threshold above which an episode
                is considered successful.  If *None*, ``success_rate``
                is set to the fraction of episodes with positive total
                reward.
        """
        self.success_threshold = success_threshold
        self._log = logger.bind(component="policy_evaluator")

    # ------------------------------------------------------------------
    # Single-agent evaluation
    # ------------------------------------------------------------------

    def evaluate_policy(
        self,
        agent: Any,
        env: Any,
        n_episodes: int = 100,
        deterministic: bool = True,
    ) -> PolicyMetrics:
        """Evaluate a policy over multiple episodes.

        Args:
            agent: RL agent with a ``select_action(state, ...)`` method.
                   For DQN agents: ``select_action(state, greedy=True)``.
                   For PPO agents: ``select_action(state, deterministic=True)``.
            env: Gymnasium environment.
            n_episodes: Number of evaluation episodes.
            deterministic: Whether to use deterministic action selection.

        Returns:
            :class:`PolicyMetrics` summarising performance.
        """
        self._log.info("evaluating_policy", n_episodes=n_episodes)
        episode_rewards: list[float] = []
        episode_lengths: list[int] = []

        for ep in range(n_episodes):
            state, _ = env.reset()
            total_reward = 0.0
            steps = 0
            done = False

            while not done:
                action = self._get_action(agent, state, deterministic)
                state, reward, terminated, truncated, _ = env.step(action)
                total_reward += reward
                steps += 1
                done = terminated or truncated

            episode_rewards.append(total_reward)
            episode_lengths.append(steps)

        rewards_arr = np.array(episode_rewards)
        threshold = self.success_threshold if self.success_threshold is not None else 0.0
        success_rate = float(np.mean(rewards_arr >= threshold))

        metrics = PolicyMetrics(
            mean_reward=float(np.mean(rewards_arr)),
            std_reward=float(np.std(rewards_arr)),
            min_reward=float(np.min(rewards_arr)),
            max_reward=float(np.max(rewards_arr)),
            mean_episode_length=float(np.mean(episode_lengths)),
            success_rate=success_rate,
        )
        self._log.info(
            "evaluation_complete",
            mean_reward=round(metrics.mean_reward, 3),
            success_rate=round(metrics.success_rate, 3),
        )
        return metrics

    # ------------------------------------------------------------------
    # Multi-agent comparison
    # ------------------------------------------------------------------

    def compare_policies(
        self,
        agents: dict[str, Any],
        env: Any,
        n_episodes: int = 100,
    ) -> dict[str, Any]:
        """Compare multiple policies on the same environment.

        Args:
            agents: Mapping of ``name → agent``.
            env: Gymnasium environment.
            n_episodes: Evaluation episodes per agent.

        Returns:
            Dictionary with per-agent metrics and a ranking.
        """
        self._log.info("comparing_policies", agents=list(agents.keys()))
        results: dict[str, PolicyMetrics] = {}
        for name, agent in agents.items():
            results[name] = self.evaluate_policy(agent, env, n_episodes)

        # Build comparison table
        table: list[dict[str, Any]] = []
        for name, m in results.items():
            table.append({
                "agent": name,
                "mean_reward": round(m.mean_reward, 4),
                "std_reward": round(m.std_reward, 4),
                "min_reward": round(m.min_reward, 4),
                "max_reward": round(m.max_reward, 4),
                "mean_length": round(m.mean_episode_length, 1),
                "success_rate": round(m.success_rate, 4),
            })

        # Rank by mean reward
        ranking = sorted(table, key=lambda r: r["mean_reward"], reverse=True)
        return {
            "comparison": ranking,
            "best_agent": ranking[0]["agent"] if ranking else None,
        }

    # ------------------------------------------------------------------
    # Training curve visualisation
    # ------------------------------------------------------------------

    @staticmethod
    def plot_training_curves(
        training_histories: dict[str, list[float]],
        window: int = 20,
    ) -> dict[str, Any]:
        """Prepare smoothed training-curve data for plotting.

        Does **not** depend on matplotlib at import time; returns
        raw data that can be fed to any plotting backend.

        Args:
            training_histories: Mapping of ``label → list of per-episode rewards``.
            window: Smoothing window size for the moving average.

        Returns:
            Dictionary with ``raw`` and ``smoothed`` series per label.
        """
        result: dict[str, Any] = {}
        for label, rewards in training_histories.items():
            arr = np.array(rewards, dtype=np.float64)
            # Compute simple moving average
            if len(arr) >= window:
                kernel = np.ones(window) / window
                smoothed = np.convolve(arr, kernel, mode="valid").tolist()
            else:
                smoothed = arr.tolist()
            result[label] = {
                "raw": arr.tolist(),
                "smoothed": smoothed,
                "final_mean": float(np.mean(arr[-window:])) if len(arr) >= window else float(np.mean(arr)),
            }
        return result

    # ------------------------------------------------------------------
    # Fairness metrics
    # ------------------------------------------------------------------

    def compute_fairness_metrics(
        self,
        agent: Any,
        env: Any,
        n_episodes: int = 50,
    ) -> dict[str, Any]:
        """Measure equity of resource allocation across episodes.

        Collects per-step allocation data from ``info["allocation"]``
        or ``info["satisfaction"]`` dicts and computes:
        * **Gini coefficient** — inequality measure (0 = perfect equality).
        * **Min-max ratio** — ratio of minimum to maximum allocation.
        * **Coefficient of variation (CV)** — std / mean.

        Args:
            agent: RL agent.
            env: Gymnasium environment that reports allocations in ``info``.
            n_episodes: Number of episodes to evaluate.

        Returns:
            Dictionary with fairness metrics.
        """
        self._log.info("computing_fairness", n_episodes=n_episodes)
        all_allocations: list[np.ndarray] = []

        for _ in range(n_episodes):
            state, _ = env.reset()
            done = False
            while not done:
                action = self._get_action(agent, state, deterministic=True)
                state, _, terminated, truncated, info = env.step(action)
                done = terminated or truncated

                # Collect allocation / satisfaction data from info
                alloc = info.get("allocation") or info.get("satisfaction")
                if alloc and isinstance(alloc, dict):
                    all_allocations.append(np.array(list(alloc.values()), dtype=np.float64))

        if not all_allocations:
            return {
                "gini_coefficient": None,
                "min_max_ratio": None,
                "coefficient_of_variation": None,
                "note": "No allocation data available in environment info",
            }

        alloc_matrix = np.array(all_allocations)  # (T, n_sectors)
        mean_alloc = alloc_matrix.mean(axis=0)  # average over time

        gini = self._gini(mean_alloc)
        min_max = float(mean_alloc.min() / mean_alloc.max()) if mean_alloc.max() > 0 else 0.0
        cv = float(mean_alloc.std() / mean_alloc.mean()) if mean_alloc.mean() > 0 else 0.0

        return {
            "gini_coefficient": round(gini, 4),
            "min_max_ratio": round(min_max, 4),
            "coefficient_of_variation": round(cv, 4),
            "mean_allocation_per_sector": {
                f"sector_{i}": round(float(v), 4) for i, v in enumerate(mean_alloc)
            },
            "n_samples": len(all_allocations),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_action(agent: Any, state: np.ndarray, deterministic: bool) -> Any:
        """Get action from agent, handling different agent interfaces.

        Args:
            agent: RL agent.
            state: Observation.
            deterministic: Use greedy / deterministic mode.

        Returns:
            Action suitable for ``env.step()``.
        """
        # PPO-style: select_action returns (action, log_prob, value)
        if hasattr(agent, "select_action"):
            import inspect
            sig = inspect.signature(agent.select_action)
            params = list(sig.parameters.keys())
            if "deterministic" in params:
                result = agent.select_action(state, deterministic=deterministic)
                return result[0] if isinstance(result, tuple) else result
            if "greedy" in params:
                return agent.select_action(state, greedy=deterministic)
            return agent.select_action(state)
        raise TypeError(f"Agent {type(agent)} has no 'select_action' method")

    @staticmethod
    def _gini(values: np.ndarray) -> float:
        """Compute Gini coefficient.

        .. math::

            G = \\frac{\\sum_i \\sum_j |x_i - x_j|}{2 n \\sum_i x_i}

        Args:
            values: 1-D array of non-negative values.

        Returns:
            Gini coefficient in [0, 1].
        """
        arr = np.asarray(values, dtype=np.float64).flatten()
        if arr.sum() == 0:
            return 0.0
        n = len(arr)
        diff_sum = float(np.sum(np.abs(arr[:, None] - arr[None, :])))
        return diff_sum / (2 * n * float(arr.sum()))


__all__ = ["PolicyEvaluator", "PolicyMetrics"]
