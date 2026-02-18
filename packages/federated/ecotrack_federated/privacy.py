"""Differential privacy mechanisms for federated learning.

Provides two key components:

* :class:`PrivacyAccountant` — tracks cumulative privacy budget across
  FL rounds using the Rényi Differential Privacy (RDP) framework and
  converts to (ε, δ)-DP guarantees.

* :class:`SecureAggregation` — simplified masking scheme that ensures
  individual client updates are not visible to the server in
  plaintext (practical secure aggregation uses more sophisticated
  cryptographic protocols; this implementation demonstrates the
  concept).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch

import structlog

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────
#  Privacy Accountant (RDP-based)
# ──────────────────────────────────────────────────────────────────────


@dataclass
class PrivacyBudgetExhausted(Exception):
    """Raised when the privacy budget has been exhausted."""

    target_epsilon: float
    spent_epsilon: float

    def __str__(self) -> str:
        return (
            f"Privacy budget exhausted: spent ε={self.spent_epsilon:.4f} "
            f"exceeds target ε={self.target_epsilon:.4f}"
        )


class PrivacyAccountant:
    """Track cumulative differential privacy budget across FL rounds.

    Uses *Rényi Differential Privacy* (RDP) composition to compute a
    tight bound on the overall (ε, δ)-DP guarantee after multiple
    rounds of the Gaussian mechanism.

    The RDP of the sampled Gaussian mechanism at order α is::

        ρ(α) = α / (2σ²)

    where σ is the noise multiplier.  After *T* rounds the total
    RDP is ``T · ρ(α)`` (by composition).  We then convert back to
    (ε, δ) via::

        ε = ρ_total(α) + ln(1/δ) / (α − 1)    for optimal α > 1.

    Args:
        target_epsilon: Maximum allowed cumulative ε.
        target_delta: Target δ for (ε, δ)-DP conversion.
    """

    def __init__(
        self,
        target_epsilon: float = 10.0,
        target_delta: float = 1e-5,
    ) -> None:
        self.target_epsilon = target_epsilon
        self.target_delta = target_delta
        self._rdp_alphas = [1 + x / 10.0 for x in range(1, 100)] + list(
            range(12, 64)
        )
        self._rdp_budget: list[list[float]] = []  # list of RDP vectors per round

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_noise_to_gradients(
        self,
        parameters: list[torch.nn.Parameter],
        epsilon: float,
        delta: float,
        max_norm: float,
    ) -> float:
        """Clip gradients and add calibrated Gaussian noise.

        This is a convenience wrapper that:

        1. Clips gradients to ``max_norm``.
        2. Computes the noise multiplier ``σ`` for the given
           single-round (ε, δ) budget.
        3. Adds ``N(0, (σ · max_norm)²)`` noise to each gradient.
        4. Records the step in the privacy accountant.

        Args:
            parameters: Model parameters whose ``.grad`` will be
                modified in place.
            epsilon: Per-round privacy budget ε.
            delta: Per-round privacy budget δ.
            max_norm: Maximum L2 gradient norm (clipping threshold).

        Returns:
            The noise multiplier σ that was applied.
        """
        # Clip
        torch.nn.utils.clip_grad_norm_(parameters, max_norm)

        # Compute σ via the analytic Gaussian mechanism:
        # σ ≥ √(2 ln(1.25/δ)) / ε
        sigma = math.sqrt(2.0 * math.log(1.25 / delta)) / epsilon

        # Add noise
        with torch.no_grad():
            for param in parameters:
                if param.grad is not None:
                    noise = torch.randn_like(param.grad) * sigma * max_norm
                    param.grad.add_(noise)

        # Record RDP
        rdp_per_alpha = [alpha / (2.0 * sigma**2) for alpha in self._rdp_alphas]
        self._rdp_budget.append(rdp_per_alpha)

        logger.debug(
            "fl.privacy.noise_added",
            sigma=sigma,
            max_norm=max_norm,
            per_round_epsilon=epsilon,
        )

        return sigma

    def compute_privacy_spent(
        self,
        num_rounds: int | None = None,
        noise_multiplier: float | None = None,
        sample_rate: float = 1.0,
    ) -> tuple[float, float]:
        """Compute the cumulative (ε, δ) privacy spent.

        If ``num_rounds`` and ``noise_multiplier`` are provided, the
        budget is computed analytically (useful for planning).
        Otherwise, the accountant uses the actually recorded rounds.

        Args:
            num_rounds: Number of training rounds (for planning).
            noise_multiplier: Noise multiplier σ (for planning).
            sample_rate: Client sampling probability per round.

        Returns:
            Tuple of ``(epsilon, delta)`` for the total training.
        """
        if num_rounds is not None and noise_multiplier is not None:
            # Analytical planning mode
            rdp_per_alpha = [
                self._compute_rdp_single_step(alpha, noise_multiplier, sample_rate)
                for alpha in self._rdp_alphas
            ]
            total_rdp = [num_rounds * r for r in rdp_per_alpha]
        elif self._rdp_budget:
            # Use recorded rounds
            total_rdp = [0.0] * len(self._rdp_alphas)
            for round_rdp in self._rdp_budget:
                for i in range(len(total_rdp)):
                    total_rdp[i] += round_rdp[i]
        else:
            return 0.0, self.target_delta

        # Convert RDP to (ε, δ)
        epsilon = self._rdp_to_epsilon(total_rdp, self.target_delta)
        return epsilon, self.target_delta

    def check_budget(self, target_epsilon: float | None = None) -> bool:
        """Check whether the privacy budget has been exceeded.

        Args:
            target_epsilon: Override for the default target.

        Returns:
            ``True`` if the budget is still available, ``False`` if
            exhausted.
        """
        eps = target_epsilon or self.target_epsilon
        spent_eps, _ = self.compute_privacy_spent()
        return spent_eps <= eps

    # ------------------------------------------------------------------
    # Private helpers — RDP accounting
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_rdp_single_step(
        alpha: float,
        noise_multiplier: float,
        sample_rate: float,
    ) -> float:
        """Compute RDP of the sampled Gaussian mechanism for one step.

        For subsampled mechanisms the RDP bound (Mironov et al., 2019)
        is tighter, but for simplicity we use the full-batch Gaussian
        RDP when ``sample_rate == 1.0``.

        Args:
            alpha: RDP order (> 1).
            noise_multiplier: σ parameter.
            sample_rate: Probability of each client being selected.

        Returns:
            RDP guarantee at order α for a single step.
        """
        if noise_multiplier == 0:
            return float("inf")

        if sample_rate >= 1.0:
            # Full participation: standard Gaussian RDP
            return alpha / (2.0 * noise_multiplier**2)

        # Sub-sampled Gaussian: upper bound (Mironov et al., 2019)
        # RDP(α) ≤ (1/(α-1)) · log(1 + q²·α·(α-1) / (2σ²))
        # where q = sample_rate  (simplified bound)
        if alpha <= 1.0:
            return 0.0

        log_term = math.log(
            1.0
            + sample_rate**2
            * alpha
            * (alpha - 1.0)
            / (2.0 * noise_multiplier**2)
        )
        return log_term / (alpha - 1.0)

    def _rdp_to_epsilon(
        self,
        rdp_values: list[float],
        delta: float,
    ) -> float:
        """Convert RDP guarantees to (ε, δ)-DP.

        Uses the conversion::

            ε = min_α { rdp(α) + ln(1/δ) / (α − 1) }

        Args:
            rdp_values: RDP values at each order in ``_rdp_alphas``.
            delta: Target δ.

        Returns:
            Minimum ε over all α.
        """
        eps_candidates: list[float] = []
        for alpha, rdp_val in zip(self._rdp_alphas, rdp_values):
            if alpha <= 1.0:
                continue
            eps = rdp_val + math.log(1.0 / delta) / (alpha - 1.0)
            eps_candidates.append(eps)

        return min(eps_candidates) if eps_candidates else float("inf")


# ──────────────────────────────────────────────────────────────────────
#  Secure Aggregation (simplified demonstration)
# ──────────────────────────────────────────────────────────────────────


class SecureAggregation:
    """Simplified secure aggregation via additive masking.

    In a full cryptographic secure aggregation protocol (e.g., Bonawitz
    et al., 2017), pairwise secret sharing ensures that the server
    never sees individual updates.  This simplified implementation
    demonstrates the *concept* by:

    1. Each client masks its update with a pseudo-random tensor
       derived from a shared seed.
    2. The server sums all masked updates and then subtracts the
       aggregate mask to recover the true sum.

    .. warning::
       This is a **demonstration** — it does not provide cryptographic
       security.  Use a proper MPC library for production deployments.
    """

    @staticmethod
    def mask_update(
        update: dict[str, torch.Tensor],
        seed: int,
    ) -> dict[str, torch.Tensor]:
        """Add a deterministic pseudo-random mask to a model update.

        Args:
            update: Model state dict to mask.
            seed: Random seed for reproducible mask generation.

        Returns:
            Masked state dict (update + mask).
        """
        gen = torch.Generator()
        gen.manual_seed(seed)

        masked: dict[str, torch.Tensor] = {}
        for key, tensor in update.items():
            mask = torch.randn(tensor.shape, generator=gen, dtype=tensor.dtype)
            masked[key] = tensor + mask

        return masked

    @staticmethod
    def unmask_aggregate(
        masked_updates: list[dict[str, torch.Tensor]],
        seeds: list[int],
    ) -> dict[str, torch.Tensor]:
        """Remove masks from aggregated updates.

        Computes ``Σ masked_i − Σ mask_i`` = ``Σ update_i``.

        Args:
            masked_updates: List of masked state dicts.
            seeds: Corresponding list of seeds used for masking.

        Returns:
            The true sum of all un-masked updates.

        Raises:
            ValueError: If lengths of *masked_updates* and *seeds*
                differ.
        """
        if len(masked_updates) != len(seeds):
            raise ValueError(
                f"Got {len(masked_updates)} updates but {len(seeds)} seeds."
            )

        if not masked_updates:
            return {}

        keys = list(masked_updates[0].keys())

        # Sum all masked updates
        summed: dict[str, torch.Tensor] = {}
        for key in keys:
            summed[key] = torch.stack(
                [m[key].float() for m in masked_updates], dim=0
            ).sum(dim=0)

        # Subtract the aggregate mask
        for seed in seeds:
            gen = torch.Generator()
            gen.manual_seed(seed)
            for key in keys:
                shape = summed[key].shape
                mask = torch.randn(shape, generator=gen, dtype=summed[key].dtype)
                summed[key] -= mask

        return summed


__all__ = [
    "PrivacyAccountant",
    "PrivacyBudgetExhausted",
    "SecureAggregation",
]
