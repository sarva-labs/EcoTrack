"""Proximal Policy Optimization agent for continuous action spaces.

Implements PPO-Clip with an Actor-Critic architecture, Generalised
Advantage Estimation (GAE), and proper advantage normalisation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

logger = structlog.get_logger(__name__)


@dataclass
class PPOConfig:
    """Configuration for the PPO agent.

    Attributes:
        hidden_dims: Hidden layer sizes for actor and critic MLPs.
        lr_actor: Learning rate for the actor (policy) network.
        lr_critic: Learning rate for the critic (value) network.
        gamma: Discount factor.
        gae_lambda: GAE λ parameter for advantage estimation.
        clip_epsilon: PPO clipping parameter.
        n_epochs: Number of optimisation epochs per update.
        batch_size: Mini-batch size within each epoch.
        entropy_coeff: Entropy bonus coefficient for exploration.
        max_grad_norm: Maximum gradient norm for clipping.
        value_loss_coeff: Weight of the value-function loss.
    """

    hidden_dims: list[int] = field(default_factory=lambda: [64, 64])
    lr_actor: float = 3e-4
    lr_critic: float = 1e-3
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    n_epochs: int = 10
    batch_size: int = 64
    entropy_coeff: float = 0.01
    max_grad_norm: float = 0.5
    value_loss_coeff: float = 0.5


# =====================================================================
# Networks
# =====================================================================


class ActorNetwork(nn.Module):
    """Gaussian policy network.

    Outputs the mean and log standard-deviation of a diagonal Gaussian
    over the continuous action space.
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dims: list[int]) -> None:
        """Build the actor network.

        Args:
            state_dim: Observation dimensionality.
            action_dim: Action dimensionality.
            hidden_dims: List of hidden layer widths.
        """
        super().__init__()
        layers: list[nn.Module] = []
        prev = state_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.Tanh())
            prev = h

        self.shared = nn.Sequential(*layers)
        self.mean_head = nn.Linear(prev, action_dim)
        self.log_std_head = nn.Linear(prev, action_dim)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            x: State tensor of shape ``(batch, state_dim)``.

        Returns:
            Tuple of ``(mean, log_std)`` each of shape ``(batch, action_dim)``.
        """
        h = self.shared(x)
        mean = self.mean_head(h)
        log_std = self.log_std_head(h).clamp(-20.0, 2.0)
        return mean, log_std


class CriticNetwork(nn.Module):
    """State-value critic network ``V(s)``."""

    def __init__(self, state_dim: int, hidden_dims: list[int]) -> None:
        """Build the critic network.

        Args:
            state_dim: Observation dimensionality.
            hidden_dims: List of hidden layer widths.
        """
        super().__init__()
        layers: list[nn.Module] = []
        prev = state_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.Tanh())
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: State tensor of shape ``(batch, state_dim)``.

        Returns:
            State value of shape ``(batch, 1)``.
        """
        return self.net(x)


# =====================================================================
# Trajectory buffer
# =====================================================================


class TrajectoryBuffer:
    """Stores on-policy trajectory data for PPO updates."""

    def __init__(self) -> None:
        self.states: list[np.ndarray] = []
        self.actions: list[np.ndarray] = []
        self.log_probs: list[float] = []
        self.rewards: list[float] = []
        self.values: list[float] = []
        self.dones: list[bool] = []

    def store(
        self,
        state: np.ndarray,
        action: np.ndarray,
        log_prob: float,
        reward: float,
        value: float,
        done: bool,
    ) -> None:
        """Append a single transition.

        Args:
            state: Observation.
            action: Action taken.
            log_prob: Log-probability of the action under the current policy.
            reward: Reward received.
            value: Critic's estimated state value.
            done: Whether the episode ended.
        """
        self.states.append(state)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.values.append(value)
        self.dones.append(done)

    def clear(self) -> None:
        """Clear all stored data."""
        self.states.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.values.clear()
        self.dones.clear()

    def __len__(self) -> int:
        return len(self.states)


# =====================================================================
# PPO Agent
# =====================================================================


class PPOAgent:
    """Proximal Policy Optimization agent for continuous-action environments.

    Features:
    * Diagonal-Gaussian actor with learned mean and log-std.
    * Separate critic (value function) network.
    * PPO-Clip objective with configurable ε.
    * Generalised Advantage Estimation (GAE-λ).
    * Proper advantage normalisation (zero mean, unit variance).
    * Entropy bonus for exploration.
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        config: PPOConfig | None = None,
        device: str | None = None,
    ) -> None:
        """Initialise the PPO agent.

        Args:
            state_dim: Dimension of the observation space.
            action_dim: Dimension of the action space.
            config: Optional configuration; defaults used if *None*.
            device: PyTorch device (auto-detected if *None*).
        """
        self.config = config or PPOConfig()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        self.actor = ActorNetwork(state_dim, action_dim, self.config.hidden_dims).to(self.device)
        self.critic = CriticNetwork(state_dim, self.config.hidden_dims).to(self.device)

        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=self.config.lr_actor)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=self.config.lr_critic)

        self.buffer = TrajectoryBuffer()

        # Bookkeeping
        self._episode_rewards: list[float] = []
        self._actor_losses: list[float] = []
        self._critic_losses: list[float] = []
        self._log = logger.bind(agent="PPO")

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------

    def select_action(
        self, state: np.ndarray, deterministic: bool = False,
    ) -> tuple[np.ndarray, float, float]:
        """Select an action from the Gaussian policy.

        Args:
            state: Observation array of shape ``(state_dim,)``.
            deterministic: If *True*, use the mean action (no sampling).

        Returns:
            Tuple of ``(action, log_prob, state_value)``.
        """
        state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            mean, log_std = self.actor(state_t)
            value = self.critic(state_t)

        std = log_std.exp()
        dist = Normal(mean, std)

        if deterministic:
            action_t = mean
        else:
            action_t = dist.sample()

        log_prob = dist.log_prob(action_t).sum(dim=-1)

        action = action_t.squeeze(0).cpu().numpy()
        return action, float(log_prob.item()), float(value.item())

    # ------------------------------------------------------------------
    # GAE computation
    # ------------------------------------------------------------------

    def _compute_gae(
        self,
        rewards: list[float],
        values: list[float],
        dones: list[bool],
        last_value: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute Generalised Advantage Estimation.

        Implements GAE(γ, λ) from Schulman et al., 2016.

        .. math::

            \\hat{A}_t = \\sum_{l=0}^{T-t} (\\gamma \\lambda)^l \\delta_{t+l}

        where ``δ_t = r_t + γ V(s_{t+1}) - V(s_t)``.

        Args:
            rewards: Per-step rewards.
            values: Per-step critic values.
            dones: Per-step done flags.
            last_value: Bootstrapped value of the final next-state.

        Returns:
            Tuple of ``(advantages, returns)`` as numpy arrays.
        """
        n = len(rewards)
        advantages = np.zeros(n, dtype=np.float32)
        gae = 0.0

        for t in reversed(range(n)):
            if t == n - 1:
                next_value = last_value
                next_non_terminal = 1.0 - float(dones[t])
            else:
                next_value = values[t + 1]
                next_non_terminal = 1.0 - float(dones[t])

            delta = rewards[t] + self.config.gamma * next_value * next_non_terminal - values[t]
            gae = delta + self.config.gamma * self.config.gae_lambda * next_non_terminal * gae
            advantages[t] = gae

        returns = advantages + np.array(values, dtype=np.float32)
        return advantages, returns

    # ------------------------------------------------------------------
    # Policy update
    # ------------------------------------------------------------------

    def train_step(self, last_value: float = 0.0) -> dict[str, float]:
        """Update actor and critic using the collected trajectory.

        Args:
            last_value: Bootstrapped value of the terminal state
                        (0 if the episode ended).

        Returns:
            Dictionary with average actor loss, critic loss, and entropy.
        """
        if len(self.buffer) == 0:
            return {"actor_loss": 0.0, "critic_loss": 0.0, "entropy": 0.0}

        # Compute advantages and returns
        advantages, returns = self._compute_gae(
            self.buffer.rewards,
            self.buffer.values,
            self.buffer.dones,
            last_value,
        )

        # Convert to tensors
        states_t = torch.FloatTensor(np.array(self.buffer.states)).to(self.device)
        actions_t = torch.FloatTensor(np.array(self.buffer.actions)).to(self.device)
        old_log_probs_t = torch.FloatTensor(self.buffer.log_probs).to(self.device)
        advantages_t = torch.FloatTensor(advantages).to(self.device)
        returns_t = torch.FloatTensor(returns).to(self.device)

        # Normalise advantages (zero mean, unit variance)
        if advantages_t.numel() > 1:
            advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)

        n = len(self.buffer)
        total_actor_loss = 0.0
        total_critic_loss = 0.0
        total_entropy = 0.0
        update_count = 0

        for _ in range(self.config.n_epochs):
            indices = np.random.permutation(n)
            for start in range(0, n, self.config.batch_size):
                end = min(start + self.config.batch_size, n)
                idx = indices[start:end]

                batch_states = states_t[idx]
                batch_actions = actions_t[idx]
                batch_old_log_probs = old_log_probs_t[idx]
                batch_advantages = advantages_t[idx]
                batch_returns = returns_t[idx]

                # --- Actor loss (PPO-Clip) --------------------------------
                mean, log_std = self.actor(batch_states)
                std = log_std.exp()
                dist = Normal(mean, std)
                new_log_probs = dist.log_prob(batch_actions).sum(dim=-1)
                entropy = dist.entropy().sum(dim=-1).mean()

                ratio = (new_log_probs - batch_old_log_probs).exp()
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(
                    ratio,
                    1.0 - self.config.clip_epsilon,
                    1.0 + self.config.clip_epsilon,
                ) * batch_advantages
                actor_loss = -torch.min(surr1, surr2).mean() - self.config.entropy_coeff * entropy

                self.actor_optimizer.zero_grad()
                actor_loss.backward()
                nn.utils.clip_grad_norm_(self.actor.parameters(), self.config.max_grad_norm)
                self.actor_optimizer.step()

                # --- Critic loss ------------------------------------------
                values = self.critic(batch_states).squeeze(-1)
                critic_loss = self.config.value_loss_coeff * nn.functional.mse_loss(values, batch_returns)

                self.critic_optimizer.zero_grad()
                critic_loss.backward()
                nn.utils.clip_grad_norm_(self.critic.parameters(), self.config.max_grad_norm)
                self.critic_optimizer.step()

                total_actor_loss += actor_loss.item()
                total_critic_loss += critic_loss.item()
                total_entropy += entropy.item()
                update_count += 1

        self.buffer.clear()

        avg_actor = total_actor_loss / max(update_count, 1)
        avg_critic = total_critic_loss / max(update_count, 1)
        avg_entropy = total_entropy / max(update_count, 1)

        self._actor_losses.append(avg_actor)
        self._critic_losses.append(avg_critic)

        return {
            "actor_loss": avg_actor,
            "critic_loss": avg_critic,
            "entropy": avg_entropy,
        }

    # ------------------------------------------------------------------
    # Full training loop
    # ------------------------------------------------------------------

    def train(
        self,
        env: Any,
        n_episodes: int = 1000,
        steps_per_episode: int = 256,
        log_every: int = 50,
    ) -> dict[str, Any]:
        """Run the full PPO training loop.

        Collects on-policy trajectories of *steps_per_episode* steps,
        then performs a policy update.

        Args:
            env: Gymnasium environment with continuous action space.
            n_episodes: Total number of training episodes.
            steps_per_episode: Steps to collect before each update.
            log_every: Log interval in episodes.

        Returns:
            Dictionary with ``episode_rewards``, ``actor_losses``,
            and ``critic_losses``.
        """
        self._log.info("training_start", n_episodes=n_episodes, steps=steps_per_episode)

        for episode in range(1, n_episodes + 1):
            state, _ = env.reset()
            episode_reward = 0.0

            for _ in range(steps_per_episode):
                action, log_prob, value = self.select_action(state)
                next_state, reward, terminated, truncated, _ = env.step(action)
                done = terminated or truncated

                self.buffer.store(state, action, log_prob, reward, value, done)

                state = next_state
                episode_reward += reward

                if done:
                    state, _ = env.reset()

            # Bootstrap value of last state
            _, _, last_value = self.select_action(state, deterministic=True)
            update_info = self.train_step(last_value=last_value if not done else 0.0)

            self._episode_rewards.append(episode_reward)

            if episode % log_every == 0:
                avg_reward = float(np.mean(self._episode_rewards[-log_every:]))
                self._log.info(
                    "training_progress",
                    episode=episode,
                    avg_reward=round(avg_reward, 3),
                    actor_loss=round(update_info["actor_loss"], 5),
                    critic_loss=round(update_info["critic_loss"], 5),
                )

        self._log.info("training_complete", total_episodes=n_episodes)
        return {
            "episode_rewards": self._episode_rewards,
            "actor_losses": self._actor_losses,
            "critic_losses": self._critic_losses,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Save model weights.

        Args:
            path: File path for the checkpoint.
        """
        torch.save({
            "actor": self.actor.state_dict(),
            "critic": self.critic.state_dict(),
            "actor_optimizer": self.actor_optimizer.state_dict(),
            "critic_optimizer": self.critic_optimizer.state_dict(),
            "config": self.config,
        }, path)

    def load(self, path: str) -> None:
        """Load model weights.

        Args:
            path: File path of the checkpoint.
        """
        checkpoint = torch.load(path, map_location=self.device)
        self.actor.load_state_dict(checkpoint["actor"])
        self.critic.load_state_dict(checkpoint["critic"])
        self.actor_optimizer.load_state_dict(checkpoint["actor_optimizer"])
        self.critic_optimizer.load_state_dict(checkpoint["critic_optimizer"])


__all__ = [
    "PPOAgent",
    "PPOConfig",
    "ActorNetwork",
    "CriticNetwork",
    "TrajectoryBuffer",
]
