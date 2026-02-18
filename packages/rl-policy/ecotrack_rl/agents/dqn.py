"""Deep Q-Network agent for discrete action spaces.

Implements a standard DQN with experience replay, target network
soft-updates, and epsilon-greedy exploration with decay.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog
import torch
import torch.nn as nn
import torch.optim as optim

logger = structlog.get_logger(__name__)


@dataclass
class DQNConfig:
    """Configuration for the DQN agent.

    Attributes:
        hidden_dims: Hidden layer sizes for the Q-network MLP.
        lr: Learning rate.
        gamma: Discount factor.
        epsilon_start: Initial exploration rate.
        epsilon_end: Minimum exploration rate.
        epsilon_decay: Multiplicative decay applied per episode.
        buffer_size: Maximum replay buffer capacity.
        batch_size: Mini-batch size for training.
        tau: Soft-update coefficient for the target network.
        train_every: Train after this many transitions stored.
    """

    hidden_dims: list[int] = field(default_factory=lambda: [128, 128])
    lr: float = 1e-3
    gamma: float = 0.99
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    buffer_size: int = 100_000
    batch_size: int = 64
    tau: float = 0.005
    train_every: int = 4


class QNetwork(nn.Module):
    """Multi-layer perceptron Q-network.

    Maps ``(state) → Q(state, action)`` for every discrete action.
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dims: list[int]) -> None:
        """Build the Q-network.

        Args:
            state_dim: Dimension of the observation space.
            action_dim: Number of discrete actions.
            hidden_dims: List of hidden layer widths.
        """
        super().__init__()
        layers: list[nn.Module] = []
        prev = state_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            prev = h
        layers.append(nn.Linear(prev, action_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: State tensor of shape ``(batch, state_dim)``.

        Returns:
            Q-values of shape ``(batch, action_dim)``.
        """
        return self.net(x)


class DQNAgent:
    """Deep Q-Network agent for discrete-action Gymnasium environments.

    Features:
    * Configurable MLP Q-network with ReLU activations.
    * Target network with Polyak (soft) update.
    * Uniform experience-replay buffer.
    * Epsilon-greedy exploration with multiplicative decay.
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        config: DQNConfig | None = None,
        device: str | None = None,
    ) -> None:
        """Initialise the DQN agent.

        Args:
            state_dim: Dimensionality of the observation vector.
            action_dim: Number of discrete actions.
            config: Optional :class:`DQNConfig`; defaults are used if *None*.
            device: PyTorch device string (auto-detected if *None*).
        """
        self.config = config or DQNConfig()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        # Networks
        self.q_network = QNetwork(state_dim, action_dim, self.config.hidden_dims).to(self.device)
        self.target_network = QNetwork(state_dim, action_dim, self.config.hidden_dims).to(self.device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_network.eval()

        self.optimizer = optim.Adam(self.q_network.parameters(), lr=self.config.lr)
        self.loss_fn = nn.MSELoss()

        # Replay buffer
        self._buffer: deque[tuple[np.ndarray, int, float, np.ndarray, bool]] = deque(
            maxlen=self.config.buffer_size,
        )

        # Exploration
        self.epsilon = self.config.epsilon_start

        # Bookkeeping
        self._total_steps: int = 0
        self._training_losses: list[float] = []
        self._episode_rewards: list[float] = []
        self._log = logger.bind(agent="DQN")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_action(self, state: np.ndarray, greedy: bool = False) -> int:
        """Select an action using epsilon-greedy exploration.

        Args:
            state: Observation array of shape ``(state_dim,)``.
            greedy: If *True*, always pick the greedy action (no exploration).

        Returns:
            Chosen action index.
        """
        if not greedy and random.random() < self.epsilon:
            return random.randrange(self.action_dim)

        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_t)
            return int(q_values.argmax(dim=1).item())

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Store a transition in the replay buffer.

        Args:
            state: Current observation.
            action: Action taken.
            reward: Reward received.
            next_state: Next observation.
            done: Whether the episode ended.
        """
        self._buffer.append((state, action, reward, next_state, done))
        self._total_steps += 1

    def train_step(self) -> float | None:
        """Sample a mini-batch and perform one gradient step.

        Returns:
            Training loss, or *None* if the buffer is too small.
        """
        if len(self._buffer) < self.config.batch_size:
            return None

        batch = random.sample(list(self._buffer), self.config.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        states_t = torch.FloatTensor(np.array(states)).to(self.device)
        actions_t = torch.LongTensor(actions).unsqueeze(1).to(self.device)
        rewards_t = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_states_t = torch.FloatTensor(np.array(next_states)).to(self.device)
        dones_t = torch.FloatTensor(dones).unsqueeze(1).to(self.device)

        # Current Q-values
        q_values = self.q_network(states_t).gather(1, actions_t)

        # Target Q-values
        with torch.no_grad():
            next_q = self.target_network(next_states_t).max(dim=1, keepdim=True).values
            target = rewards_t + self.config.gamma * next_q * (1 - dones_t)

        loss = self.loss_fn(q_values, target)

        self.optimizer.zero_grad()
        loss.backward()
        # Gradient clipping for stability
        nn.utils.clip_grad_norm_(self.q_network.parameters(), max_norm=1.0)
        self.optimizer.step()

        loss_val = loss.item()
        self._training_losses.append(loss_val)
        return loss_val

    def update_target(self) -> None:
        """Soft-update the target network towards the online network.

        Uses Polyak averaging: ``θ_target ← τ θ_online + (1-τ) θ_target``.
        """
        for tp, op in zip(self.target_network.parameters(), self.q_network.parameters()):
            tp.data.copy_(self.config.tau * op.data + (1.0 - self.config.tau) * tp.data)

    def decay_epsilon(self) -> None:
        """Decay the exploration rate by the configured factor."""
        self.epsilon = max(self.config.epsilon_end, self.epsilon * self.config.epsilon_decay)

    # ------------------------------------------------------------------
    # Full training loop
    # ------------------------------------------------------------------

    def train(
        self,
        env: Any,
        n_episodes: int = 500,
        log_every: int = 50,
    ) -> dict[str, Any]:
        """Run the full DQN training loop.

        Args:
            env: Gymnasium environment with discrete action space.
            n_episodes: Number of training episodes.
            log_every: Log progress every *N* episodes.

        Returns:
            Dictionary with ``episode_rewards`` and ``training_losses``.
        """
        self._log.info("training_start", n_episodes=n_episodes)

        for episode in range(1, n_episodes + 1):
            state, _ = env.reset()
            episode_reward = 0.0
            done = False

            while not done:
                action = self.select_action(state)
                next_state, reward, terminated, truncated, _ = env.step(action)
                done = terminated or truncated

                self.store_transition(state, action, reward, next_state, done)

                if self._total_steps % self.config.train_every == 0:
                    self.train_step()

                self.update_target()
                state = next_state
                episode_reward += reward

            self.decay_epsilon()
            self._episode_rewards.append(episode_reward)

            if episode % log_every == 0:
                avg_reward = float(np.mean(self._episode_rewards[-log_every:]))
                self._log.info(
                    "training_progress",
                    episode=episode,
                    avg_reward=round(avg_reward, 3),
                    epsilon=round(self.epsilon, 4),
                    buffer_size=len(self._buffer),
                )

        self._log.info("training_complete", total_episodes=n_episodes)
        return {
            "episode_rewards": self._episode_rewards,
            "training_losses": self._training_losses,
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
            "q_network": self.q_network.state_dict(),
            "target_network": self.target_network.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "config": self.config,
        }, path)

    def load(self, path: str) -> None:
        """Load model weights.

        Args:
            path: File path of the checkpoint.
        """
        checkpoint = torch.load(path, map_location=self.device)
        self.q_network.load_state_dict(checkpoint["q_network"])
        self.target_network.load_state_dict(checkpoint["target_network"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.epsilon = checkpoint.get("epsilon", self.config.epsilon_end)


__all__ = ["DQNAgent", "DQNConfig", "QNetwork"]
