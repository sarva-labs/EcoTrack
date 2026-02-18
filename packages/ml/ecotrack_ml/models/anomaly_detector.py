"""Anomaly detection for environmental monitoring.

Provides :class:`EnvironmentalAutoencoder`, a variational autoencoder (VAE)
for detecting anomalous environmental sensor readings.  Anomaly scores
are computed via reconstruction error plus KL divergence.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from ecotrack_ml.models.base import (
    EcoTrackModel,
    ModelMetadata,
    ModelTask,
    PredictionResult,
)


class EnvironmentalAutoencoder(EcoTrackModel):
    """Variational Autoencoder for environmental anomaly detection.

    Architecture:
        * **Encoder** — sequence of linear layers reducing the input to
          a low-dimensional latent space, parameterised as *μ* and
          *log σ²*.
        * **Reparameterisation trick** — sample *z = μ + σ · ε* where
          *ε ∼ N(0, I)*.
        * **Decoder** — mirrored sequence of linear layers expanding
          back to the input dimensionality.

    Anomaly scoring is based on the per-sample reconstruction error
    (mean squared error between input and output).

    Args:
        metadata: Model metadata for the registry.
        input_dim: Dimensionality of input feature vectors.
        hidden_dims: List of hidden layer widths for the encoder
            (decoder mirrors in reverse).
        latent_dim: Dimensionality of the latent space.
    """

    def __init__(
        self,
        metadata: ModelMetadata | None = None,
        *,
        input_dim: int = 50,
        hidden_dims: list[int] | None = None,
        latent_dim: int = 16,
    ) -> None:
        if metadata is None:
            metadata = ModelMetadata(
                name="env_autoencoder",
                version="0.1.0",
                task=ModelTask.ANOMALY_DETECTION,
                domain="health",
                description="Variational autoencoder for environmental anomaly detection",
            )
        super().__init__(metadata)

        if hidden_dims is None:
            hidden_dims = [128, 64, 32]

        self.input_dim = input_dim
        self.latent_dim = latent_dim

        # ----- Encoder -----
        encoder_layers: list[nn.Module] = []
        in_dim = input_dim
        for h_dim in hidden_dims:
            encoder_layers.extend([
                nn.Linear(in_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.ReLU(inplace=True),
            ])
            in_dim = h_dim
        self.encoder = nn.Sequential(*encoder_layers)

        # Latent projections
        self.fc_mu = nn.Linear(hidden_dims[-1], latent_dim)
        self.fc_log_var = nn.Linear(hidden_dims[-1], latent_dim)

        # ----- Decoder -----
        decoder_layers: list[nn.Module] = []
        reversed_dims = list(reversed(hidden_dims))
        in_dim = latent_dim
        for h_dim in reversed_dims:
            decoder_layers.extend([
                nn.Linear(in_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.ReLU(inplace=True),
            ])
            in_dim = h_dim
        decoder_layers.append(nn.Linear(reversed_dims[-1], input_dim))
        self.decoder = nn.Sequential(*decoder_layers)

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode input to latent parameters.

        Args:
            x: ``(batch, input_dim)``

        Returns:
            Tuple of ``(mu, log_var)`` each of shape ``(batch, latent_dim)``.
        """
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_log_var(h)

    @staticmethod
    def reparameterize(mu: torch.Tensor, log_var: torch.Tensor) -> torch.Tensor:
        """Reparameterisation trick: z = μ + σ · ε.

        Args:
            mu: Mean of the latent Gaussian.
            log_var: Log-variance of the latent Gaussian.

        Returns:
            Sampled latent vector of the same shape.
        """
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Decode latent vector back to input space.

        Args:
            z: ``(batch, latent_dim)``

        Returns:
            ``(batch, input_dim)``
        """
        return self.decoder(z)

    def forward(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Full forward pass: encode → reparameterise → decode.

        Args:
            x: ``(batch, input_dim)``

        Returns:
            Tuple of ``(reconstruction, mu, log_var)``.
        """
        mu, log_var = self.encode(x)
        z = self.reparameterize(mu, log_var)
        return self.decode(z), mu, log_var

    def anomaly_score(self, x: torch.Tensor) -> torch.Tensor:
        """Compute per-sample anomaly scores.

        The anomaly score is the mean-squared reconstruction error
        across features for each sample.

        Args:
            x: ``(batch, input_dim)``

        Returns:
            ``(batch,)`` anomaly scores (higher → more anomalous).
        """
        self.eval()
        with torch.no_grad():
            x_hat, _, _ = self.forward(x)
            return torch.mean((x - x_hat) ** 2, dim=1)

    @staticmethod
    def vae_loss(
        x: torch.Tensor,
        x_hat: torch.Tensor,
        mu: torch.Tensor,
        log_var: torch.Tensor,
        kl_weight: float = 1.0,
    ) -> torch.Tensor:
        """Combined VAE loss: reconstruction + KL divergence.

        .. math::

            \\mathcal{L} = \\text{MSE}(x, \\hat{x})
                         + \\beta \\cdot \\text{KL}(q(z|x) \\| p(z))

        Args:
            x: Original input.
            x_hat: Reconstructed output.
            mu: Latent mean.
            log_var: Latent log-variance.
            kl_weight: Weighting factor (β) for the KL term.

        Returns:
            Scalar loss tensor.
        """
        recon_loss = F.mse_loss(x_hat, x, reduction="mean")
        kl_loss = -0.5 * torch.mean(1 + log_var - mu.pow(2) - log_var.exp())
        return recon_loss + kl_weight * kl_loss

    def predict(self, x: torch.Tensor) -> PredictionResult:
        """Override base predict to include anomaly scores.

        Args:
            x: ``(batch, input_dim)``

        Returns:
            :class:`PredictionResult` where ``predictions`` are
            reconstruction outputs and ``confidence`` contains the
            anomaly scores.
        """
        import time

        self.eval()
        start = time.perf_counter()
        with torch.no_grad():
            x_hat, mu, log_var = self.forward(x)
            scores = torch.mean((x - x_hat) ** 2, dim=1)
        elapsed = (time.perf_counter() - start) * 1000

        return PredictionResult(
            predictions=x_hat.cpu().numpy(),
            confidence=scores.cpu().numpy(),
            metadata={"mu": mu.cpu().numpy(), "log_var": log_var.cpu().numpy()},
            inference_time_ms=elapsed,
        )


__all__ = ["EnvironmentalAutoencoder"]
